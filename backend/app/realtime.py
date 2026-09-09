from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .config import get_settings

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
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            system_instruction=(
                "You are GenQuantaa AI, a concise real-time interview copilot. "
                "Transcribe the speaker and provide direct, structured interview answers. "
                "Do not invent resume facts."
            ),
        )

        async with client.aio.live.connect(model=settings.gemini_model, config=config) as session:
            async def receive_client() -> None:
                while True:
                    message: dict[str, Any] = json.loads(await websocket.receive_text())
                    kind = message.get("type")
                    if kind == "text":
                        text = str(message.get("text", "")).strip()
                        if text:
                            await session.send_realtime_input(text=text)
                    elif kind == "context":
                        text = str(message.get("text", "")).strip()
                        if text:
                            await session.send_realtime_input(text=f"Context update:\n{text}")
                    elif kind == "audio":
                        data = base64.b64decode(message.get("data", ""))
                        if data:
                            await session.send_realtime_input(
                                audio=types.Blob(data=data, mime_type=message.get("mime_type", "audio/pcm;rate=16000"))
                            )
                    elif kind == "audio_end":
                        await session.send_realtime_input(audio_stream_end=True)

            async def send_model() -> None:
                async for response in session.receive():
                    server = getattr(response, "server_content", None)
                    if server:
                        interim = getattr(server, "interim_input_transcription", None)
                        if interim and getattr(interim, "text", None):
                            await websocket.send_json({"type": "transcript_interim", "text": interim.text})
                        final = getattr(server, "input_transcription", None)
                        if final and getattr(final, "text", None):
                            await websocket.send_json({"type": "transcript", "text": final.text})
                        output = getattr(server, "output_transcription", None)
                        if output and getattr(output, "text", None):
                            await websocket.send_json({"type": "text", "text": output.text})
                        if getattr(server, "interrupted", False):
                            await websocket.send_json({"type": "interrupted"})
                        if getattr(server, "turn_complete", False):
                            await websocket.send_json({"type": "turn_complete"})
                    if response.text:
                        await websocket.send_json({"type": "text", "text": response.text})

            await asyncio.gather(receive_client(), send_model())
    except WebSocketDisconnect:
        return
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
            await websocket.close(code=1011)
        except Exception:
            pass
