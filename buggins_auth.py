"""Authentication gate for the standalone Buggins app.

Authentication requests are made by the Streamlit server. A returned access
token is verified server-side before the baby log is allowed to render.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
import time

import httpx
import streamlit as st


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
class AuthConfigurationError(RuntimeError):
    """Raised when the protected app is missing a required auth setting."""


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str


def auth_required() -> bool:
    return (os.getenv("BUGGINS_AUTH_REQUIRED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def require_auth() -> AuthUser | None:
    """Stop the Streamlit run unless a verified, approved user is signed in."""
    if not auth_required():
        return None

    # The standalone login must not expose Streamlit's multipage navigation or
    # deployment controls while the protected page is stopped at this gate.
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"], [data-testid="stSidebarNav"],
        [data-testid="stHeaderActionElements"], .stDeployButton {
            display: none !important;
        }
        [data-testid="stAppViewContainer"] > .main {
            padding-top: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    try:
        url, public_key, allowed_emails, allowed_user_ids = _configuration()
    except AuthConfigurationError as exc:
        st.error(str(exc))
        st.stop()

    existing = _session_user()
    if existing and _session_is_current():
        return existing
    linked = _magic_link_user(url, public_key, allowed_emails, allowed_user_ids)
    if linked:
        return linked
    _native_email_auth(url, public_key, allowed_emails, allowed_user_ids)
    st.stop()


def _native_email_auth(
    url: str,
    public_key: str,
    allowed_emails: set[str],
    allowed_user_ids: set[str],
) -> None:
    """Render a reliable server-assisted magic-link login inside Streamlit."""
    st.markdown(
        """
        <style>
        .buggins-login-title { text-align: center; margin-top: 4rem; }
        .buggins-login-title h1 { margin-bottom: .35rem; }
        .buggins-login-title p { color: #b9c9df; margin-bottom: 2rem; }
        div[data-testid="stForm"] {
            max-width: 430px; margin: 0 auto; padding: 1.6rem 1.5rem 1.25rem;
            border: 1px solid rgba(135, 177, 255, .62); border-radius: 26px;
            background: linear-gradient(160deg, #132744, #0b1930 60%, #10162d);
            box-shadow: 0 22px 60px rgba(0, 5, 20, .42);
        }
        </style>
        <div class="buggins-login-title">
          <div style="font-size:42px">🌙</div>
          <h1>Welcome to Buggins</h1>
          <p>Your private family log. Sign in securely to continue.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    default_email = sorted(allowed_emails)[0] if len(allowed_emails) == 1 else ""
    with st.form("buggins-request-link"):
        email = st.text_input(
            "Approved email address",
            value=default_email,
            placeholder="you@example.com",
        ).strip().lower()
        submitted = st.form_submit_button(
            "Email me a secure sign-in link", type="primary", use_container_width=True
        )
    if not submitted:
        return
    if not email or email not in allowed_emails:
        st.error("That email address has not been approved for Buggins.")
        return
    callback_url = _auth_callback_url()
    try:
        response = httpx.post(
            url.rstrip("/") + "/auth/v1/otp",
            params={"redirect_to": callback_url},
            headers={"apikey": public_key, "Content-Type": "application/json"},
            json={"email": email, "create_user": True},
            timeout=15,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        st.error("Buggins could not send the sign-in email. Please wait a moment and try again.")
        return
    st.success(
        "Your secure Buggins sign-in link has been emailed. Open that link on this device to continue."
    )


def _auth_callback_url() -> str:
    public_url = (os.getenv("BUGGINS_PUBLIC_URL") or "").strip().rstrip("/")
    if not public_url:
        railway_domain = (os.getenv("RAILWAY_PUBLIC_DOMAIN") or "").strip()
        public_url = f"https://{railway_domain}" if railway_domain else "http://127.0.0.1:8501"
    return public_url + "/app/static/auth-callback.html"


def _magic_link_user(
    url: str,
    public_key: str,
    allowed_emails: set[str],
    allowed_user_ids: set[str],
) -> AuthUser | None:
    """Accept the short-lived token placed by our same-origin auth callback."""
    try:
        token = str(st.context.cookies.get("buggins_access_token") or "").strip()
        expires_at = _as_float(st.context.cookies.get("buggins_expires_at"))
    except (AttributeError, RuntimeError):
        return None
    if not token or expires_at <= time.time() + 30:
        return None
    try:
        user = _verify_user(url, public_key, token)
        _ensure_approved(user, allowed_emails, allowed_user_ids)
    except (httpx.HTTPError, ValueError, PermissionError):
        return None
    _store_session(user, token, expires_at)
    return user


def current_user() -> AuthUser | None:
    if not auth_required() or not _session_is_current():
        return None
    return _session_user()


def _configuration() -> tuple[str, str, set[str], set[str]]:
    secrets = _read_section(os.path.join(ROOT_DIR, ".streamlit", "secrets.toml"), "supabase")
    url = (os.getenv("SUPABASE_URL") or str(secrets.get("url") or "")).strip()
    auth_key = (
        os.getenv("SUPABASE_PUBLISHABLE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
        # The standalone flow below is entirely server-assisted; this fallback
        # is never embedded in HTML or sent to the browser.
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or str(secrets.get("publishable_key") or secrets.get("anon_key") or "")
    ).strip()
    allowed_emails = _csv_set(os.getenv("BUGGINS_ALLOWED_EMAILS"), lower=True)
    allowed_user_ids = _csv_set(os.getenv("BUGGINS_ALLOWED_USER_IDS"), lower=False)

    if not url:
        raise AuthConfigurationError("Buggins sign-in is not configured: SUPABASE_URL is missing.")
    if not auth_key:
        raise AuthConfigurationError(
            "Buggins sign-in is not configured: a Supabase authentication key is missing."
        )
    if not allowed_emails and not allowed_user_ids:
        raise AuthConfigurationError(
            "Buggins is locked because no approved users have been configured."
        )
    return url, auth_key, allowed_emails, allowed_user_ids


def _verify_user(url: str, public_key: str, token: str) -> AuthUser:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    cached_hash = str(st.session_state.get("_buggins_token_hash") or "")
    verified_at = _as_float(st.session_state.get("_buggins_verified_at"))
    cached_user = _session_user()
    if cached_user and token_hash == cached_hash and time.time() - verified_at < 60:
        return cached_user

    response = httpx.get(
        url.rstrip("/") + "/auth/v1/user",
        headers={"apikey": public_key, "Authorization": f"Bearer {token}"},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    user_id = str(data.get("id") or "").strip()
    email = str(data.get("email") or "").strip().lower()
    if not user_id or not email:
        raise ValueError("The signed-in Supabase account is incomplete.")
    st.session_state["_buggins_token_hash"] = token_hash
    st.session_state["_buggins_verified_at"] = time.time()
    return AuthUser(id=user_id, email=email)


def _ensure_approved(user: AuthUser, allowed_emails: set[str], allowed_user_ids: set[str]) -> None:
    if user.email in allowed_emails or user.id in allowed_user_ids:
        return
    raise PermissionError("This account has not been approved for Buggins.")


def _store_session(user: AuthUser, token: str, expires_at: float) -> None:
    st.session_state["_buggins_user"] = {"id": user.id, "email": user.email}
    st.session_state["_buggins_access_token"] = token
    st.session_state["_buggins_expires_at"] = expires_at


def _clear_session() -> None:
    for key in (
        "_buggins_user",
        "_buggins_access_token",
        "_buggins_expires_at",
        "_buggins_token_hash",
        "_buggins_verified_at",
    ):
        st.session_state.pop(key, None)


def _session_user() -> AuthUser | None:
    raw = st.session_state.get("_buggins_user")
    if not isinstance(raw, dict):
        return None
    user_id = str(raw.get("id") or "").strip()
    email = str(raw.get("email") or "").strip().lower()
    return AuthUser(id=user_id, email=email) if user_id and email else None


def _session_is_current() -> bool:
    expires_at = _as_float(st.session_state.get("_buggins_expires_at"))
    return bool(_session_user() and expires_at > time.time() + 30)


def _friendly_auth_error(exc: Exception) -> str:
    if isinstance(exc, PermissionError):
        return str(exc)
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {401, 403}:
        return "Your Buggins sign-in has expired. Please sign in again."
    return "Buggins could not verify this sign-in. Please try again."


def _csv_set(value: str | None, *, lower: bool) -> set[str]:
    items = {item.strip() for item in str(value or "").split(",") if item.strip()}
    return {item.lower() for item in items} if lower else items


def _as_float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _read_section(path: str, section: str) -> dict[str, str]:
    values: dict[str, str] = {}
    active = False
    try:
        with open(path, "r") as file:
            for raw_line in file:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    active = line == f"[{section}]"
                    continue
                if active and "=" in line:
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        pass
    return values
