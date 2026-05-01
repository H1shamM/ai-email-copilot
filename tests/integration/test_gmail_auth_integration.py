"""Integration tests for Gmail OAuth flow.

These tests hit real Google OAuth and require a valid `token.pickle` (or
will trigger a browser-based consent flow). Run explicitly with:

    pytest -m integration tests/integration/test_gmail_auth_integration.py
"""

import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.path.exists("credentials.json"),
        reason="Requires credentials.json from Google Cloud Console",
    ),
]


def test_get_credentials_returns_valid_creds():
    """Calling get_credentials() returns an object with .valid=True after auth."""
    from app.gmail.auth import get_credentials

    creds = get_credentials()
    assert creds is not None
    assert creds.valid is True


def test_can_build_gmail_service():
    """The credentials are usable for instantiating a Gmail API client."""
    from app.gmail.service import get_email_service

    service = get_email_service()
    assert service is not None
