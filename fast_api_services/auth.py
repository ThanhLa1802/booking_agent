"""
JWT dependency shared with Django — validates HS256 tokens issued by Django SimpleJWT.
Extracts user_id from the `user_id` claim (matching SimpleJWT's USER_ID_CLAIM setting).
"""
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel
from .config import get_settings

_bearer = HTTPBearer()


class TokenPayload(BaseModel):
    user_id: int
    username: str = ""


def _decode_token(token: str) -> TokenPayload:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user_id claim",
        )
    return TokenPayload(user_id=int(user_id), username=payload.get("username", ""))


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> TokenPayload:
    return _decode_token(credentials.credentials)


# Optional auth — returns None if no token provided (for public endpoints)
_optional_bearer = HTTPBearer(auto_error=False)


async def get_optional_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_optional_bearer)
    ],
) -> TokenPayload | None:
    if credentials is None:
        return None
    return _decode_token(credentials.credentials)
