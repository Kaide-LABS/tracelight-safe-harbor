import json
import logging
import asyncio
from datetime import datetime
from google import genai
from google.genai import types
from backend.models.schemas import SecurityQuestion, TelemetryEvidence
from backend.telemetry.base import TelemetryAdapter
from backend.config import ShieldWallSettings

logger = logging.getLogger(__name__)

TELEMETRY_TOOL_DECLARATIONS = [
    types.FunctionDeclaration(
        name="query_cloudtrail",
        description="Search AWS CloudTrail logs for specific events",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "event_name": types.Schema(type="STRING", description="CloudTrail event name (e.g., ConsoleLogin, CreateUser)"),
                "time_range_days": types.Schema(type="INTEGER", description="Look back N days"),
                "filter_key": types.Schema(type="STRING"),
                "filter_value": types.Schema(type="STRING"),
            },
            required=["event_name"],
        ),
    ),
    types.FunctionDeclaration(
        name="query_iam_config",
        description="Retrieve IAM configuration: MFA status, password policies, role definitions",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "query_type": types.Schema(type="STRING", enum=["mfa_status", "password_policy", "roles", "users", "access_keys"]),
            },
            required=["query_type"],
        ),
    ),
    types.FunctionDeclaration(
        name="query_encryption_status",
        description="Check KMS encryption status of AWS resources",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "resource_type": types.Schema(type="STRING", enum=["rds", "s3", "ebs", "dynamodb"]),
            },
            required=["resource_type"],
        ),
    ),
    types.FunctionDeclaration(
        name="query_network_config",
        description="Retrieve VPC, security group, and network ACL configurations",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "query_type": types.Schema(type="STRING", enum=["security_groups", "vpc_flow_logs", "nacls", "public_endpoints"]),
            },
            required=["query_type"],
        ),
    ),
]

SYSTEM_PROMPT = """You are a cloud security engineer with read-only access to AWS infrastructure.
Given a security questionnaire question, determine which infrastructure queries
would provide evidence to answer it. Use the available tools to retrieve live
infrastructure state. Summarize what each result proves.
Do NOT fabricate evidence. If no relevant data is found, say so."""


async def _process_single_question(q: SecurityQuestion, adapter: TelemetryAdapter, settings: ShieldWallSettings, client: genai.Client) -> list[TelemetryEvidence]:
    if not q.requires_telemetry:
        return []

    evidence_list = []
    tool = types.Tool(function_declarations=TELEMETRY_TOOL_DECLARATIONS)

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=settings.gemini_model,
            contents=[
                types.Content(role="user", parts=[
                    types.Part.from_text(f"Question: {q.normalized_query}\nCategory: {q.category}")
                ])
            ],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=[tool],
                temperature=0.1,
            ),
        )

        # Process function calls from response
        for candidate in response.candidates:
            for part in candidate.content.parts:
                if part.function_call:
                    fc = part.function_call
                    func_name = fc.name
                    args = dict(fc.args) if fc.args else {}

                    # Execute tool against adapter
                    raw_result = await adapter.execute(func_name, **args)

                    # Ask Gemini to summarize the result
                    sum_response = await asyncio.to_thread(
                        client.models.generate_content,
                        model=settings.gemini_model,
                        contents=f"Summarize this AWS infrastructure query result for a security questionnaire.\nQuestion: {q.normalized_query}\nTool: {func_name}({json.dumps(args)})\nResult: {json.dumps(raw_result)}",
                        config=types.GenerateContentConfig(temperature=0.1),
                    )

                    summary = sum_response.text

                    evidence_list.append(TelemetryEvidence(
                        question_id=q.id,
                        query_executed=f"{func_name}({json.dumps(args)})",
                        query_type="mock" if settings.demo_mode else "athena_sql",
                        raw_result=raw_result if isinstance(raw_result, (dict, list)) else {"result": raw_result},
                        summary=summary,
                        timestamp=datetime.utcnow().isoformat() + "Z",
                        proves="Telemetry indicates actual infrastructure state matches summary."
                    ))

    except Exception as e:
        logger.error(f"Error gathering telemetry for Q{q.id}: {e}")

    return evidence_list


async def gather_telemetry(questions: list[SecurityQuestion], adapter: TelemetryAdapter, settings: ShieldWallSettings) -> list[TelemetryEvidence]:
    client = genai.Client(api_key=settings.gemini_api_key)
    semaphore = asyncio.Semaphore(10)

    async def _bounded(q):
        async with semaphore:
            return await _process_single_question(q, adapter, settings, client)

    results = await asyncio.gather(*[_bounded(q) for q in questions])

    flattened = []
    for r in results:
        flattened.extend(r)
    return flattened
