import os
import uuid
import json
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from backend.config import get_settings
from backend.orchestrator import PipelineOrchestrator
from backend.models.schemas import JobState

app = FastAPI()
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = PipelineOrchestrator(settings)

@app.on_event("startup")
async def startup():
    os.makedirs("/tmp/safe_harbor", exist_ok=True)

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename.endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Must be an .xlsx or .xlsm file")
    
    job_id = str(uuid.uuid4())
    job_dir = f"/tmp/safe_harbor/{job_id}"
    os.makedirs(job_dir, exist_ok=True)
    file_path = f"{job_dir}/template.xlsx"
    
    content = await file.read()
    if len(content) > settings.max_file_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large")
        
    with open(file_path, "wb") as f:
        f.write(content)
        
    orchestrator.jobs[job_id] = JobState(job_id=job_id, status="pending")
    return {"job_id": job_id}

@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await websocket.accept()
    
    if job_id not in orchestrator.jobs:
        await websocket.send_text(json.dumps({"error": "Job not found"}))
        await websocket.close()
        return
        
    file_path = f"/tmp/safe_harbor/{job_id}/template.xlsx"
    
    async def ws_callback(event):
        await websocket.send_text(event.model_dump_json())
        
    try:
        await orchestrator.run_pipeline(job_id, file_path, ws_callback)
    except WebSocketDisconnect:
        print(f"Client disconnected for job {job_id}")
    finally:
        pass

@app.get("/api/download/{job_id}")
async def download(job_id: str):
    if job_id not in orchestrator.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = orchestrator.jobs[job_id]
    if job.status != "complete":
        raise HTTPException(status_code=400, detail="Job not complete")
        
    return FileResponse(
        job.output_file_path, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
        filename="safe_harbor_model.xlsx"
    )

@app.get("/api/audit/{job_id}")
async def get_audit(job_id: str):
    if job_id not in orchestrator.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = orchestrator.jobs[job_id]
    if job.status == "pending":
        raise HTTPException(status_code=400, detail="Job still pending")
        
    return job.model_dump()
