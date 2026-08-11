# app/main.py
from app.logger import setup_logging

setup_logging()

from app.secrets import load_gemini_api_key_from_secret_manager

load_gemini_api_key_from_secret_manager()


import os
import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
import logging

logger = logging.getLogger("api")
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from google.genai import types
from app.session import get_runner

# OpenTelemetry Tracing Setup
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

provider = TracerProvider()
if os.getenv("ENABLE_TRACING", "false").lower() == "true":
    processor = SimpleSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

app = FastAPI(title="Mini-Concierge Agent API")
FastAPIInstrumentor.instrument_app(app)


class ApprovalResponsePayload(BaseModel):
    approval_id: str
    confirmed: bool


class QueryRequest(BaseModel):
    user_id: str
    session_id: str
    query: Optional[str] = None
    invocation_id: Optional[str] = None
    approval_response: Optional[ApprovalResponsePayload] = None


def create_approval_response(approval_id: str, confirmed: bool) -> types.Content:
    confirmation_response = types.FunctionResponse(
        id=approval_id,
        name="adk_request_confirmation",
        response={"confirmed": confirmed},
    )
    return types.Content(
        role="user", parts=[types.Part(function_response=confirmation_response)]
    )


def check_for_approval(events: List[Any]) -> Optional[Dict[str, Any]]:
    for event in events:
        if not event.content or not event.content.parts:
            continue
        for part in event.content.parts:
            fc = part.function_call
            if not fc or fc.name != "adk_request_confirmation":
                continue
            hint = (fc.args or {}).get("hint") if fc.args else None
            return {
                "approval_id": fc.id,
                "invocation_id": event.invocation_id,
                "hint": hint,
            }
    return None


def get_final_response(events: List[Any]) -> str:
    response_parts = []
    for event in events:
        if not event.content or not event.content.parts:
            continue
        for part in event.content.parts:
            if getattr(part, "thought", False):
                continue
            if part.text:
                response_parts.append(part.text)
    return "".join(response_parts).strip()


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


async def consolidate_memory_background(session_id: str):
    logger.info(
        f"Asynchronously consolidating memory for session {session_id} in background..."
    )
    await asyncio.sleep(0.1)
    logger.info(f"Consolidation complete for session {session_id}.")


async def _execute_agent_run(runner, payload: QueryRequest) -> list[Any]:
    if payload.invocation_id and payload.approval_response:
        # Resuming flow
        approval_msg = create_approval_response(
            payload.approval_response.approval_id, payload.approval_response.confirmed
        )
        return [
            event
            async for event in runner.run_async(
                user_id=payload.user_id,
                session_id=payload.session_id,
                new_message=approval_msg,
                invocation_id=payload.invocation_id,
            )
        ]

    # New flow
    if not payload.query:
        raise HTTPException(
            status_code=400, detail="Query is required for new requests."
        )
    user_msg = types.Content(
        role="user", parts=[types.Part.from_text(text=payload.query)]
    )
    return [
        event
        async for event in runner.run_async(
            user_id=payload.user_id, session_id=payload.session_id, new_message=user_msg
        )
    ]


@app.post("/query")
async def query_endpoint(payload: QueryRequest, background_tasks: BackgroundTasks):
    runner = get_runner()
    try:
        events = await _execute_agent_run(runner, payload)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Agent execution failed")
        raise HTTPException(status_code=500, detail=f"Agent execution error: {str(e)}")

    approval_info = check_for_approval(events)
    if approval_info:
        return {
            "status": "paused",
            "message": "Requires human approval",
            "session_id": payload.session_id,
            "invocation_id": approval_info["invocation_id"],
            "approval_info": {
                "approval_id": approval_info["approval_id"],
                "hint": approval_info["hint"],
            },
        }

    final_text = get_final_response(events)
    background_tasks.add_task(consolidate_memory_background, payload.session_id)
    return {
        "status": "success",
        "response": final_text,
        "session_id": payload.session_id,
    }
