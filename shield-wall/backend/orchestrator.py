import asyncio
from datetime import datetime
from typing import Callable, Awaitable
import os

from backend.config import ShieldWallSettings
from backend.models.schemas import ShieldWallJobState, ShieldWallWSEvent, ShieldWallAuditEntry, QuestionnaireResult, ParsedQuestionnaire
from backend.telemetry.mock_adapter import MockTelemetryAdapter
from backend.telemetry.aws_adapter import AWSLiveTelemetryAdapter
from backend.policy_store.indexer import index_policies
from backend.agents.questionnaire_parser import parse_questionnaire
from backend.agents.telemetry_agent import gather_telemetry
from backend.agents.policy_agent import gather_policy_citations
from backend.agents.synthesis_agent import synthesize_answers
from backend.agents.drift_detector import detect_drift

from backend.parsers.excel_parser import parse_excel_questionnaire
from backend.parsers.pdf_parser import parse_pdf_questionnaire
from backend.parsers.text_parser import parse_docx_questionnaire, parse_csv_questionnaire

class ShieldWallOrchestrator:
    def __init__(self, settings: ShieldWallSettings):
        self.settings = settings
        self.jobs: dict[str, ShieldWallJobState] = {}
        if settings.demo_mode:
            self.adapter = MockTelemetryAdapter()
        else:
            self.adapter = AWSLiveTelemetryAdapter(None, settings.aws_athena_database)
        self.policy_collection = None

    def initialize(self):
        # Synchronous initialization of ChromaDB
        self.policy_collection = index_policies("./data/policies", self.settings)

    def _log_audit(self, job_id: str, phase: str, detail: str, agent: str = None, data: dict = None):
        if job_id in self.jobs:
            entry = ShieldWallAuditEntry(
                timestamp=datetime.utcnow().isoformat() + "Z",
                phase=phase,
                detail=detail,
                agent=agent,
                data=data
            )
            self.jobs[job_id].audit_log.append(entry)

    async def run_pipeline(self, job_id: str, file_path: str, ws_callback: Callable[[ShieldWallWSEvent], Awaitable[None]]):
        try:
            await asyncio.wait_for(
                self._execute(job_id, file_path, ws_callback),
                timeout=self.settings.generation_timeout_s
            )
        except asyncio.TimeoutError:
            self.jobs[job_id].status = "error"
            self.jobs[job_id].error_message = "Processing timed out"
            await ws_callback(ShieldWallWSEvent(job_id=job_id, phase="error", event_type="error", detail="Processing timed out"))
        except Exception as e:
            self.jobs[job_id].status = "error"
            self.jobs[job_id].error_message = str(e)
            await ws_callback(ShieldWallWSEvent(job_id=job_id, phase="error", event_type="error", detail=str(e)))

    async def _execute(self, job_id: str, file_path: str, ws_callback: Callable[[ShieldWallWSEvent], Awaitable[None]]):
        import time
        _pipeline_start = time.time()
        self.jobs[job_id].status = "parsing"
        await ws_callback(ShieldWallWSEvent(job_id=job_id, phase="parsing", event_type="progress", detail=f"Parsing uploaded file {file_path}..."))
        
        # 1. Parse Phase
        ext = file_path.split('.')[-1].lower()
        raw_questions = []
        if ext in ['xlsx', 'xlsm']:
            raw_questions = await asyncio.to_thread(parse_excel_questionnaire, file_path)
        elif ext == 'pdf':
            raw_questions = await asyncio.to_thread(parse_pdf_questionnaire, file_path)
        elif ext == 'docx':
            raw_questions = await asyncio.to_thread(parse_docx_questionnaire, file_path)
        elif ext == 'csv':
            raw_questions = await asyncio.to_thread(parse_csv_questionnaire, file_path)
        elif ext == 'txt':
            with open(file_path, 'r') as f:
                raw_questions = [{"text": line.strip(), "row": i} for i, line in enumerate(f) if line.strip() and line.strip().endswith('?')]
        
        self._log_audit(job_id, "parse", f"Extracted {len(raw_questions)} raw questions")
        await ws_callback(ShieldWallWSEvent(job_id=job_id, phase="parsing", event_type="progress", detail=f"[PARSE] Detected {len(raw_questions)} questions"))
        
        # 2. Classification Phase
        self.jobs[job_id].status = "classifying"
        questionnaire = await parse_questionnaire(raw_questions, os.path.basename(file_path), ext, self.settings)
        self.jobs[job_id].questionnaire = questionnaire
        
        requires_tel = sum(1 for q in questionnaire.questions if q.requires_telemetry)
        requires_pol = sum(1 for q in questionnaire.questions if q.requires_policy)
        categories = len(set(q.category for q in questionnaire.questions))
        
        self._log_audit(job_id, "classifying", "Classification complete", agent="Gemini 2.0 Flash")
        await ws_callback(ShieldWallWSEvent(job_id=job_id, phase="classifying", event_type="progress", detail=f"[CLASS] {requires_tel} require telemetry, {requires_pol} require policy citation, {categories} categories detected"))
        
        # 3. Parallel Evidence Gathering
        self.jobs[job_id].status = "querying_telemetry"
        
        q_tel = [q for q in questionnaire.questions if q.requires_telemetry]
        q_pol = [q for q in questionnaire.questions if q.requires_policy]
        
        await ws_callback(ShieldWallWSEvent(job_id=job_id, phase="querying_telemetry", event_type="progress", detail="[TELEM] Executing infrastructure queries..."))
        await ws_callback(ShieldWallWSEvent(job_id=job_id, phase="querying_policies", event_type="progress", detail="[POLICY] Retrieving policy citations from vector store..."))
        
        telemetry_task = gather_telemetry(q_tel, self.adapter, self.settings)
        policy_task = gather_policy_citations(q_pol, self.policy_collection, self.settings)
        
        telemetry_results_list, policy_results = await asyncio.gather(telemetry_task, policy_task)
        
        # Format telemetry results dict
        telemetry_results = {}
        for ev in telemetry_results_list:
            if ev.question_id not in telemetry_results:
                telemetry_results[ev.question_id] = []
            telemetry_results[ev.question_id].append(ev)
            
        self._log_audit(job_id, "evidence_gathering", "Retrieved telemetry and policies")
        
        # 4. Synthesis Phase
        self.jobs[job_id].status = "synthesizing"
        await ws_callback(ShieldWallWSEvent(job_id=job_id, phase="synthesizing", event_type="progress", detail="[SYNTH] Drafting answers..."))
        
        answers = await synthesize_answers(questionnaire.questions, telemetry_results, policy_results, self.settings)
        for ans in answers:
            await ws_callback(ShieldWallWSEvent(job_id=job_id, phase="synthesizing", event_type="answer_update", detail=f"[SYNTH] Q#{ans.question_id} — Answer drafted ({ans.confidence.upper()} confidence)"))
            
        # 5. Drift Detection Phase
        self.jobs[job_id].status = "detecting_drift"
        drift_alerts = detect_drift(answers)
        self.jobs[job_id].drift_alerts = drift_alerts
        
        for alert in drift_alerts:
            prefix = "⚠ CRITICAL:" if alert.severity == "critical" else "⚠ WARNING:"
            await ws_callback(ShieldWallWSEvent(job_id=job_id, phase="detecting_drift", event_type="drift_alert", detail=f"[DRIFT] {prefix} Q#{alert.question_id} — {alert.telemetry_shows}"))
            
        # 6. Complete
        high_conf = sum(1 for a in answers if a.confidence == "high")
        med_conf = sum(1 for a in answers if a.confidence == "medium")
        low_conf = sum(1 for a in answers if a.confidence == "low")
        needs_review = sum(1 for a in answers if a.needs_human_review)
        
        result = QuestionnaireResult(
            total_questions=len(questionnaire.questions),
            answered=len(answers),
            high_confidence=high_conf,
            medium_confidence=med_conf,
            low_confidence=low_conf,
            drift_alerts=len(drift_alerts),
            needs_review=needs_review,
            answers=answers,
            processing_time_ms=int((time.time() - _pipeline_start) * 1000),
            export_ready=True
        )
        
        self.jobs[job_id].result = result
        self.jobs[job_id].status = "complete"
        
        await ws_callback(ShieldWallWSEvent(job_id=job_id, phase="complete", event_type="complete", detail="Shield-Wall analysis complete.", data=result.model_dump()))
