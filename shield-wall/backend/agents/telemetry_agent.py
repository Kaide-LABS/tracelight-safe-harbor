import json
import asyncio
from datetime import datetime
from openai import AsyncOpenAI
from backend.models.schemas import SecurityQuestion, TelemetryEvidence
from backend.telemetry.base import TelemetryAdapter
from backend.config import ShieldWallSettings

TELEMETRY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_cloudtrail",
            "description": "Search AWS CloudTrail logs for specific events",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_name": {"type": "string", "description": "CloudTrail event name (e.g., ConsoleLogin, CreateUser)"},
                    "time_range_days": {"type": "integer", "description": "Look back N days"},
                    "filter_key": {"type": "string"},
                    "filter_value": {"type": "string"},
                },
                "required": ["event_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_iam_config",
            "description": "Retrieve IAM configuration: MFA status, password policies, role definitions",
            "parameters": {
                "type": "object",
                "properties": {
                    "query_type": {"type": "string", "enum": ["mfa_status", "password_policy", "roles", "users", "access_keys"]},
                },
                "required": ["query_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_encryption_status",
            "description": "Check KMS encryption status of AWS resources",
            "parameters": {
                "type": "object",
                "properties": {
                    "resource_type": {"type": "string", "enum": ["rds", "s3", "ebs", "dynamodb"]},
                },
                "required": ["resource_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_network_config",
            "description": "Retrieve VPC, security group, and network ACL configurations",
            "parameters": {
                "type": "object",
                "properties": {
                    "query_type": {"type": "string", "enum": ["security_groups", "vpc_flow_logs", "nacls", "public_endpoints"]},
                },
                "required": ["query_type"]
            }
        }
    }
]

async def _process_single_question(q: SecurityQuestion, adapter: TelemetryAdapter, settings: ShieldWallSettings, openai_client: AsyncOpenAI) -> list[TelemetryEvidence]:
    if not q.requires_telemetry:
        return []
        
    system_prompt = """
You are a cloud security engineer with read-only access to AWS infrastructure.
Given a security questionnaire question, determine which infrastructure queries
would provide evidence to answer it. Use the available tools to retrieve live
infrastructure state. Summarize what each result proves.
Do NOT fabricate evidence. If no relevant data is found, say so.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Question: {q.normalized_query}\nCategory: {q.category}"}
    ]
    
    evidence_list = []
    
    try:
        response = await openai_client.chat.completions.create(
            model=settings.gpt4o_model,
            messages=messages,
            tools=TELEMETRY_TOOLS,
            tool_choice="auto",
        )
        
        msg = response.choices[0].message
        if msg.tool_calls:
            for tool_call in msg.tool_calls:
                func_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                
                # Execute tool
                raw_result = await adapter.execute(func_name, **args)
                
                # Ask GPT to summarize
                messages.append(msg)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(raw_result)
                })
                
                sum_resp = await openai_client.chat.completions.create(
                    model=settings.gpt4o_model,
                    messages=messages
                )
                
                summary = sum_resp.choices[0].message.content
                
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
        print(f"Error gathering telemetry for Q{q.id}: {e}")
        
    return evidence_list

async def gather_telemetry(questions: list[SecurityQuestion], adapter: TelemetryAdapter, settings: ShieldWallSettings) -> list[TelemetryEvidence]:
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    
    tasks = []
    for q in questions:
        tasks.append(_process_single_question(q, adapter, settings, openai_client))
        
    # Run in parallel, limit concurrency if needed (using gather for now)
    results = await asyncio.gather(*tasks)
    
    flattened = []
    for r in results:
        flattened.extend(r)
        
    return flattened
