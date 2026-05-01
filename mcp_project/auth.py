"""
OAuth/JWT verification helpers for MCP tool access.
"""
import os
import time
import json
from typing import Any

import requests
from jose import jwt

_JWKS_CACHE: dict[str, Any] = {"fetched_at": 0, "jwks": None}


def _load_jwks() -> dict:
    jwks_url = os.getenv("MCP_JWKS_URL", "").strip()
    if not jwks_url:
        raise ValueError("MCP_JWKS_URL is not configured.")

    now = int(time.time())
    cache_ttl = int(os.getenv("MCP_JWKS_TTL_SECONDS", "600"))
    if _JWKS_CACHE["jwks"] and now - _JWKS_CACHE["fetched_at"] < cache_ttl:
        return _JWKS_CACHE["jwks"]

    resp = requests.get(jwks_url, timeout=10)
    resp.raise_for_status()
    jwks = resp.json()
    _JWKS_CACHE["jwks"] = jwks
    _JWKS_CACHE["fetched_at"] = now
    return jwks


def _get_signing_key(token: str) -> dict:
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")
    jwks = _load_jwks()
    keys = jwks.get("keys", [])
    for key in keys:
        if key.get("kid") == kid:
            return key
    raise ValueError("Signing key not found for token.")


def _normalize_token(token: str) -> str:
    token = (token or "").strip()
    if token.lower().startswith("bearer "):
        return token[7:].strip()
    return token


def verify_access(token: str, required_scopes: list[str]) -> tuple[bool, dict, str | None]:
    """Verify JWT token and required scopes. Returns (ok, claims, error)."""
    auth_required = os.getenv("MCP_AUTH_REQUIRED", "true").lower() == "true"
    token = _normalize_token(token)

    if not token:
        if auth_required:
            return False, {}, "Missing access token."
        return True, {}, None

    issuer = os.getenv("MCP_ISSUER", "").strip() or None
    audience = os.getenv("MCP_AUDIENCE", "").strip() or None

    try:
        key = _get_signing_key(token)
        claims = jwt.decode(
            token,
            key,
            algorithms=[key.get("alg", "RS256")],
            issuer=issuer,
            audience=audience,
        )
    except Exception as exc:
        return False, {}, f"Invalid token: {exc}"

    if required_scopes:
        scope_str = claims.get("scope", "") or ""
        scopes = set(scope_str.split())
        for required in required_scopes:
            if required not in scopes:
                return False, claims, "Missing required scope."

    return True, claims, None


def get_actor_from_claims(claims: dict, fallback: dict | None = None) -> tuple[str, str]:
    """Extract actor_id and role from claims or fallback metadata."""
    fallback = fallback or {}
    actor_id = claims.get("sub") or claims.get("email") or fallback.get("actor_id") or "unknown"
    roles = claims.get("roles") or claims.get("role") or fallback.get("actor_role") or "unknown"
    if isinstance(roles, list):
        actor_role = roles[0] if roles else "unknown"
    else:
        actor_role = str(roles)
    return str(actor_id), actor_role
