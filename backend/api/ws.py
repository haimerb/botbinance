import asyncio

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from backend.core.config import bot
from backend.services.auth import decode_token
from backend.services.metrics import update_ws_connections, record_ws_message

router = APIRouter(tags=["websocket"])


@router.websocket("/api/ws")
async def websocket_endpoint(ws: WebSocket):
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4001, reason="Token requerido")
        return
    try:
        current_user = decode_token(token)
    except HTTPException:
        await ws.close(code=4001, reason="Token inválido")
        return

    bot.ensure_user(current_user["sub"])
    await ws.accept()
    update_ws_connections(1)
    try:
        while True:
            state = bot.get_state()
            await ws.send_json(state)
            record_ws_message()
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        update_ws_connections(-1)
