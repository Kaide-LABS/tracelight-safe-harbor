import openpyxl

def parse_excel_questionnaire(file_path: str) -> list[dict]:
    wb = openpyxl.load_workbook(file_path, data_only=True)
    questions = []
    
    for ws in wb.worksheets:
        header_row_idx = None
        for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
            if not row:
                continue
            
            # Detect header row
            if header_row_idx is None:
                row_strs = [str(c).lower() for c in row if c is not None]
                if any("question" in c or "requirement" in c or "control" in c or "#" in c or "id" in c for c in row_strs):
                    header_row_idx = row_idx
                    continue
                
            if header_row_idx is not None and row_idx > header_row_idx:
                # Find the longest text column as the question text
                longest_text = ""
                for cell in row:
                    if isinstance(cell, str) and len(cell) > len(longest_text):
                        longest_text = cell
                
                if longest_text.strip():
                    questions.append({
                        "text": longest_text.strip(),
                        "row": row_idx,
                        "sheet": ws.title
                    })
                    
    return questions
