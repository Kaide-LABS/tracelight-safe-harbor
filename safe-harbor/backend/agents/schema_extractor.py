import json
from google import genai
from google.genai import types
from backend.models.schemas import TemplateSchema
from backend.config import Settings

async def extract_schema(parsed_template: dict, settings: Settings) -> TemplateSchema:
    client = genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
    )
    
    system_prompt = """
You are a financial model analyst specializing in LBO, DCF, and 3-statement models.

Given the following Excel template structure (JSON), perform these tasks:
1. Classify each column header by its financial data type: currency_USD, currency_EUR, currency_GBP, percentage, ratio, integer, date, or text.
2. Identify the temporal range (e.g., FY2020-FY2025) for each column with time-series data.
3. Detect inter-sheet dependencies from the formula references provided.
4. Classify the overall model type as LBO, DCF, 3-statement, or unknown.
5. Infer the likely industry sector from any contextual clues in the headers or sheet names. If no clues, default to "General Corporate".
6. Set realistic constraints for each input column:
    - Revenue: growth_rate_range of (-0.10, 0.30), must_be_positive=True
    - COGS/OpEx: must_be_positive=True
    - Margins: min 0.0, max 1.0
    - Debt tranches: must_be_positive=True
    - Interest rates: min 0.0, max 0.25

Output ONLY valid JSON conforming exactly to the required schema.
"""
    
    schema_json = TemplateSchema.model_json_schema()
    
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=f"{system_prompt}\n\nRequired Schema:\n{json.dumps(schema_json)}\n\nTemplate Structure:\n{json.dumps(parsed_template)}",
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    top_p=0.9,
                    response_mime_type="application/json"
                ),
            )
            
            raw_text = response.text
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:-3]
                
            parsed = json.loads(raw_text)
            schema = TemplateSchema.model_validate(parsed)
            
            # Map cell references and periods from original parsed_template
            for sheet in schema.sheets:
                # Find matching sheet in parsed_template
                pt_sheet = next((s for s in parsed_template["sheets"] if s["name"] == sheet.name), None)
                if pt_sheet:
                    for col in sheet.columns:
                        refs = []
                        periods = []
                        for ic in pt_sheet["input_cells"]:
                            if ic["column_header"] == col.header:
                                refs.append(ic["ref"])
                                if "period" in ic and ic["period"]:
                                    periods.append(ic["period"])
                        col.cell_references = refs
                        col.periods = list(dict.fromkeys(periods)) # unique
            return schema
        except Exception as e:
            if attempt == 2:
                raise e
