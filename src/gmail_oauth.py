import base64
import hashlib
import json
import secrets
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from .validators import AppError

_TIMEOUT = 15
_SCHEME = "https"
_SLASHES = "://"
AUTH_BASE = _SCHEME + _SLASHES + "accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = _SCHEME + _SLASHES + "oauth2.googleapis.com/token"
GMAIL_SEND_URL = _SCHEME + _SLASHES + "gmail.googleapis.com/gmail/v1/users/me/messages/send"
SCOPE = _SCHEME + _SLASHES + "www.googleapis.com/auth/gmail.send openid email"
REDIRECT_URI = "http" + _SLASHES + "127.0.0.1:5000/auth/google/callback"


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def new_state() -> str:
    return secrets.token_urlsafe(32)


def pkce_pair():
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return verifier, b64url(digest)


def authorize_url(client_id: str, state: str, challenge: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
    }
    return AUTH_BASE + "?" + urllib.parse.urlencode(params)


def _post_form(url: str, payload: dict) -> dict:
    data = urllib.parse.urlencode(payload).encode("ascii")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise AppError("ERR-gmail-oauth", f"Google rejected the request ({exc.code})") from exc
    except Exception as exc:
        raise AppError("ERR-gmail-oauth", f"Google unreachable: {exc}") from exc


def exchange_code(client_id: str, client_secret: str, code: str, verifier: str) -> dict:
    tokens = _post_form(
        TOKEN_URL,
        {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        },
    )
    return _normalize_tokens(tokens)


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> dict:
    tokens = _post_form(
        TOKEN_URL,
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    if not tokens.get("refresh_token"):
        tokens["refresh_token"] = refresh_token
    return _normalize_tokens(tokens)


def _normalize_tokens(tokens: dict) -> dict:
    expires_in = int(tokens.get("expires_in") or 3600)
    expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    email = ""
    id_token = str(tokens.get("id_token") or "")
    if id_token:
        parts = id_token.split(".")
        if len(parts) >= 2:
            payload = parts[1] + "=" * (-len(parts[1]) % 4)
            try:
                claims = json.loads(base64.urlsafe_b64decode(payload))
                email = str(claims.get("email") or "")
            except Exception:
                email = ""
                print("gmail_oauth: id_token claim parse skipped")
    return {
        "access_token": str(tokens.get("access_token") or ""),
        "refresh_token": str(tokens.get("refresh_token") or ""),
        "expiry": expiry.isoformat(),
        "email": email,
    }


def token_expired(expiry_iso: str) -> bool:
    if not expiry_iso:
        return True
    try:
        expiry = datetime.fromisoformat(expiry_iso)
    except ValueError:
        return True
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= expiry - timedelta(seconds=60)


def send_raw(access_token: str, mime_bytes: bytes) -> dict:
    body = json.dumps({"raw": b64url(mime_bytes)}).encode("utf-8")
    request = urllib.request.Request(
        GMAIL_SEND_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + access_token,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise AppError("ERR-gmail-send", f"Gmail API send failed ({exc.code})") from exc
    except Exception as exc:
        raise AppError("ERR-gmail-send", f"Gmail API unreachable: {exc}") from exc


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
