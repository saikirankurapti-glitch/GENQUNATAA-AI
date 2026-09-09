from __future__ import annotations

import asyncio
import base64
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .config import get_settings
from .db import SessionLocal
from .db_models import SessionRecord
from .intelligence import InterviewIntelligence
from .question_boundary import QuestionBoundaryDetector
from .visual_fusion import visual_copilot_fusion

router = APIRouter(prefix="/api/v1/realtime")


@router.websocket("/ws")
async def realtime_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    settings = get_settings()
    if not settings.gemini_api_key:
        await websocket.send_json({"type": "error", "message": "GEMINI_API_KEY is not configured."})
        await websocket.close(code=1008)
        return
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
                        async with SessionLocal() as db:
                            if raw_id:
                                try:
                                    candidate = UUID(str(raw_id))
                                    if await db.get(SessionRecord, candidate): session_id = candidate
                                except ValueError: pass
                            if session_id is None:
                                record = SessionRecord(title="Live interview", mode="live")
                                db.add(record)
                                await db.commit()
                                await db.refresh(record)
                                session_id = record.id
                        detector.reset()
                        await websocket.send_json({"type": "session", "session_id": str(session_id), "auto_answer": auto_answer, "answer_mode": answer_mode, "visual_context_active": bool(visual_context)})
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
                        if text: await session.send_realtime_input(text=text)
                    elif kind == "context":
                        text = str(message.get("text", "")).strip()
                        if text: await session.send_realtime_input(text=f"Context update:\n{text}")
                    elif kind == "audio":
                        data = base64.b64decode(message.get("data", ""))
                        if data:
                            await session.send_realtime_input(audio=types.Blob(data=data, mime_type=message.get("mime_type", "audio/pcm;rate=16000")))
                    elif kind == "audio_end":
                        await session.send_realtime_input(audio_stream_end=True)

            async def analyze_and_send(boundary: Any) -> None:
                if not session_id or not auto_answer: return
                try:
                    await websocket.send_json({"type": "question_detected", "data": {"text": boundary.text, "confidence": boundary.confidence, "reason": boundary.reason, "visual_context_active": bool(visual_context)}})
                    async with SessionLocal() as db:
                        if visual_context:
                            result = await visual_copilot_fusion.analyze(db, session_id, boundary.text, visual_context, detection_confidence=boundary.confidence, detection_reason=boundary.reason, answer_mode=answer_mode)
                        else:
                            result = await InterviewIntelligence().analyze_question(db, session_id, boundary.text, detection_confidence=boundary.confidence, detection_reason=boundary.reason, answer_mode=answer_mode)
                    await websocket.send_json({"type": "question_analysis", "data": result})
                except Exception as exc:
                    await websocket.send_json({"type": "intelligence_error", "message": str(exc)})

            async def send_model() -> None:
                async for response in session.receive():
                    server = getattr(response, "server_content", None)
                    if server:
                        interim = getattr(server, "interim_input_transcription", None)
                        if interim and getattr(interim, "text", None): await websocket.send_json({"type": "transcript_interim", "text": interim.text})
                        final = getattr(server, "input_transcription", None)
                        if final and getattr(final, "text", None):
                            transcript = final.text.strip()
                            if transcript:
                                detector.add(transcript)
                                await websocket.send_json({"type": "transcript", "text": transcript})
                                if "?" in transcript:
                                    boundary = detector.flush()
                                    if boundary: asyncio.create_task(analyze_and_send(boundary))
                        output = getattr(server, "output_transcription", None)
                        if output and getattr(output, "text", None): await websocket.send_json({"type": "text", "text": output.text})
                        if getattr(server, "interrupted", False):
                            detector.reset()
                            await websocket.send_json({"type": "interrupted"})
                        if getattr(server, "turn_complete", False):
                            boundary = detector.flush()
                            if boundary: asyncio.create_task(analyze_and_send(boundary))
                            await websocket.send_json({"type": "turn_complete"})
                    if response.text: await websocket.send_json({"type": "text", "text": response.text})
            await asyncio.gather(receive_client(), send_model())
    except WebSocketDisconnect:
        return
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
            await websocket.close(code=1011)
        except Exception: pass
