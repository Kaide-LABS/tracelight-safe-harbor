import time
import json
from openai import OpenAI
from backend.models.schemas import TemplateSchema, SyntheticPayload, GenerationMetadata, TokenUsage
from backend.config import Settings

async def generate_synthetic_data(schema: TemplateSchema, settings: Settings, retry_instructions: str = None) -> SyntheticPayload:
    client = OpenAI(api_key=settings.openai_api_key)
    
    system_prompt = f"""
You are a financial data generator for institutional-grade synthetic models.

Generate realistic synthetic data for a {schema.model_type} model in the {schema.industry} sector ({schema.currency}).

RULES:
- All numbers must be internally consistent. Revenue must show realistic growth patterns.
- Cost ratios must be industry-appropriate.
- Debt schedules must amortize correctly.
- DO NOT generate random numbers. Generate numbers that tell a coherent business story.
- Respect ALL constraints specified per column.
- Base revenue should be between $50M and $500M.
- EBITDA margins should be between 10% and 40% depending on industry.
- Interest rates on debt tranches should be between 4% and 12%.
- ONLY generate values for columns that are of financial data types.
"""
    if retry_instructions:
        system_prompt += f"\nCRITICAL CORRECTION: The previous generation failed validation.\n{retry_instructions}\nRegenerate ONLY the specified line items while keeping all other values identical."

    start_time = time.time()
    completion = client.chat.completions.parse(
        model=settings.gpt4o_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(schema.model_dump())},
        ],
        response_format=SyntheticPayload,
        temperature=settings.generation_temperature,
    )
    
    generation_time = int((time.time() - start_time) * 1000)
    
    result: SyntheticPayload = completion.choices[0].message.parsed
    
    usage = completion.usage
    result.generation_metadata = GenerationMetadata(
        model_used=settings.gpt4o_model,
        temperature=settings.generation_temperature,
        token_usage=TokenUsage(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens
        ),
        generation_time_ms=generation_time
    )
    
    return result
