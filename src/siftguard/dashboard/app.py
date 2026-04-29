from __future__ import annotations
import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="SIFTGuard Dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_sessions: dict[str, list[dict]] = {}
_queues: dict[str, asyncio.Queue] = {}

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
    async def event_generator() -> AsyncGenerator[str, None]:
        _, queue = get_or_create_session(session_id)
        for event in _sessions.get(session_id, []):
            yield f"data: {json.dumps(event)}\n\n"
        while True:
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
    asyncio.create_task(_run_investigation(session_id, case_id, briefing, memory_image))
    return {"session_id": session_id, "case_id": case_id}

async def _run_investigation(session_id: str, case_id: str, briefing: str, memory_image: str):
    from siftguard.agent.loop import SYSTEM_PROMPT, TOOL_SCHEMAS, _dispatch_tool
    from siftguard.audit.log import AuditLog
    import anthropic

    await push_event(session_id, {"type": "start", "case_id": case_id, "briefing": briefing})
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    evidence = {"memory_image": memory_image} if memory_image else {}
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
            model="claude-sonnet-4-5-20251022",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
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
