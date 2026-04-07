import json
from google import genai
from google.genai import types
from pydantic import BaseModel
from backend.models.schemas import ParsedQuestionnaire, SecurityQuestion
from backend.config import ShieldWallSettings

class ParsedBatch(BaseModel):
    questions: list[SecurityQuestion]

async def parse_questionnaire(raw_questions: list[dict], file_name: str, file_ext: str, settings: ShieldWallSettings) -> ParsedQuestionnaire:
    client = genai.Client(vertexai=True, project=settings.google_cloud_project, location=settings.google_cloud_location)
    
    system_prompt = """
You are an information security analyst classifying vendor security questionnaire questions.

For each question:
1. Assign a category from: access_control, encryption, network_security, incident_response, data_classification, business_continuity, vendor_management, physical_security, compliance, logging_monitoring, change_management, other.
2. Rewrite it as a clear, unambiguous normalized query.
3. Determine if answering requires live infrastructure telemetry (e.g., "Is MFA enforced?" -> true).
4. Determine if answering requires policy document citation (e.g., "What is your IR plan?" -> true).

Output JSON array conforming to the requested schema.
"""

    # Batching logic (simplified for MVP: send all if small, else truncate)
    batch = raw_questions[:settings.max_questions]
    
    import random
    
    structured_questions = []
    
    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=f"{system_prompt}\n\nQuestions:\n{json.dumps(batch)}",
            config=types.GenerateContentConfig(
                temperature=0.1,
                top_p=0.9,
                response_mime_type="application/json",
                response_schema=ParsedBatch.model_json_schema()
            ),
        )
        
        parsed = json.loads(response.text)
        structured_questions = parsed.get("questions", [])
        
        for i, sq in enumerate(structured_questions):
            sq["id"] = i + 1
            if i < len(batch):
                sq["source_row"] = batch[i].get("row")
                sq["source_sheet"] = batch[i].get("sheet")
                sq["original_text"] = batch[i].get("text", sq.get("original_text"))
                
    except Exception as e:
        print(f"Gemini parsing failed: {e}. Falling back to basic mapping.")
        for i, rq in enumerate(batch):
            structured_questions.append({
                "id": i + 1,
                "category": "other",
                "original_text": rq.get("text", ""),
                "normalized_query": rq.get("text", ""),
                "requires_telemetry": True,
                "requires_policy": True,
                "source_row": rq.get("row"),
                "source_sheet": rq.get("sheet")
            })
            
    final_questions = [SecurityQuestion(**sq) for sq in structured_questions]
            
    return ParsedQuestionnaire(
        source_file=file_name,
        source_format=file_ext,
        total_questions=len(final_questions),
        questions=final_questions,
        metadata={}
    )
