import os
import chromadb
from openai import OpenAI
import PyPDF2
import docx

def index_policies(policy_dir: str, settings):
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    collection = client.get_or_create_collection("shield_wall_policies", metadata={"hnsw:space": "cosine"})
    
    # Simple check if already indexed to save time in demo
    if collection.count() > 0:
        return collection
        
    openai_client = OpenAI(api_key=settings.openai_api_key)
    
    for filename in os.listdir(policy_dir):
        filepath = os.path.join(policy_dir, filename)
        text = ""
        if filename.endswith(".pdf"):
            try:
                reader = PyPDF2.PdfReader(filepath)
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted: text += extracted + "\n"
            except Exception: pass
        elif filename.endswith(".docx"):
            try:
                doc = docx.Document(filepath)
                for para in doc.paragraphs:
                    text += para.text + "\n"
            except Exception: pass
        elif filename.endswith((".md", ".txt")):
            with open(filepath, "r") as f:
                text = f.read()
                
        if not text.strip():
            continue
            
        import tiktoken
        enc = tiktoken.encoding_for_model("text-embedding-3-small")
        tokens = enc.encode(text)
        
        chunk_size = settings.policy_chunk_size
        overlap = settings.policy_chunk_overlap
        
        chunks = []
        for i in range(0, len(tokens), chunk_size - overlap):
            chunk_tokens = tokens[i:i + chunk_size]
            chunks.append(enc.decode(chunk_tokens))
            
        for i, chunk in enumerate(chunks):
            try:
                resp = openai_client.embeddings.create(model="text-embedding-3-small", input=chunk)
                embedding = resp.data[0].embedding
                chunk_id = f"{filename}_chunk_{i}"
                
                collection.add(
                    ids=[chunk_id],
                    embeddings=[embedding],
                    documents=[chunk],
                    metadatas=[{"source": filename, "section": "General", "chunk_index": i}]
                )
            except Exception as e:
                print(f"Error indexing chunk {i} of {filename}: {e}")
                
    return collection
