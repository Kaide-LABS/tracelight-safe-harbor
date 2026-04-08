import time
import json
import asyncio
import functools
import logging
from google import genai
from google.genai import types
from backend.models.schemas import TemplateSchema, SyntheticPayload, GenerationMetadata, TokenUsage
from backend.config import Settings

logger = logging.getLogger(__name__)

async def generate_synthetic_data(schema: TemplateSchema, settings: Settings, retry_instructions: str = None, parsed_template: dict = None) -> SyntheticPayload:
    client = genai.Client(api_key=settings.gemini_api_key)

    # Build input cells list from the PARSER output (authoritative), not the schema
    input_cells_desc = []
    if parsed_template:
        for sheet in parsed_template["sheets"]:
            for ic in sheet["input_cells"]:
                input_cells_desc.append({
                    "sheet_name": sheet["name"],
                    "header": ic["column_header"],
                    "period": ic.get("period", ""),
                    "cell_ref": ic["ref"],
                })
    else:
        # Fallback to schema if no parsed template
        for sheet in schema.sheets:
            for col in sheet.columns:
                if col.is_input and col.periods:
                    for period in col.periods:
                        idx = col.periods.index(period)
                        input_cells_desc.append({
                            "sheet_name": sheet.name,
                            "header": col.header,
                            "period": period,
                            "cell_ref": col.cell_references[idx] if idx < len(col.cell_references) else ""
                        })

    total_cells = len(input_cells_desc)

    system_prompt = f"""You are a financial data generator for institutional-grade synthetic models.

Generate realistic synthetic data for a {schema.model_type} model in the {schema.industry} sector ({schema.currency}).

You MUST generate a value for EVERY input cell listed below. There are {total_cells} cells total.

RULES:
- All numbers must be internally consistent. Revenue must show realistic growth patterns.
- Cost ratios must be industry-appropriate.
- Debt schedules must amortize correctly.
- DO NOT generate random numbers. Generate numbers that tell a coherent business story.
- Respect ALL constraints specified per column.
- Base revenue should be between $50M and $500M.
- EBITDA margins should be between 10% and 40% depending on industry.
- Interest rates on debt tranches should be between 4% and 12%.
- Percentages should be expressed as decimals (e.g. 25% = 0.25).
- ONLY generate values for the input cells listed. Do NOT skip any.
- Every cell in the output "cells" array must have: sheet_name, cell_ref, header, period, value.

OUTPUT FORMAT:
Return valid JSON with this exact structure:
{{
  "model_type": "{schema.model_type}",
  "industry": "{schema.industry}",
  "currency": "{schema.currency}",
  "cells": [
    {{"sheet_name": "...", "cell_ref": "...", "header": "...", "period": "...", "value": ...}},
    ... (one entry for EACH of the {total_cells} input cells)
  ],
  "generation_metadata": {{
    "model_used": "{settings.gemini_model}",
    "temperature": 1.0,
    "token_usage": {{"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}},
    "generation_time_ms": 0
  }}
}}
"""

    if retry_instructions:
        system_prompt += f"\nCRITICAL CORRECTION: The previous generation failed validation.\n{retry_instructions}\nRegenerate ONLY the specified line items while keeping all other values identical."

    user_content = f"Schema:\n{json.dumps(schema.model_dump())}\n\nInput cells to fill ({total_cells} total):\n{json.dumps(input_cells_desc)}"

    start_time = time.time()

    response = await asyncio.to_thread(
        functools.partial(
            client.models.generate_content,
            model=settings.gemini_model,
            contents=f"{system_prompt}\n\n{user_content}",
            config=types.GenerateContentConfig(
                temperature=1.0,
                max_output_tokens=65536,
                thinking_config=types.ThinkingConfig(thinking_budget=2048),
                response_mime_type="application/json",
            ),
        )
    )

    generation_time = int((time.time() - start_time) * 1000)

    raw_text = response.text
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]

    parsed = json.loads(raw_text)
    result = SyntheticPayload.model_validate(parsed)

    # Update metadata with actual usage
    usage_meta = getattr(response, 'usage_metadata', None)
    prompt_tokens = getattr(usage_meta, 'prompt_token_count', 0) if usage_meta else 0
    completion_tokens = getattr(usage_meta, 'candidates_token_count', 0) if usage_meta else 0

    result.generation_metadata = GenerationMetadata(
        model_used=settings.gemini_model,
        temperature=1.0,
        token_usage=TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens
        ),
        generation_time_ms=generation_time
    )

    logger.info(f"Gemini generated {len(result.cells)} cells (expected {total_cells}) in {generation_time}ms")

    return result
