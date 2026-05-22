from __future__ import annotations

import asyncio
import contextlib
import io
import json
import os
import pathlib
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse

from siftguard.cases.loader import get_case, list_case_ids

load_dotenv(Path(__file__).resolve().parents[4] / ".env")


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
    event["timestamp"] = datetime.now(UTC).isoformat()
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
            except TimeoutError:
                yield ": keepalive\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/investigate")
async def start_investigation(request: Request):
    body = await request.json()
    session_id = str(uuid.uuid4())[:8]
    case_id = body.get("case_id", f"CASE-{session_id}")
    briefing = body.get("briefing", "")
    memory_image = body.get("memory_image", "")
    training_mode = body.get("training_mode", False)
    orchestrator = body.get("orchestrator", "native")
    self_correction = body.get("self_correction", True)
    asyncio.create_task(
        _run_investigation(
            session_id,
            case_id,
            briefing,
            memory_image,
            training_mode,
            orchestrator,
            self_correction,
        )
    )
    # Store orchestrator label for PDF export
    await push_event(
        session_id,
        {"type": "meta", "orchestrator": orchestrator, "self_correction": self_correction},
    )
    return {"session_id": session_id, "case_id": case_id}


async def _run_investigation(
    session_id: str,
    case_id: str,
    briefing: str,
    memory_image: str,
    training_mode: bool = False,
    orchestrator: str = "native",
    self_correction: bool = True,
):
    if orchestrator == "openai-fc":
        from siftguard.orchestrators.openai_fc_adapter import run_case_openai_fc as run_case
    elif orchestrator == "langgraph":
        from siftguard.orchestrators.langgraph_adapter import run_case_langgraph as run_case
    elif orchestrator == "gemini":
        from siftguard.orchestrators.gemini_adapter import run_case_gemini as run_case
    elif orchestrator == "haiku":
        from siftguard.agent.loop import run_case as _run_native

        async def run_case(*args, **kwargs):
            kwargs["model"] = "claude-haiku-4-5"
            return await _run_native(*args, **kwargs)
    elif orchestrator == "claudecode":
        from siftguard.eval.orchestrators.claude_code_adapter import ClaudeCodeAdapter

        _cc = ClaudeCodeAdapter()

        async def run_case(*args, **kwargs):
            _on_event = kwargs.get("on_event")
            if _on_event:
                _on_event("investigation_started", {"case_id": case_id, "briefing": briefing})
            result = await asyncio.get_running_loop().run_in_executor(
                None, lambda: _cc.run(case_id, briefing)
            )
            if _on_event:
                if result.success:
                    _on_event(
                        "verdict_reached", {"verdict": result.report.get("verdict", "unknown")}
                    )
                else:
                    _on_event("verdict_reached", {"verdict": "error", "error": result.error})
            return result.report
    else:
        from siftguard.agent.loop import run_case

    evidence = {"memory_image": memory_image} if memory_image else {}
    audit_db = os.path.join(os.path.dirname(__file__), "..", "..", "..", "audit", f"{case_id}.db")

    _EVENT_MAP = {
        "iteration_complete": "iteration",
        "tool_call_start": "tool_call",
        "tool_call_end": "tool_result",
        "investigation_started": "start",
        "verdict_reached": "complete",
        "ioc_detected": "ioc",
        "hypothesis_update": "hypothesis",
    }
    _main_loop = asyncio.get_running_loop()

    def on_event(event_type: str, data: dict):
        mapped = _EVENT_MAP.get(event_type, event_type)
        # Rename 'type' key in data → 'ioc_type' to avoid overwriting the SSE event type
        safe_data = {
            ("ioc_type" if k == "type" and mapped == "ioc" else k): v for k, v in data.items()
        }
        with contextlib.suppress(Exception):
            _main_loop.call_soon_threadsafe(
                lambda: _main_loop.create_task(
                    push_event(session_id, {"type": mapped, **safe_data})
                )
            )

    try:
        run_kwargs: dict = dict(
            case_id=case_id,
            evidence_files=evidence,
            briefing=briefing,
            audit_db=audit_db,
            training_mode=training_mode,
            on_event=on_event,
        )
        # config_override is accepted by the typed v2 adapters only.
        # Native/haiku route to v1 loop; claudecode is a subprocess wrapper.
        if orchestrator in ("openai-fc", "langgraph", "gemini"):
            run_kwargs["config_override"] = {"self_correction": self_correction}
        report = await run_case(**run_kwargs)
        # v2 adapters return (report_str, run_id) — unwrap
        if isinstance(report, tuple):
            report = report[0]
        print(
            f"[POST-RUN] orch={orchestrator} report_type={type(report).__name__} report_len={len(report) if report else 0}",
            flush=True,
        )
        if report:
            # Universal IOC extraction — works for every orchestrator that returns a report dict
            report_dict = report if isinstance(report, dict) else None
            if not report_dict and isinstance(report, str):
                import re as _re_ioc

                m = _re_ioc.search(
                    r"```(?:siftguard-report|json)?\s*\n(\{.*?\})\n```", report, _re_ioc.DOTALL
                )
                if m:
                    try:
                        report_dict = json.loads(m.group(1))
                    except Exception:
                        report_dict = None
            if report_dict:
                _IOC_TYPE_MAP = {
                    "process": "process",
                    "network": "ip",
                    "ip": "ip",
                    "file": "file",
                    "registry": "registry",
                    "hash": "hash",
                }
                for ioc in (report_dict.get("confirmed_iocs") or []) + (
                    report_dict.get("suspicious_indicators") or []
                ):
                    on_event(
                        "ioc_detected",
                        {
                            "ioc_type": _IOC_TYPE_MAP.get(ioc.get("type", "").lower(), "other"),
                            "value": ioc.get("value", ""),
                            "evidence": ioc.get("evidence", []),
                            "confirmed": ioc in (report_dict.get("confirmed_iocs") or []),
                        },
                    )
                for tech in (
                    report_dict.get("mitre_techniques")
                    or report_dict.get("sections", {}).get("mitre_techniques")
                    or []
                ):
                    on_event(
                        "ioc_detected",
                        {"ioc_type": "mitre", "value": tech, "evidence": [], "confirmed": True},
                    )
            await push_event(session_id, {"type": "report", "content": report})
    except Exception as e:
        import traceback as _tb

        tb_str = _tb.format_exc()
        print(
            f"[INVESTIGATION ERROR session={session_id} orch={orchestrator}]\n{tb_str}", flush=True
        )
        await push_event(
            session_id, {"type": "error", "message": f"{type(e).__name__}: {str(e)[:300]}"}
        )

    await push_event(session_id, {"type": "complete"})


