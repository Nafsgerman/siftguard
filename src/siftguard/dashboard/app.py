from __future__ import annotations
import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, Response
import io
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="SIFTGuard Dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_sessions: dict[str, list[dict]] = {}
_queues: dict[str, asyncio.Queue] = {}
_stream_gen: dict[str, str] = {}

def get_or_create_session(session_id: str):
    if session_id not in _sessions:
        _sessions[session_id] = []
        _queues[session_id] = asyncio.Queue()
    return _sessions[session_id], _queues[session_id]

async def push_event(session_id: str, event: dict) -> None:
    events, queue = get_or_create_session(session_id)
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    events.append(event)
    await queue.put(event)

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path) as f:
        return HTMLResponse(f.read())

@app.get("/api/stream/{session_id}")
async def stream(session_id: str, request: Request):
    gen_id = str(uuid.uuid4())
    _stream_gen[session_id] = gen_id
    fresh_queue: asyncio.Queue = asyncio.Queue()
    _queues[session_id] = fresh_queue
    async def event_generator() -> AsyncGenerator[str, None]:
        queue = fresh_queue
        get_or_create_session(session_id)
        for event in _sessions.get(session_id, []):
            if _stream_gen.get(session_id) != gen_id:
                return
            yield f"data: {json.dumps(event)}\n\n"
        while True:
            if _stream_gen.get(session_id) != gen_id:
                return
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.post("/api/investigate")
async def start_investigation(request: Request):
    body = await request.json()
    session_id = str(uuid.uuid4())[:8]
    case_id = body.get("case_id", f"CASE-{session_id}")
    briefing = body.get("briefing", "")
    memory_image = body.get("memory_image", "")
    training_mode = body.get("training_mode", False)
    asyncio.create_task(_run_investigation(session_id, case_id, briefing, memory_image, training_mode))
    return {"session_id": session_id, "case_id": case_id}

async def _run_investigation(session_id: str, case_id: str, briefing: str, memory_image: str, training_mode: bool = False):
    from siftguard.agent.loop import SYSTEM_PROMPT, TRAINING_SYSTEM_PROMPT, TOOL_SCHEMAS, _dispatch_tool
    from siftguard.audit.log import AuditLog
    import anthropic

    await push_event(session_id, {"type": "start", "case_id": case_id, "briefing": briefing})
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    evidence = {"memory_image": memory_image} if memory_image else {}
    active_prompt = TRAINING_SYSTEM_PROMPT if training_mode else SYSTEM_PROMPT
    audit = AuditLog(f"./audit/{case_id}.db")
    evidence_summary = "\n".join(f"- {k}: {v}" for k, v in evidence.items())
    messages = [{"role": "user", "content": (
        f"## Case ID: {case_id}\n\n## Briefing\n{briefing}\n\n"
        f"## Available Evidence\n{evidence_summary}\n\nBegin your investigation."
    )}]
    max_iterations = int(os.environ.get("SIFTGUARD_MAX_AGENT_ITERATIONS", "15"))

    for iteration in range(max_iterations):
        await push_event(session_id, {"type": "iteration", "iteration": iteration + 1, "max": max_iterations})
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=4096,
            system=active_prompt,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )
        assistant_content = []
        tool_calls = []
        for block in response.content:
            assistant_content.append(block)
            if block.type == "text" and block.text.strip():
                await push_event(session_id, {"type": "agent_text", "text": block.text})
                if "## Executive Summary" in block.text:
                    await push_event(session_id, {"type": "report", "content": block.text})
                if training_mode and "[TRAINING]" in block.text:
                    for line in block.text.split("\n"):
                        if "[TRAINING]" in line:
                            annotation = line.replace("[TRAINING]", "").strip()
                            if annotation:
                                await push_event(session_id, {"type": "training_annotation", "text": annotation})
            elif block.type == "tool_use":
                tool_calls.append(block)
                await push_event(session_id, {"type": "tool_call", "tool": block.name, "args": block.input})
        messages.append({"role": "assistant", "content": assistant_content})
        if response.stop_reason == "end_turn" and not tool_calls:
            break
        if tool_calls:
            tool_results = []
            for tc in tool_calls:
                result = await _dispatch_tool(tc.name, tc.input)
                audit.record(case_id=case_id, tool_name=tc.name, tool_version="1.0.0",
                    args=tc.input, outcome=result.outcome.value, output=result.model_dump_json(),
                    duration_ms=result.duration_ms, agent_iteration=iteration)
                await push_event(session_id, {
                    "type": "tool_result", "tool": tc.name, "outcome": result.outcome.value,
                    "summary": result.summary, "duration_ms": result.duration_ms,
                    "findings_count": len(result.findings),
                })
                tool_results.append({"type": "tool_result", "tool_use_id": tc.id,
                    "content": result.model_dump_json()[:8000]})
            messages.append({"role": "user", "content": tool_results})

    await push_event(session_id, {"type": "complete"})

