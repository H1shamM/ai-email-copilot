import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
]

_AUTH_EXPIRED_MSG = (
    "Gmail authorization expired or revoked — re-run OAuth "
    "(delete token.pickle and re-authenticate)."
)


def get_credentials():
    creds = None

    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # A revoked/expired refresh token raises RefreshError, which would
            # otherwise bubble up as an opaque failure. Convert it to a clear,
            # actionable RuntimeError that the Telegram handlers surface.
            try:
                creds.refresh(Request())
            except RefreshError as exc:
                raise RuntimeError(_AUTH_EXPIRED_MSG) from exc
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    return creds


def gmail_token_status() -> tuple[bool, str]:
    """Non-interactively check the stored Gmail token: (ok, detail).

    Never launches the browser OAuth flow, so it's safe to call from a scheduled
    health check. Refreshes (and persists) an expired-but-refreshable token as a
    side effect; reports the failure detail when the refresh token is dead.
    """
    if not os.path.exists("token.pickle"):
        return False, "no token.pickle"
    try:
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    except Exception as exc:  # noqa: BLE001 — corrupt/unreadable token file
        return False, f"unreadable token.pickle: {exc}"

    if creds.valid:
        return True, "valid"
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError as exc:
            return False, f"refresh failed: {exc}"
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)
        return True, "refreshed"
    return False, "invalid (no refresh token)"