@app.get("/api/export/pdf/{session_id}")
async def export_pdf(session_id: str):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        HRFlowable,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    events = _sessions.get(session_id, [])
    if not events:
        return Response(status_code=404)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    BLUE = colors.HexColor("#1a73e8")
    DARK = colors.HexColor("#202124")
    GRAY = colors.HexColor("#5f6368")
    colors.HexColor("#d93025")
    colors.HexColor("#1e8e3e")

    h1 = ParagraphStyle(
        "h1",
        parent=styles["Normal"],
        fontSize=22,
        textColor=BLUE,
        spaceAfter=4,
        fontName="Helvetica-Bold",
    )
    h2 = ParagraphStyle(
        "h2",
        parent=styles["Normal"],
        fontSize=13,
        textColor=DARK,
        spaceBefore=10,
        spaceAfter=4,
        fontName="Helvetica-Bold",
    )
    body = ParagraphStyle(
        "body", parent=styles["Normal"], fontSize=9, textColor=DARK, leading=14, spaceAfter=3
    )
    meta = ParagraphStyle("meta", parent=styles["Normal"], fontSize=8, textColor=GRAY, spaceAfter=2)

    story = []
    case_id = next((e["case_id"] for e in events if e.get("case_id")), session_id)
    briefing = next((e.get("briefing", "") for e in events if e.get("type") == "start"), "")
    orchestrator_label = next(
        (e.get("orchestrator", "") for e in events if e.get("type") == "meta"), ""
    )
    self_corr = next(
        (e.get("self_correction", True) for e in events if e.get("type") == "meta"), True
    )
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    story.append(Paragraph("SIFTGuard DFIR Report", h1))
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=6))
    story.append(Paragraph(f"Case ID: <b>{case_id}</b>", meta))
    story.append(Paragraph(f"Generated: {generated_at}", meta))
    story.append(Paragraph(f"Session: {session_id}", meta))
    if orchestrator_label:
        orch_map = {
            "native": "Native Claude Loop",
            "openai-fc": "OpenAI Function Calling",
            "langgraph": "LangGraph",
            "gemini": "Gemini 2.5 Pro",
            "claudecode": "Claude Code (headless)",
        }
        story.append(
            Paragraph(
                f"Orchestrator: <b>{orch_map.get(orchestrator_label, orchestrator_label)}</b>", meta
            )
        )
        story.append(
            Paragraph(f"Self-correction: {'Enabled' if self_corr else 'Disabled (ablation)'}", meta)
        )
    story.append(Spacer(1, 6 * mm))

    if briefing:
        story.append(Paragraph("Briefing", h2))
        story.append(Paragraph(briefing.replace("\n", "<br/>"), body))
        story.append(Spacer(1, 4 * mm))

    report_blocks = [e["content"] for e in events if e.get("type") == "report"]
    if report_blocks:
        story.append(Paragraph("Investigation Report", h2))
        story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY, spaceAfter=4))
        import re as _re2

        for block in report_blocks:
            if isinstance(block, dict):
                block = json.dumps(block, indent=2)
            elif isinstance(block, tuple | list):
                block = str(block[0]) if block else ""
            elif not isinstance(block, str):
                block = str(block)
            block = _re2.sub(r"\[TRAINING\].*?(?=##|\Z)", "", block, flags=_re2.DOTALL).strip()
            block = _re2.sub(r"\*\*([^*]+)\*\*", r"\1", block)
            block = _re2.sub(r"\*([^*]+)\*", r"\1", block)
            for line in block.split("\n"):
                line = line.strip()
                if not line:
                    story.append(Spacer(1, 2 * mm))
                elif line.startswith("## "):
                    story.append(Paragraph(line[3:], h2))
                elif line.startswith("# "):
                    story.append(Paragraph(line[2:], h1))
                elif line.startswith("- ") or line.startswith("* "):
                    story.append(Paragraph(f"• {line[2:]}", body))
                else:
                    story.append(Paragraph(line, body))

    tool_events = [e for e in events if e.get("type") == "tool_result"]
    if tool_events:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("Tool Execution Log", h2))
        story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY, spaceAfter=4))
        table_data = [["Tool", "Outcome", "Findings", "Duration", "Summary"]]
        for e in tool_events:
            table_data.append(
                [
                    e.get("tool", "")[:30],
                    e.get("outcome", "").upper(),
                    str(e.get("findings_count", 0)),
                    f"{e.get('duration_ms', 0)}ms",
                    (e.get("summary", "")[:60] + "…")
                    if len(e.get("summary", "")) > 60
                    else e.get("summary", ""),
                ]
            )
        t = Table(table_data, colWidths=[40 * mm, 20 * mm, 18 * mm, 20 * mm, None])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f8f9fa")],
                    ),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dadce0")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(t)

    story.append(Spacer(1, 8 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY))
    story.append(
        Paragraph(
            "Generated by SIFTGuard — Autonomous DFIR Agent | SANS SIFT Workstation | "
            "Evidence integrity guaranteed by architectural spoliation prevention.",
            ParagraphStyle("footer", parent=meta, alignment=TA_CENTER),
        )
    )

    doc.build(story)
    buf.seek(0)
    filename = f"siftguard-{case_id}-{session_id}.pdf"
    return Response(
        content=buf.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/corrections/{case_id}")
async def get_corrections(case_id: str):
    from siftguard.eval.analytics.correction_panel import get_correction_breakdown

    db_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "audit", f"{case_id}.db")
    if not os.path.exists(db_path):
        return Response(status_code=404)
    return get_correction_breakdown(db_path, case_id)