@app.get("/api/export/pdf/{session_id}")
async def export_pdf(session_id: str):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_LEFT, TA_CENTER

    events = _sessions.get(session_id, [])
    if not events:
        return Response(status_code=404)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)

    styles = getSampleStyleSheet()
    BLUE = colors.HexColor("#1a73e8")
    DARK = colors.HexColor("#202124")
    GRAY = colors.HexColor("#5f6368")
    RED  = colors.HexColor("#d93025")
    GREEN = colors.HexColor("#1e8e3e")

    h1 = ParagraphStyle("h1", parent=styles["Normal"], fontSize=22, textColor=BLUE,
        spaceAfter=4, fontName="Helvetica-Bold")
    h2 = ParagraphStyle("h2", parent=styles["Normal"], fontSize=13, textColor=DARK,
        spaceBefore=10, spaceAfter=4, fontName="Helvetica-Bold")
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9, textColor=DARK,
        leading=14, spaceAfter=3)
    meta = ParagraphStyle("meta", parent=styles["Normal"], fontSize=8, textColor=GRAY, spaceAfter=2)
    code = ParagraphStyle("code", parent=styles["Normal"], fontSize=8, textColor=DARK,
        fontName="Courier", backColor=colors.HexColor("#f8f9fa"), leading=12,
        leftIndent=6, spaceAfter=2)

    story = []

    # Header
    case_id = next((e["case_id"] for e in events if e.get("case_id")), session_id)
    briefing = next((e.get("briefing","") for e in events if e.get("type") == "start"), "")
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    story.append(Paragraph("SIFTGuard DFIR Report", h1))
    story.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=6))
    story.append(Paragraph(f"Case ID: <b>{case_id}</b>", meta))
    story.append(Paragraph(f"Generated: {generated_at}", meta))
    story.append(Paragraph(f"Session: {session_id}", meta))
    story.append(Spacer(1, 6*mm))

    if briefing:
        story.append(Paragraph("Briefing", h2))
        story.append(Paragraph(briefing.replace("\n","<br/>"), body))
        story.append(Spacer(1, 4*mm))

    # Executive report blocks
    report_blocks = [e["content"] for e in events if e.get("type") == "report"]
    if report_blocks:
        story.append(Paragraph("Investigation Report", h2))
        story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY, spaceAfter=4))
        for block in report_blocks:
            for line in block.split("\n"):
                line = line.strip()
                if not line:
                    story.append(Spacer(1, 2*mm))
                elif line.startswith("## "):
                    story.append(Paragraph(line[3:], h2))
                elif line.startswith("# "):
                    story.append(Paragraph(line[2:], h1))
                elif line.startswith("- ") or line.startswith("* "):
                    story.append(Paragraph(f"• {line[2:]}", body))
                else:
                    story.append(Paragraph(line, body))

    # Tool execution summary table
    tool_events = [e for e in events if e.get("type") == "tool_result"]
    if tool_events:
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph("Tool Execution Log", h2))
        story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY, spaceAfter=4))
        table_data = [["Tool", "Outcome", "Findings", "Duration", "Summary"]]
        for e in tool_events:
            outcome = e.get("outcome", "")
            outcome_color = GREEN if outcome == "ok" else (RED if outcome == "fail" else GRAY)
            table_data.append([
                e.get("tool","")[:30],
                outcome.upper(),
                str(e.get("findings_count", 0)),
                f"{e.get('duration_ms',0)}ms",
                (e.get("summary","")[:60] + "…") if len(e.get("summary","")) > 60 else e.get("summary",""),
            ])
        t = Table(table_data, colWidths=[40*mm, 20*mm, 18*mm, 20*mm, None])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), BLUE),
            ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
            ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",   (0,0), (-1,-1), 8),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8f9fa")]),
            ("GRID",       (0,0), (-1,-1), 0.25, colors.HexColor("#dadce0")),
            ("LEFTPADDING",(0,0), (-1,-1), 4),
            ("RIGHTPADDING",(0,0), (-1,-1), 4),
            ("TOPPADDING", (0,0), (-1,-1), 3),
            ("BOTTOMPADDING",(0,0), (-1,-1), 3),
            ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ]))
        story.append(t)

    # Footer
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY))
    story.append(Paragraph(
        "Generated by SIFTGuard — Autonomous DFIR Agent | SANS SIFT Workstation | "
        "Evidence integrity guaranteed by architectural spoliation prevention.",
        ParagraphStyle("footer", parent=meta, alignment=TA_CENTER)
    ))

    doc.build(story)
    buf.seek(0)
    filename = f"siftguard-{case_id}-{session_id}.pdf"
    return Response(
        content=buf.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
