import asyncio

import jwt
import pytest
from fastapi import HTTPException

import backend.api.ws as ws_api
from backend.services.auth import JWT_ALGO, JWT_SECRET, decode_token


class FakeWebSocket:
    def __init__(self, token=None):
        self.query_params = {"token": token} if token is not None else {}
        self.closed = None
        self.accepted = False

    async def close(self, code=None, reason=None):
        self.closed = (code, reason)

    async def accept(self):
        self.accepted = True


def test_decode_token_rechaza_payload_sin_sub():
    token = jwt.encode(
        {"email": "usuario@example.com", "type": "access"},
        JWT_SECRET,
        algorithm=JWT_ALGO,
    )

    with pytest.raises(HTTPException) as error:
        decode_token(token)

    assert error.value.status_code == 401
    assert error.value.detail == "Token inválido"


def test_ws_cierra_token_con_sub_no_entero():
    token = jwt.encode(
        {"sub": "no-entero", "email": "usuario@example.com", "type": "access"},
        JWT_SECRET,
        algorithm=JWT_ALGO,
    )
    socket = FakeWebSocket(token)

    asyncio.run(ws_api.websocket_endpoint(socket))

    assert socket.closed == (4001, "Token inválido")
    assert not socket.accepted
