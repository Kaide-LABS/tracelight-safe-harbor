import os
import uuid
import json
import asyncio
import logging
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from backend.config import get_settings
from backend.orchestrator import PipelineOrchestrator
from backend.models.schemas import JobState
from backend.middleware.logging_middleware import StructuredLoggingMiddleware
from backend.health import router as health_router

from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()
app.include_router(health_router)
app.add_middleware(StructuredLoggingMiddleware)

app.mount("/templates", StaticFiles(directory="templates"), name="templates")
settings = get_settings()

allowed_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    os.getenv("FRONTEND_ORIGIN", ""),
]
allowed_origins = [o for o in allowed_origins if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = PipelineOrchestrator(settings)


def _get_google_creds(sa_path: str):
    """Load OAuth user credentials (preferred) or fall back to service account."""
    import os
    token_path = os.path.join(os.path.dirname(sa_path), 'oauth_token.json')
    if os.path.exists(token_path):
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(token_path)
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            # Save refreshed token
            import json
            with open(token_path, 'w') as f:
                json.dump({
                    'token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                    'scopes': list(creds.scopes or []),
                }, f)
        return creds
    else:
        from google.oauth2 import service_account
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        return service_account.Credentials.from_service_account_file(sa_path, scopes=SCOPES)


def _create_sheet_from_xlsx(xlsx_path: str, title: str, sa_path: str, add_validation: bool = False) -> dict:
    """Read xlsx with openpyxl, create Google Sheet via Sheets API, write all data."""
    import openpyxl
    from googleapiclient.discovery import build

    creds = _get_google_creds(sa_path)
    sheets_svc = build('sheets', 'v4', credentials=creds)
    drive_svc = build('drive', 'v3', credentials=creds)

    # Read xlsx
    wb = openpyxl.load_workbook(xlsx_path, data_only=False)

    # Create spreadsheet with correct sheet names
    sheet_props = [{"properties": {"title": ws.title}} for ws in wb.worksheets]
    body = {"properties": {"title": title}, "sheets": sheet_props}
    spreadsheet = sheets_svc.spreadsheets().create(body=body, fields='spreadsheetId').execute()
    spreadsheet_id = spreadsheet['spreadsheetId']

    # Write data sheet by sheet
    data = []
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=ws.max_column):
            row_data = []
            for cell in row:
                val = cell.value
                if val is None:
                    row_data.append({"userEnteredValue": {"stringValue": ""}})
                elif isinstance(val, str) and val.startswith("="):
                    row_data.append({"userEnteredValue": {"formulaValue": val}})
                elif isinstance(val, bool):
                    row_data.append({"userEnteredValue": {"boolValue": val}})
                elif isinstance(val, (int, float)):
                    row_data.append({"userEnteredValue": {"numberValue": val}})
                else:
                    row_data.append({"userEnteredValue": {"stringValue": str(val)}})
            rows.append({"values": row_data})

        # Find the sheet ID
        sheet_meta = sheets_svc.spreadsheets().get(
            spreadsheetId=spreadsheet_id, fields='sheets.properties'
        ).execute()
        sheet_id = None
        for s in sheet_meta['sheets']:
            if s['properties']['title'] == ws.title:
                sheet_id = s['properties']['sheetId']
                break

        if sheet_id is not None:
            data.append({
                "updateCells": {
                    "rows": rows,
                    "fields": "userEnteredValue",
                    "start": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 0},
                }
            })

    if data:
        sheets_svc.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": data},
        ).execute()

    # Add Validation sheet with live formulas (only for generated output, not templates)
    if add_validation:
        _add_validation_sheet(sheets_svc, spreadsheet_id, wb)

    # Make publicly viewable
    drive_svc.permissions().create(
        fileId=spreadsheet_id,
        body={'type': 'anyone', 'role': 'reader'},
    ).execute()

    embed_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit?embedded=true&rm=minimal"
    view_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"

    return {"embed_url": embed_url, "view_url": view_url, "sheet_id": spreadsheet_id}


