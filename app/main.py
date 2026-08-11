# app/main.py
from app.logger import setup_logging

setup_logging()

from fastapi import FastAPI, HTTPException
import logging

logger = logging.getLogger("api")
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from google.genai import types
from app.session import get_runner
import app.session as app_session

app = FastAPI(title="Mini-Concierge Agent API")


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
        if event.content and event.content.parts:
            for part in event.content.parts:
                if (
                    part.function_call
                    and part.function_call.name == "adk_request_confirmation"
                ):
                    # Extract hint from args if present
                    hint = None
                    if part.function_call.args:
                        hint = part.function_call.args.get("hint")
                    return {
                        "approval_id": part.function_call.id,
                        "invocation_id": event.invocation_id,
                        "hint": hint,
                    }
    return None


def get_final_response(events: List[Any]) -> str:
    response_parts = []
    for event in events:
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text and not getattr(part, "thought", False):
                    response_parts.append(part.text)
    return "".join(response_parts).strip()


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/query")
async def query_endpoint(payload: QueryRequest):
    runner = get_runner()
    events = []

    import os

    db_path = "data/sessions.db"
    if os.path.exists(db_path):
        print(f"DEBUG: DB file size: {os.path.getsize(db_path)} bytes")
    else:
        print("DEBUG: DB file does NOT exist!")

    session = await app_session.session_service.get_session(
        app_name="mini_concierge",
        user_id=payload.user_id,
        session_id=payload.session_id,
    )

    if session:
        print(
            f"DEBUG: Session {payload.session_id} exists. Events count: {len(session.events)}"
        )
        for e in session.events:

            author = getattr(e, "author", "unknown")
            content = getattr(e, "content", None) or getattr(e, "message", None)
            print(f"  Event: {author} id={e.id} ts={e.timestamp} - {content}")

    else:
        print(f"DEBUG: Session {payload.session_id} does NOT exist in DB.")
        try:
            sessions_list = await app_session.session_service.list_sessions(
                app_name="mini_concierge"
            )
            print(f"DEBUG: Total sessions in DB: {len(sessions_list.sessions)}")
            for s in sessions_list.sessions:
                print(f"  Session ID in DB: {s.id}, User ID: {s.user_id}")
        except Exception as e:
            print(f"DEBUG: Failed to list sessions: {e}")

    try:

        if payload.invocation_id and payload.approval_response:
            # Resuming flow
            approval_msg = create_approval_response(
                payload.approval_response.approval_id,
                payload.approval_response.confirmed,
            )
            async for event in runner.run_async(
                user_id=payload.user_id,
                session_id=payload.session_id,
                new_message=approval_msg,
                invocation_id=payload.invocation_id,
            ):
                events.append(event)
        else:
            # New flow
            if not payload.query:
                raise HTTPException(
                    status_code=400, detail="Query is required for new requests."
                )
            user_msg = types.Content(
                role="user", parts=[types.Part.from_text(text=payload.query)]
            )
            async for event in runner.run_async(
                user_id=payload.user_id,
                session_id=payload.session_id,
                new_message=user_msg,
            ):
                events.append(event)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Agent execution failed")
        raise HTTPException(status_code=500, detail=f"Agent execution error: {str(e)}")

    print(
        f"\n[API] Events: {[{'author': e.author, 'content': e.content, 'long_running_tool_ids': e.long_running_tool_ids} for e in events]}"
    )
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
    return {
        "status": "success",
        "response": final_text,
        "session_id": payload.session_id,
    }
