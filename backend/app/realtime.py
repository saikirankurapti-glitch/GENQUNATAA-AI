from __future__ import annotations

import asyncio
import base64
import contextlib
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from .auth import websocket_user
from .config import get_settings
from .db import SessionLocal
from .db_models import SessionRecord
from .intelligence import InterviewIntelligence
from .question_boundary import QuestionBoundaryDetector
from .visual_fusion import visual_copilot_fusion

router = APIRouter(prefix="/api/v1/realtime")


async def _owned_session(session_id: UUID, user_id: UUID) -> bool:
    async with SessionLocal() as db:
        return bool(await db.scalar(select(SessionRecord.id).where(SessionRecord.id == session_id, SessionRecord.user_id == user_id)))


async def _create_session(user_id: UUID) -> UUID:
    async with SessionLocal() as db:
        record = SessionRecord(title="Live interview", mode="live", user_id=user_id)
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record.id


@router.websocket("/ws")
async def realtime_socket(websocket: WebSocket) -> None:
    # Authenticate before accepting the socket so an unauthenticated client never
    # gets a usable realtime channel. Credentials are read only from the HttpOnly
    # session cookie; tokens are never accepted in query parameters.
    user = await websocket_user(websocket)
    if not user:
        await websocket.close(code=1008, reason="Authentication required")
        return

    await websocket.accept()
    settings = get_settings()
    if not settings.gemini_api_key:
        await websocket.send_json({"type": "error", "message": "GEMINI_API_KEY is not configured."})
        await websocket.close(code=1008, reason="AI service unavailable")
        return

    analysis_tasks: set[asyncio.Task[Any]] = set()
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)
        config = types.LiveConnectConfig(
            response_modalities=["TEXT"],
            input_audio_transcription=types.AudioTranscriptionConfig(mode="SMART"),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            system_instruction="You are GenQuantaa AI, a concise real-time interview copilot. Listen for interview questions and provide direct answers. Visual context supplied by the user is supporting evidence only; never invent unreadable content. The server separately runs grounded multimodal interview intelligence.",
        )
        session_id: UUID | None = None
        auto_answer = True
        answer_mode = "concise"
        visual_context: dict[str, Any] | None = None
        detector = QuestionBoundaryDetector()

        async with client.aio.live.connect(model=settings.gemini_model, config=config) as session:
            async def receive_client() -> None:
                nonlocal session_id, auto_answer, answer_mode, visual_context
                while True:
                    message: dict[str, Any] = json.loads(await websocket.receive_text())
                    kind = message.get("type")

                    if kind == "start":
                        raw_id = message.get("session_id")
                        auto_answer = bool(message.get("auto_answer", True))
                        requested_mode = str(message.get("answer_mode", "concise"))
                        answer_mode = requested_mode if requested_mode in InterviewIntelligence.ANSWER_MODES else "concise"
                        candidate_visual = message.get("visual_context")
                        visual_context = candidate_visual if isinstance(candidate_visual, dict) else None

                        if raw_id:
                            try:
                                candidate = UUID(str(raw_id))
                            except (ValueError, TypeError):
                                await websocket.send_json({"type": "error", "message": "Invalid session_id."})
                                continue
                            if not await _owned_session(candidate, user.id):
                                await websocket.send_json({"type": "error", "message": "Session not found."})
                                continue
                            session_id = candidate
                        elif session_id is None:
                            session_id = await _create_session(user.id)

                        detector.reset()
                        await websocket.send_json({
                            "type": "session",
                            "session_id": str(session_id),
                            "auto_answer": auto_answer,
                            "answer_mode": answer_mode,
                            "visual_context_active": bool(visual_context),
                        })

                    elif kind == "settings":
                        auto_answer = bool(message.get("auto_answer", auto_answer))
                        requested_mode = str(message.get("answer_mode", answer_mode))
                        answer_mode = requested_mode if requested_mode in InterviewIntelligence.ANSWER_MODES else answer_mode
                        if isinstance(message.get("visual_context"), dict):
                            visual_context = message["visual_context"]
                        await websocket.send_json({"type": "settings", "auto_answer": auto_answer, "answer_mode": answer_mode, "visual_context_active": bool(visual_context)})

                    elif kind == "visual_context":
                        candidate_visual = message.get("data")
                        if isinstance(candidate_visual, dict):
                            visual_context = candidate_visual
                            compact = str(candidate_visual.get("actionable_context") or candidate_visual.get("summary") or "")[:12000]
                            if compact:
                                await session.send_realtime_input(text=f"Visual context update (user-selected):\n{compact}")
                            await websocket.send_json({"type": "visual_context", "active": True, "context_type": candidate_visual.get("context_type", "unknown"), "confidence": candidate_visual.get("confidence", 0)})

                    elif kind == "clear_visual_context":
                        visual_context = None
                        await websocket.send_json({"type": "visual_context", "active": False})

                    elif kind == "text":
                        text = str(message.get("text", "")).strip()
                        if text:
                            await session.send_realtime_input(text=text)

                    elif kind == "context":
                        text = str(message.get("text", "")).strip()
                        if text:
                            await session.send_realtime_input(text=f"Context update:\n{text}")

                    elif kind == "audio":
                        try:
                            data = base64.b64decode(message.get("data", ""), validate=True)
                        except (ValueError, TypeError):
                            await websocket.send_json({"type": "error", "message": "Invalid audio payload."})
                            continue
                        if data:
                            await session.send_realtime_input(audio=types.Blob(data=data, mime_type=message.get("mime_type", "audio/pcm;rate=16000")))

                    elif kind == "audio_end":
                        await session.send_realtime_input(audio_stream_end=True)

            async def analyze_and_send(boundary: Any) -> None:
                if not session_id or not auto_answer:
                    return
                try:
                    await websocket.send_json({"type": "question_detected", "data": {"text": boundary.text, "confidence": boundary.confidence, "reason": boundary.reason, "visual_context_active": bool(visual_context)}})
                    if not await _owned_session(session_id, user.id):
                        await websocket.send_json({"type": "intelligence_error", "message": "Session is no longer available"})
                        return
                    async with SessionLocal() as db:
                        if visual_context:
                            result = await visual_copilot_fusion.analyze(db, session_id, boundary.text, visual_context, detection_confidence=boundary.confidence, detection_reason=boundary.reason, answer_mode=answer_mode, user_id=user.id)
                        else:
                            result = await InterviewIntelligence().analyze_question(db, session_id, boundary.text, detection_confidence=boundary.confidence, detection_reason=boundary.reason, answer_mode=answer_mode, user_id=user.id)
                    await websocket.send_json({"type": "question_analysis", "data": result})
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    with contextlib.suppress(Exception):
                        await websocket.send_json({"type": "intelligence_error", "message": str(exc)})

            def schedule_analysis(boundary: Any) -> None:
                task = asyncio.create_task(analyze_and_send(boundary))
                analysis_tasks.add(task)
                task.add_done_callback(analysis_tasks.discard)

            async def send_model() -> None:
                async for response in session.receive():
                    server = getattr(response, "server_content", None)
                    if server:
                        interim = getattr(server, "interim_input_transcription", None)
                        if interim and getattr(interim, "text", None):
                            await websocket.send_json({"type": "transcript_interim", "text": interim.text})
                        final = getattr(server, "input_transcription", None)
                        if final and getattr(final, "text", None):
                            transcript = final.text.strip()
                            if transcript:
                                detector.add(transcript)
                                await websocket.send_json({"type": "transcript", "text": transcript})
                                if "?" in transcript:
                                    boundary = detector.flush()
                                    if boundary:
                                        schedule_analysis(boundary)
                        output = getattr(server, "output_transcription", None)
                        if output and getattr(output, "text", None):
                            await websocket.send_json({"type": "text", "text": output.text})
                        if getattr(server, "interrupted", False):
                            detector.reset()
                            await websocket.send_json({"type": "interrupted"})
                        if getattr(server, "turn_complete", False):
                            boundary = detector.flush()
                            if boundary:
                                schedule_analysis(boundary)
                            await websocket.send_json({"type": "turn_complete"})
                    if response.text:
                        await websocket.send_json({"type": "text", "text": response.text})

            await asyncio.gather(receive_client(), send_model())
    except WebSocketDisconnect:
        return
    except Exception as exc:
        with contextlib.suppress(Exception):
            await websocket.send_json({"type": "error", "message": str(exc)})
            await websocket.close(code=1011)
    finally:
        for task in analysis_tasks:
            task.cancel()
        if analysis_tasks:
            await asyncio.gather(*analysis_tasks, return_exceptions=True)