def _add_validation_sheet(sheets_svc, spreadsheet_id: str, wb):
    """Add a 'Validation' sheet with live formulas proving data integrity."""
    import re

    # Check which sheets exist
    sheet_names = [ws.title for ws in wb.worksheets]
    has_is = 'Income Statement' in sheet_names
    has_bs = 'Balance Sheet' in sheet_names
    has_cf = 'Cash Flow Statement' in sheet_names
    has_ds = 'Debt Schedule' in sheet_names
    has_ra = 'Returns Analysis' in sheet_names

    # Detect periods from row 2 of Income Statement (or row 1)
    periods = []
    if has_is:
        ws = wb['Income Statement']
        for col in range(2, ws.max_column + 1):
            for r in [2, 1]:
                val = ws.cell(row=r, column=col).value
                if val and re.search(r'(FY|CY)?\d{4}', str(val)):
                    periods.append({"col_letter": chr(64 + col), "label": str(val).strip()})
                    break
    if not periods:
        return  # Can't build validation without periods

    cols = [p["col_letter"] for p in periods]

    # Add the validation sheet
    sheets_svc.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": "✓ Validation"}}}]},
    ).execute()

    # Build validation rows
    rows = []

    def _header(text):
        return [{"userEnteredValue": {"stringValue": text}, "userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 11}}}]

    def _label(text):
        return [{"userEnteredValue": {"stringValue": text}}]

    def _formula_row(label, formulas):
        """Row with label in A, formulas in B onwards."""
        r = [{"userEnteredValue": {"stringValue": label}}]
        for f in formulas:
            r.append({"userEnteredValue": {"formulaValue": f}})
        return r

    def _status_row(label, check_formulas):
        """Row with label in A, PASS/FAIL checks in B onwards."""
        r = [{"userEnteredValue": {"stringValue": label}}]
        for f in check_formulas:
            r.append({"userEnteredValue": {"formulaValue": f}})
        return r

    # Title
    rows.append({"values": _header("SAFE-HARBOR VALIDATION REPORT")})
    rows.append({"values": _label("All checks are live Google Sheets formulas — click any cell to verify.")})
    rows.append({"values": []})  # blank

    # Period headers row
    period_row = [{"userEnteredValue": {"stringValue": ""}}]
    for p in periods:
        period_row.append({"userEnteredValue": {"stringValue": p["label"]}, "userEnteredFormat": {"textFormat": {"bold": True}}})
    rows.append({"values": period_row})

    # ── Section 1: Balance Sheet Identity ──
    rows.append({"values": []})
    rows.append({"values": _header("1. BALANCE SHEET IDENTITY (Assets = Liabilities + Equity)")})
    if has_bs:
        rows.append({"values": _formula_row("Total Assets", [f"='Balance Sheet'!{c}20" for c in cols])})
        rows.append({"values": _formula_row("Total Liabilities", [f"='Balance Sheet'!{c}36" for c in cols])})
        rows.append({"values": _formula_row("Total Equity", [f"='Balance Sheet'!{c}42" for c in cols])})
        rows.append({"values": _formula_row("Δ (Assets - L - E)", [f"='Balance Sheet'!{c}20-('Balance Sheet'!{c}36+'Balance Sheet'!{c}42)" for c in cols])})
        rows.append({"values": _status_row("✓ Status", [f'=IF(ABS(\'Balance Sheet\'!{c}20-(\'Balance Sheet\'!{c}36+\'Balance Sheet\'!{c}42))<1,"PASS","FAIL")' for c in cols])})

    # ── Section 2: Gross Margin ──
    rows.append({"values": []})
    rows.append({"values": _header("2. MARGIN ANALYSIS")})
    if has_is:
        rows.append({"values": _formula_row("Revenue", [f"='Income Statement'!{c}4" for c in cols])})
        rows.append({"values": _formula_row("Gross Profit", [f"='Income Statement'!{c}6" for c in cols])})
        rows.append({"values": _formula_row("Gross Margin %", [f"='Income Statement'!{c}6/'Income Statement'!{c}4" for c in cols])})
        rows.append({"values": _formula_row("EBITDA", [f"='Income Statement'!{c}14" for c in cols])})
        rows.append({"values": _formula_row("EBITDA Margin %", [f"='Income Statement'!{c}14/'Income Statement'!{c}4" for c in cols])})
        rows.append({"values": _formula_row("Net Income", [f"='Income Statement'!{c}29" for c in cols])})
        rows.append({"values": _formula_row("Net Margin %", [f"='Income Statement'!{c}29/'Income Statement'!{c}4" for c in cols])})
        rows.append({"values": _status_row("✓ Margins in range", [f'=IF(AND(\'Income Statement\'!{c}6/\'Income Statement\'!{c}4>0,\'Income Statement\'!{c}6/\'Income Statement\'!{c}4<1),"PASS","FAIL")' for c in cols])})

    # ── Section 3: Revenue Growth ──
    rows.append({"values": []})
    rows.append({"values": _header("3. REVENUE GROWTH RATE")})
    if has_is and len(cols) > 1:
        growth_formulas = [""] + [f"='Income Statement'!{cols[i]}4/'Income Statement'!{cols[i-1]}4-1" for i in range(1, len(cols))]
        rows.append({"values": _formula_row("YoY Growth %", growth_formulas)})
        rows.append({"values": _formula_row("Avg Growth", ["", f"=AVERAGE({cols[1]}{'len(rows)'}:{cols[-1]}{'len(rows)'})" if len(cols) > 2 else ""])})

    # ── Section 4: Cash Flow Reconciliation ──
    rows.append({"values": []})
    rows.append({"values": _header("4. CASH FLOW RECONCILIATION")})
    if has_cf:
        rows.append({"values": _formula_row("Beginning Cash", [f"='Cash Flow Statement'!{c}31" for c in cols])})
        rows.append({"values": _formula_row("Net Change in Cash", [f"='Cash Flow Statement'!{c}30" for c in cols])})
        rows.append({"values": _formula_row("Ending Cash", [f"='Cash Flow Statement'!{c}32" for c in cols])})
        rows.append({"values": _formula_row("Δ (End - Begin - Net)", [f"='Cash Flow Statement'!{c}32-'Cash Flow Statement'!{c}31-'Cash Flow Statement'!{c}30" for c in cols])})
        rows.append({"values": _status_row("✓ Status", [f'=IF(ABS(\'Cash Flow Statement\'!{c}32-\'Cash Flow Statement\'!{c}31-\'Cash Flow Statement\'!{c}30)<1,"PASS","FAIL")' for c in cols])})

    # ── Section 5: Debt Schedule Rollforward ──
    rows.append({"values": []})
    rows.append({"values": _header("5. DEBT SCHEDULE — SENIOR SECURED")})
    if has_ds:
        rows.append({"values": _formula_row("Beginning Balance", [f"='Debt Schedule'!{c}5" for c in cols])})
        rows.append({"values": _formula_row("+ Drawdowns", [f"='Debt Schedule'!{c}6" for c in cols])})
        rows.append({"values": _formula_row("- Repayments", [f"='Debt Schedule'!{c}7" for c in cols])})
        rows.append({"values": _formula_row("= Ending Balance", [f"='Debt Schedule'!{c}9" for c in cols])})
        rows.append({"values": _formula_row("Δ (End - Begin - Draw + Repay)", [f"='Debt Schedule'!{c}9-('Debt Schedule'!{c}5+'Debt Schedule'!{c}6+'Debt Schedule'!{c}7)" for c in cols])})
        rows.append({"values": _status_row("✓ Status", [f'=IF(ABS(\'Debt Schedule\'!{c}9-(\'Debt Schedule\'!{c}5+\'Debt Schedule\'!{c}6+\'Debt Schedule\'!{c}7))<1,"PASS","FAIL")' for c in cols])})

    # ── Section 6: Cross-Sheet Linkage ──
    rows.append({"values": []})
    rows.append({"values": _header("6. CROSS-SHEET LINKAGE")})
    if has_is and has_cf:
        rows.append({"values": _formula_row("IS: D&A", [f"='Income Statement'!{c}17" for c in cols])})
        rows.append({"values": _formula_row("CF: D&A Add-back", [f"='Cash Flow Statement'!{c}6" for c in cols])})
        rows.append({"values": _formula_row("Δ (IS D&A - CF D&A)", [f"=ABS('Income Statement'!{c}17)-ABS('Cash Flow Statement'!{c}6)" for c in cols])})
        rows.append({"values": _status_row("✓ D&A Linkage", [f'=IF(ABS(ABS(\'Income Statement\'!{c}17)-ABS(\'Cash Flow Statement\'!{c}6))<1,"PASS","FAIL")' for c in cols])})
    if has_is and has_ds:
        rows.append({"values": _formula_row("IS: Total Interest", [f"='Income Statement'!{c}23" for c in cols])})
        rows.append({"values": _formula_row("DS: Total Interest", [f"='Debt Schedule'!{c}27" for c in cols])})
        rows.append({"values": _status_row("✓ Interest Linkage", [f'=IF(ABS(ABS(\'Income Statement\'!{c}23)-ABS(\'Debt Schedule\'!{c}27))<1,"PASS","FAIL")' for c in cols])})

    # ── Section 7: Statistical Summary ──
    rows.append({"values": []})
    rows.append({"values": _header("7. STATISTICAL DISTRIBUTION")})
    if has_is:
        rev_range = f"'Income Statement'!{cols[0]}4:{cols[-1]}4"
        margin_range = f"'Income Statement'!{cols[0]}7:{cols[-1]}7"
        rows.append({"values": [
            {"userEnteredValue": {"stringValue": "Revenue"}},
            {"userEnteredValue": {"stringValue": "Mean"}},
            {"userEnteredValue": {"formulaValue": f"=AVERAGE({rev_range})"}},
            {"userEnteredValue": {"stringValue": "Std Dev"}},
            {"userEnteredValue": {"formulaValue": f"=STDEV({rev_range})"}},
            {"userEnteredValue": {"stringValue": "CV"}},
            {"userEnteredValue": {"formulaValue": f"=STDEV({rev_range})/AVERAGE({rev_range})"}},
        ]})
        rows.append({"values": [
            {"userEnteredValue": {"stringValue": "Gross Margin"}},
            {"userEnteredValue": {"stringValue": "Mean"}},
            {"userEnteredValue": {"formulaValue": f"=AVERAGE({margin_range})"}},
            {"userEnteredValue": {"stringValue": "Min"}},
            {"userEnteredValue": {"formulaValue": f"=MIN({margin_range})"}},
            {"userEnteredValue": {"stringValue": "Max"}},
            {"userEnteredValue": {"formulaValue": f"=MAX({margin_range})"}},
        ]})

    # ── Section 8: Leverage Ratios ──
    rows.append({"values": []})
    rows.append({"values": _header("8. LEVERAGE & COVERAGE RATIOS")})
    if has_ds and has_is:
        rows.append({"values": _formula_row("Total Debt (Senior End)", [f"='Debt Schedule'!{c}9" for c in cols])})
        rows.append({"values": _formula_row("Debt / EBITDA", [f"=IF('Income Statement'!{c}14<>0,'Debt Schedule'!{c}9/'Income Statement'!{c}14,\"N/A\")" for c in cols])})
        rows.append({"values": _formula_row("Interest Coverage (EBIT/Interest)", [f"=IF('Income Statement'!{c}23<>0,'Income Statement'!{c}18/ABS('Income Statement'!{c}23),\"N/A\")" for c in cols])})

    # Write the validation sheet
    sheet_meta = sheets_svc.spreadsheets().get(
        spreadsheetId=spreadsheet_id, fields='sheets.properties'
    ).execute()
    val_sheet_id = None
    for s in sheet_meta['sheets']:
        if s['properties']['title'] == '✓ Validation':
            val_sheet_id = s['properties']['sheetId']
            break

    if val_sheet_id is not None and rows:
        sheets_svc.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{
                "updateCells": {
                    "rows": rows,
                    "fields": "userEnteredValue,userEnteredFormat",
                    "start": {"sheetId": val_sheet_id, "rowIndex": 0, "columnIndex": 0},
                }
            }]},
        ).execute()


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
        logger.info(f"Client disconnected for job {job_id}")
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

