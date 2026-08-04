from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.websockets import WebSocket

from config import get_settings

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> None:
    """FastAPI dependency: validates Bearer token when app_access_token is configured.

    Attach via ``dependencies=[Depends(require_auth)]`` on an APIRouter or route.
    Auth is silently skipped when ``settings.app_access_token`` is empty (local dev).
    """
    expected: str = get_settings().app_access_token
    if not expected:
        return  # auth disabled — local-dev default

    if credentials is None or credentials.credentials != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing access token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def validate_ws_token(websocket: WebSocket, token: str = "") -> bool:
    """Validate a WebSocket connection token (passed as ``?token=`` query param).

    Browsers cannot set custom headers on WebSocket upgrades, so the token is
    carried as a query parameter instead.

    Returns True if allowed, or closes the socket with code 4401 and returns
    False when a token is required but missing/wrong.
    """
    expected: str = get_settings().app_access_token
    if not expected:
        return True  # auth disabled

    if token != expected:
        logger.warning("WebSocket auth rejected — invalid or missing token")
        await websocket.close(code=4401)
        return False

    return True