@app.get("/api/orchestrator-comparison/{db_id}")
async def orchestrator_comparison(db_id: str, case: str = "all"):
    """Panel 7 — case='all' aggregates; case='TEST-001' filters."""
    import json as _json
    import sqlite3
    from datetime import datetime as _dt

    ORCH_IDS = [
        "siftguard-v2",
        "siftguard-langgraph",
        "siftguard-openai-fc",
        "siftguard-gemini",
        "siftguard-claudecode",
    ]
    ORCH_LABELS = {
        "siftguard-v2": "Native Loop (Sonnet)",
        "siftguard-langgraph": "LangGraph (Sonnet)",
        "siftguard-openai-fc": "OpenAI FC (gpt-5.5)",
        "siftguard-gemini": "Gemini 3 Pro",
        "siftguard-claudecode": "Claude Code (headless)",
    }

    known_cases = list_case_ids()
    target_cases = (
        known_cases if case == "all" else ([case] if case in known_cases else known_cases)
    )

    repo_root = pathlib.Path(__file__).resolve().parents[3]

    # F1 from experiments/analysis/<cid>/data.json
    f1_by_orch: dict[str, dict[str, float]] = {}
    for cid in target_cases:
        data_file = repo_root / "experiments" / "analysis" / cid / "data.json"
        if not data_file.exists():
            continue
        try:
            d = _json.loads(data_file.read_text())
            p7 = d.get("panel_7", {}).get("data", {})
            mapping = {
                "siftguard-v2": (p7.get("siftguard-v2") or p7.get("baseline", {})).get("mean"),
                "siftguard-langgraph": (
                    p7.get("siftguard-langgraph") or p7.get("langgraph", {})
                ).get("mean"),
                "siftguard-openai-fc": (
                    p7.get("siftguard-openai-fc") or p7.get("openai_fc", {})
                ).get("mean"),
                "siftguard-gemini": (p7.get("siftguard-gemini") or p7.get("gemini", {})).get(
                    "mean"
                ),
                "siftguard-claudecode": (
                    p7.get("siftguard-claudecode") or p7.get("claudecode", {})
                ).get("mean"),
            }
            for aid, score in mapping.items():
                if score is not None:
                    f1_by_orch.setdefault(aid, {})[cid] = round(score, 4)
        except Exception:
            pass

    # cost/iterations/wall_time from audit DB
    db_path = repo_root / "audit" / f"{db_id}.db"
    db_results: dict[str, dict] = {}
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            db_rows = conn.execute(
                "SELECT agent_id, total_cost_usd, completed_iterations, started_at, completed_at "
                "FROM experiment_run ORDER BY started_at DESC"
            ).fetchall()
            for row in db_rows:
                aid = row["agent_id"]
                if aid in db_results:
                    continue
                wall_ms = None
                if row["started_at"] and row["completed_at"]:
                    with contextlib.suppress(Exception):
                        wall_ms = int(
                            (
                                _dt.fromisoformat(row["completed_at"])
                                - _dt.fromisoformat(row["started_at"])
                            ).total_seconds()
                            * 1000
                        )
                db_results[aid] = {
                    "cost_usd": round(row["total_cost_usd"], 4)
                    if row["total_cost_usd"] is not None
                    else None,
                    "iterations": row["completed_iterations"],
                    "wall_ms": wall_ms,
                }
        except Exception:
            pass
        finally:
            conn.close()

    coverage_hits = 0
    coverage_total = len(ORCH_IDS) * len(target_cases)
    rows = {}
    for aid in ORCH_IDS:
        case_scores = f1_by_orch.get(aid, {})
        scores = list(case_scores.values())
        coverage_hits += len(scores)
        db = db_results.get(aid, {})
        rows[aid] = {
            "label": ORCH_LABELS[aid],
            "mean_f1": round(sum(scores) / len(scores), 4) if scores else None,
            "case_scores": case_scores,
            "n_cases": len(scores),
            "cost_usd": db.get("cost_usd"),
            "iterations": db.get("iterations"),
            "wall_ms": db.get("wall_ms"),
        }

    return {
        "rows": rows,
        "coverage": {"hits": coverage_hits, "total": coverage_total},
        "case_filter": case,
        "available_cases": known_cases,
    }


@app.get("/api/cases")
async def get_cases():
    """Returns list of known cases for Panel 7 case selector."""
    cases = []
    for cid in list_case_ids():
        try:
            m = get_case(cid)
            cases.append({"case_id": cid, "case_name": m.case_name, "threat_type": m.threat_type})
        except Exception:
            cases.append({"case_id": cid, "case_name": cid, "threat_type": "unknown"})
    return {"cases": cases}