@app.post("/api/sheets/template/{filename}")
async def create_template_sheet(filename: str):
    """Create a Google Sheet from a template xlsx via Sheets API."""
    file_path = f"templates/{filename}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Template not found")

    settings = get_settings()
    sa_path = settings.google_service_account_path
    if not os.path.exists(sa_path):
        raise HTTPException(status_code=500, detail="Google service account not configured")

    try:
        return await asyncio.to_thread(_create_sheet_from_xlsx, file_path, f"Template_{filename}", sa_path)
    except Exception as e:
        logger.error(f"Template Sheets creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/preview/{filename}")
async def preview_template(filename: str):
    import os
    file_path = f"templates/{filename}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Template not found")
    from backend.excel_io.parser import parse_template
    parsed = parse_template(file_path)
    return parsed

@app.post("/api/sheets/{job_id}")
async def create_google_sheet(job_id: str):
    """Create a Google Sheet from the output xlsx via Sheets API (no Drive upload)."""
    if job_id not in orchestrator.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = orchestrator.jobs[job_id]
    if job.status != "complete" or not job.output_file_path:
        raise HTTPException(status_code=400, detail="Job not complete")

    settings = get_settings()
    sa_path = settings.google_service_account_path
    if not os.path.exists(sa_path):
        raise HTTPException(status_code=500, detail="Google service account not configured")

    try:
        return await asyncio.to_thread(_create_sheet_from_xlsx, job.output_file_path, f"SafeHarbor_{job_id[:8]}", sa_path, True)
    except Exception as e:
        logger.error(f"Google Sheets creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Google Sheets creation failed: {str(e)}")


