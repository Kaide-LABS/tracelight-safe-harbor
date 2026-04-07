import docx
import pandas as pd
import re

def parse_docx_questionnaire(file_path: str) -> list[dict]:
    questions = []
    try:
        doc = docx.Document(file_path)
        for i, para in enumerate(doc.paragraphs):
            text = para.text.strip()
            # Heuristic: if it ends with '?' or starts with a number
            if text and (text.endswith('?') or re.match(r"^\d{1,3}[\.\)]", text)):
                questions.append({
                    "text": text,
                    "paragraph_index": i
                })
    except Exception as e:
        print(f"Error parsing DOCX: {e}")
    return questions

def parse_csv_questionnaire(file_path: str) -> list[dict]:
    questions = []
    try:
        df = pd.read_csv(file_path)
        # Find column with longest average string length
        best_col = None
        max_len = 0
        for col in df.columns:
            if df[col].dtype == object:
                avg_len = df[col].dropna().astype(str).str.len().mean()
                if avg_len > max_len:
                    max_len = avg_len
                    best_col = col
                    
        if best_col:
            for idx, val in df[best_col].items():
                if pd.notna(val) and str(val).strip():
                    questions.append({
                        "text": str(val).strip(),
                        "row": idx + 2 # +2 to account for header and 0-indexing
                    })
    except Exception as e:
        print(f"Error parsing CSV: {e}")
    return questions
