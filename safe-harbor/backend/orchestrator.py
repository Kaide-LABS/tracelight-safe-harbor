import asyncio
import uuid
import time
import logging
from typing import Callable, Awaitable
from datetime import datetime

from backend.config import Settings
from backend.models.schemas import JobState, WSEvent, AuditLogEntry, TemplateSchema, SyntheticPayload
from backend.excel_io.parser import parse_template
from backend.excel_io.writer import write_synthetic_data
from backend.agents.schema_extractor import extract_schema
from backend.agents.synthetic_gen import generate_synthetic_data
from backend.agents.validator import DeterministicValidator
from backend.agents.post_processor import post_process
from backend.agents.bs_plug import balance_bs
from backend.middleware import cost_tracker

logger = logging.getLogger(__name__)

class PipelineOrchestrator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.jobs: dict[str, JobState] = {}

    def _update_status(self, job_id: str, status: str):
        self.jobs[job_id].status = status

    def _log_audit(self, job_id: str, phase: str, detail: str, agent: str = None, data: dict = None):
        entry = AuditLogEntry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            phase=phase,
            detail=detail,
            agent=agent,
            data=data
        )
        self.jobs[job_id].audit_log.append(entry)

    async def run_pipeline(self, job_id: str, file_path: str, ws_callback: Callable[[WSEvent], Awaitable[None]]):
        try:
            await asyncio.wait_for(
                self._execute(job_id, file_path, ws_callback),
                timeout=self.settings.generation_timeout_s
            )
        except asyncio.TimeoutError:
            self._update_status(job_id, "error")
            self.jobs[job_id].error_message = "Generation timed out"
            await ws_callback(WSEvent(job_id=job_id, phase="error", event_type="error", detail="Generation timed out"))
        except Exception as e:
            self._update_status(job_id, "error")
            self.jobs[job_id].error_message = str(e)
            await ws_callback(WSEvent(job_id=job_id, phase="error", event_type="error", detail=str(e)))

    async def _execute(self, job_id: str, file_path: str, ws_callback: Callable[[WSEvent], Awaitable[None]]):
        # 1. Parse Phase
        self._update_status(job_id, "parsing")
        await ws_callback(WSEvent(job_id=job_id, phase="parse", event_type="progress", detail="Parsing Excel template..."))
        
        parsed = await asyncio.to_thread(parse_template, file_path)
        self.jobs[job_id].parsed_template = parsed
        self._log_audit(job_id, "parse", "Template parsed", data={"total_input_cells": parsed["total_input_cells"]})
        await ws_callback(WSEvent(job_id=job_id, phase="parse", event_type="progress", detail=f"Found {parsed['total_input_cells']} input cells across {len(parsed['sheets'])} sheets"))
        for sheet in parsed['sheets']:
            await ws_callback(WSEvent(job_id=job_id, phase="parse", event_type="progress", detail=f"[MAP] {sheet['name']} -> {len(sheet['input_cells'])} input cells"))

        # 2. Schema Extraction Phase
        self._update_status(job_id, "extracting_schema")
        await ws_callback(WSEvent(job_id=job_id, phase="schema_extract", event_type="progress", detail="Schema extraction starting..."))
        
        async def schema_progress(msg):
            await ws_callback(WSEvent(job_id=job_id, phase="schema_extract", event_type="progress", detail=msg))

        schema = await extract_schema(parsed, self.settings, on_progress=schema_progress)
        self.jobs[job_id].template_schema = schema
        self._log_audit(job_id, "schema_extract", "Schema extracted successfully", agent=self.settings.gemini_fast_model)

        cost_entry = cost_tracker.log_cost("schema_extractor", self.settings.gemini_fast_model, {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500})
        self.jobs[job_id].cost_entries.append(cost_entry)
        
        await ws_callback(WSEvent(job_id=job_id, phase="schema_extract", event_type="progress", detail=f"[TYPE] Model classified as: {schema.model_type}"))
        for ref in schema.inter_sheet_refs:
            await ws_callback(WSEvent(job_id=job_id, phase="schema_extract", event_type="progress", detail=f"[LINK] {ref.source_sheet}.{ref.source_column} -> {ref.target_sheet}.{ref.target_column} ✓"))

        # 3. Generation & Validation Loop
        self._update_status(job_id, "generating")
        retry_instructions = None
        
        for attempt in range(self.settings.max_retries):
            # Generate
            await ws_callback(WSEvent(job_id=job_id, phase="generate", event_type="progress", detail="Synthetic generation starting (sheet-by-sheet)..."))
            payload = await generate_synthetic_data(schema, self.settings, retry_instructions, parsed_template=parsed)

            # Post-process: fix rolling balances, sign conventions, zero fills
            raw_cells = [c.model_dump() for c in payload.cells]
            fixed_cells = post_process(raw_cells, parsed)
            from backend.models.schemas import CellValue
            payload.cells = [CellValue(**c) for c in fixed_cells]

            self.jobs[job_id].synthetic_payload = payload
            self._log_audit(job_id, "generate", f"Generated synthetic payload (attempt {attempt+1})", agent=self.settings.gemini_model)

            gen_cost = cost_tracker.log_cost("synthetic_gen", self.settings.gemini_model, payload.generation_metadata.token_usage)
            self.jobs[job_id].cost_entries.append(gen_cost)
            
            for cell in payload.cells:
                await ws_callback(WSEvent(
                    job_id=job_id, phase="generate", event_type="cell_update",
                    detail=f"{cell.sheet_name}.{cell.header} [{cell.period}] = {cell.value}",
                    data={"sheet": cell.sheet_name, "cell_ref": cell.cell_ref, "value": cell.value}
                ))
            
            # Validate
            self._update_status(job_id, "validating")
            validator = DeterministicValidator(schema)
            result = validator.validate(payload)
            self.jobs[job_id].validation_result = result
            
            for rule in result.rules:
                if rule.passed:
                    await ws_callback(WSEvent(job_id=job_id, phase="validate", event_type="validation", detail=f"✓ {rule.rule_name} ({rule.period})"))
            
            for adj in result.adjustments:
                await ws_callback(WSEvent(job_id=job_id, phase="validate", event_type="validation", detail=f"⚡ Adjusted {adj.target_cell} by {adj.delta:+,.0f} to force {adj.reason}"))
            
            if result.status == "FAILED":
                if attempt < self.settings.max_retries - 1:
                    retry_instructions = validator.build_retry_instructions()
                    self.jobs[job_id].retry_count += 1
                    self._log_audit(job_id, "validate", f"Validation failed, retrying. {retry_instructions}", agent="DeterministicValidator")
                    await ws_callback(WSEvent(job_id=job_id, phase="validate", event_type="progress", detail=f"Retrying generation (attempt {attempt+2})..."))
                    self._update_status(job_id, "generating")
                    continue
                else:
                    raise Exception("Validation failed after maximum retries")
            
            # Passed
            self._log_audit(job_id, "validate", "Validation passed", agent="DeterministicValidator", data={"status": result.status})
            
            # 4. Write Phase
            self._update_status(job_id, "writing")
            output_path = f"/tmp/safe_harbor/{job_id}/output.xlsx"
            import os
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            final_payload = result.validated_payload if result.validated_payload else payload
            await asyncio.to_thread(write_synthetic_data, file_path, final_payload, output_path)

            # Two-pass BS balance plug: evaluate formulas, compute imbalance, write correction
            await asyncio.to_thread(balance_bs, output_path, parsed)

            self.jobs[job_id].output_file_path = output_path
            self._update_status(job_id, "complete")
            self._log_audit(job_id, "write", "Output file generated successfully")
            
            await ws_callback(WSEvent(job_id=job_id, phase="write", event_type="complete", detail="Success", data=result.model_dump()))
            break
