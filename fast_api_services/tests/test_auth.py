"""Unit tests for JWT auth dependency (no DB / Redis needed)."""
import pytest
from unittest.mock import patch
from jose import jwt
from fastapi import HTTPException


TEST_SECRET = "test-secret-key-1234"
TEST_ALGORITHM = "HS256"


def _make_token(user_id: int, extra: dict = {}) -> str:
    payload = {"user_id": user_id, "username": "testuser", **extra}
    return jwt.encode(payload, TEST_SECRET, algorithm=TEST_ALGORITHM)


def _decode(token: str):
    from fast_api_services.auth import _decode_token
    return _decode_token(token)


class TestJWTDecoding:
    def test_valid_token_returns_payload(self):
        token = _make_token(42)
        with patch("fast_api_services.auth.get_settings") as mock_settings:
            mock_settings.return_value.secret_key = TEST_SECRET
            mock_settings.return_value.jwt_algorithm = TEST_ALGORITHM
            payload = _decode(token)
        assert payload.user_id == 42
        assert payload.username == "testuser"

    def test_invalid_token_raises_401(self):
        with patch("fast_api_services.auth.get_settings") as mock_settings:
            mock_settings.return_value.secret_key = TEST_SECRET
            mock_settings.return_value.jwt_algorithm = TEST_ALGORITHM
            with pytest.raises(HTTPException) as exc_info:
                _decode("not.a.valid.token")
        assert exc_info.value.status_code == 401

    def test_token_missing_user_id_raises_401(self):
        token = jwt.encode({"username": "nouid"}, TEST_SECRET, algorithm=TEST_ALGORITHM)
        with patch("fast_api_services.auth.get_settings") as mock_settings:
            mock_settings.return_value.secret_key = TEST_SECRET
            mock_settings.return_value.jwt_algorithm = TEST_ALGORITHM
            with pytest.raises(HTTPException) as exc_info:
                _decode(token)
        assert exc_info.value.status_code == 401
        assert "user_id" in exc_info.value.detail
