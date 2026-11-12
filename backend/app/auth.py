from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings

bearer_scheme = HTTPBearer(auto_error=False)


def unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def decode_access_token(token: str, secret: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
    except jwt.InvalidTokenError as error:
        raise unauthorized("Token de acceso inválido") from error

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise unauthorized("O token non contén un usuario válido")
    return claims


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    settings = get_settings()
    if credentials is None:
        raise unauthorized("Falta o token de acceso")
    if not settings.supabase_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A autenticación non está configurada no servidor",
        )
    return decode_access_token(credentials.credentials, settings.supabase_jwt_secret)


def get_user_roles(claims: dict[str, Any]) -> set[str]:
    roles = {claims.get("role")} if isinstance(claims.get("role"), str) else set()
    metadata = claims.get("user_metadata")
    if isinstance(metadata, dict) and isinstance(metadata.get("role"), str):
        roles.add(metadata["role"])
    return {role for role in roles if role}


def require_roles(*allowed_roles: str):
    def dependency(claims: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if not get_user_roles(claims).intersection(allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="O usuario non ten permisos para esta operación",
            )
        return claims

    return dependency
