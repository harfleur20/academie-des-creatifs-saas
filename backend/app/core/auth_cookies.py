from fastapi import Request

from app.core.config import settings


def auth_cookie_secure_for_request(request: Request) -> bool:
    """Keep production cookies secure while allowing local HTTP development."""
    if settings.environment == "production":
        return settings.auth_cookie_secure
    return settings.auth_cookie_secure and request.url.scheme == "https"
