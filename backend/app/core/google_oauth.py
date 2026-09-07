from __future__ import annotations

from dataclasses import dataclass

from starlette.concurrency import run_in_threadpool

from app.core.config import settings

GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


@dataclass(frozen=True)
class GoogleProfile:
    subject: str
    email: str
    email_verified: bool
    full_name: str
    picture: str | None
    hosted_domain: str | None


def _verify_sync(token: str) -> dict:
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    return id_token.verify_oauth2_token(token, google_requests.Request(), settings.GOOGLE_CLIENT_ID)


async def verify_google_id_token(token: str) -> GoogleProfile:
    """Validate a Google ID token and return the verified profile."""
    if not settings.google_enabled:
        raise ValueError("Google sign-in is not configured.")
    try:
        claims = await run_in_threadpool(_verify_sync, token)
    except ImportError:
        raise ValueError("Google sign-in dependency is not installed.")
    except Exception:
        raise ValueError("Invalid Google credential.")

    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise ValueError("Invalid Google credential.")
    email = (claims.get("email") or "").lower()
    if not email:
        raise ValueError("Google account did not provide an email address.")
    if not claims.get("email_verified", False):
        raise ValueError("Google email address is not verified.")

    allowed = settings.google_allowed_domains_list
    if allowed and email.rsplit("@", 1)[-1] not in allowed:
        raise ValueError("This Google account domain is not allowed to sign in.")

    return GoogleProfile(
        subject=str(claims["sub"]),
        email=email,
        email_verified=True,
        full_name=claims.get("name") or email.split("@")[0],
        picture=claims.get("picture"),
        hosted_domain=claims.get("hd"),
    )