@app.get("/api/spreadsheet/{job_id}")
async def get_spreadsheet_data(job_id: str):
    """Return the output xlsx with computed formula values."""
    if job_id not in orchestrator.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = orchestrator.jobs[job_id]
    if job.status != "complete" or not job.output_file_path:
        raise HTTPException(status_code=400, detail="Job not complete")

    import openpyxl

    # Evaluate formulas using the formulas library
    computed_values = {}
    try:
        import formulas
        xl_model = formulas.ExcelModel().loads(job.output_file_path).finish()
        solution = xl_model.calculate()
        for key, val in solution.items():
            # key is like "'Income Statement'!B6"
            import numpy as np
            v = val
            if hasattr(v, 'tolist'):
                v = v.tolist()
            if isinstance(v, (list,)):
                v = v[0] if len(v) == 1 else v
            if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
                v = None
            computed_values[str(key).upper()] = v
    except Exception as e:
        logger.warning(f"Formula evaluation failed: {e}")

    wb = openpyxl.load_workbook(job.output_file_path, data_only=False)
    sheets = []
    for ws in wb.worksheets:
        cells = {}
        max_row = ws.max_row or 1
        max_col = ws.max_column or 1
        for row in range(1, max_row + 1):
            for col in range(1, max_col + 1):
                cell = ws.cell(row=row, column=col)
                val = cell.value
                if val is not None:
                    coord = cell.coordinate
                    is_formula = isinstance(val, str) and val.startswith("=")

                    # Try to get computed value for formula cells
                    computed = None
                    if is_formula:
                        lookup = f"'{ws.title}'!{coord}".upper()
                        computed = computed_values.get(lookup)
                        if computed is None:
                            # Try without quotes
                            lookup2 = f"{ws.title}!{coord}".upper()
                            computed = computed_values.get(lookup2)

                    cells[coord] = {
                        "v": computed if is_formula else val,
                        "f": val if is_formula else None,
                        "r": row,
                        "c": col,
                    }
        sheets.append({
            "name": ws.title,
            "maxRow": max_row,
            "maxCol": max_col,
            "cells": cells,
        })
    return {"sheets": sheets}


@app.get("/api/costs/{job_id}")
async def get_costs(job_id: str):
    if job_id not in orchestrator.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = orchestrator.jobs[job_id]
    entries = getattr(job, "cost_entries", [])
    total_cost = sum(e.estimated_cost_usd for e in entries)
    return {
        "job_id": job_id,
        "entries": [e.model_dump() for e in entries],
        "total_cost_usd": total_cost
    }
