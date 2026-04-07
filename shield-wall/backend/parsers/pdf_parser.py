import PyPDF2
import re

def parse_pdf_questionnaire(file_path: str) -> list[dict]:
    questions = []
    try:
        reader = PyPDF2.PdfReader(file_path)
        full_text = ""
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                full_text += text + "\n"
        
        # Split on numbered patterns: "1. ", "2) ", etc.
        pattern = re.compile(r"(\d{1,3}[\.\)]\s)")
        segments = pattern.split(full_text)
        
        # segments will be ['prefix', '1. ', 'Question...', '2. ', 'Question...']
        # Combine the number and the question
        for i in range(1, len(segments), 2):
            number = segments[i]
            q_text = segments[i+1].strip() if i+1 < len(segments) else ""
            if q_text:
                questions.append({
                    "text": number + q_text,
                    "page": -1 # page tracking simplified
                })
    except Exception as e:
        print(f"Error parsing PDF: {e}")
        
    return questions
