import os
import uuid
import json
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from backend.config import get_settings
from backend.orchestrator import ShieldWallOrchestrator
from backend.models.schemas import ShieldWallJobState
from backend.policy_store.indexer import index_policies

app = FastAPI()
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = ShieldWallOrchestrator(settings)

@app.on_event("startup")
async def startup():
    os.makedirs("/tmp/shield_wall", exist_ok=True)
    orchestrator.initialize()

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = file.filename.split('.')[-1].lower()
    if ext not in ['xlsx', 'csv', 'pdf', 'docx', 'txt']:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    
    job_id = str(uuid.uuid4())
    job_dir = f"/tmp/shield_wall/{job_id}"
    os.makedirs(job_dir, exist_ok=True)
    file_path = f"{job_dir}/questionnaire.{ext}"
    
    content = await file.read()
    if len(content) > settings.max_file_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large")
        
    with open(file_path, "wb") as f:
        f.write(content)
        
    orchestrator.jobs[job_id] = ShieldWallJobState(job_id=job_id, status="pending")
    return {"job_id": job_id}

@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await websocket.accept()
    
    if job_id not in orchestrator.jobs:
        await websocket.send_text(json.dumps({"error": "Job not found"}))
        await websocket.close()
        return
        
    # Get the file path
    job_dir = f"/tmp/shield_wall/{job_id}"
    files = os.listdir(job_dir)
    if not files:
        await websocket.close()
        return
    file_path = os.path.join(job_dir, files[0])
    
    async def ws_callback(event):
        await websocket.send_text(event.model_dump_json())
        
    try:
        await orchestrator.run_pipeline(job_id, file_path, ws_callback)
    except WebSocketDisconnect:
        pass

@app.get("/api/result/{job_id}")
async def get_result(job_id: str):
    if job_id not in orchestrator.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return orchestrator.jobs[job_id].model_dump()

@app.get("/api/export/{job_id}")
async def export_job(job_id: str):
    if job_id not in orchestrator.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = orchestrator.jobs[job_id]
    if job.status != "complete":
        raise HTTPException(status_code=400, detail="Job not complete")
        
    # Mocking export for MVP
    export_path = f"/tmp/shield_wall/{job_id}/answers.txt"
    with open(export_path, "w") as f:
        for ans in job.result.answers:
            f.write(f"Q{ans.question_id}: {ans.answer_text}\n\n")
            
    return FileResponse(export_path, filename="completed_questionnaire.txt")

@app.post("/api/policies/reindex")
async def reindex_policies():
    orchestrator.initialize()
    return {"status": "success"}
