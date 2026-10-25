"""Self-check test for LINE bot gateway signature and webhook security."""
import base64
import hashlib
import hmac
import sys
from pathlib import Path
from unittest.mock import patch

# Add project/line-bot to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "project" / "line-bot"))
from line_service import verify_signature, verify_admin_auth

def test_signature_verification():
    secret = "test_channel_secret_123"
    body = b'{"events":[{"type":"message","message":{"type":"text","text":"hello"}}]}'

    # Correct HMAC-SHA256 signature
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    valid_sig = base64.b64encode(mac).decode("utf-8")

    # 1. Valid signature passes
    assert verify_signature(secret, body, valid_sig) is True, "Valid signature must pass"

    # 2. Tampered body fails
    assert verify_signature(secret, b'tampered', valid_sig) is False, "Tampered body must fail"

    # 3. Wrong signature fails
    assert verify_signature(secret, body, "bad_signature") is False, "Wrong signature must fail"

    # 4. Fail-closed: empty secret fails
    assert verify_signature("", body, valid_sig) is False, "Empty secret must fail-closed"

    # 5. Fail-closed: empty signature fails
    assert verify_signature(secret, body, "") is False, "Empty signature must fail-closed"

    print("ALL ASSERTIONS PASSED: verify_signature is secure and fail-closed.")

def test_admin_auth_verification():
    secret = "test_channel_secret_456"
    api_key = "test_aitob_key_789"

    with patch("line_service.CHANNEL_SECRET", secret), patch("line_service.AITOB_API_KEY", api_key):
        # 1. Valid Bearer tokens pass
        assert verify_admin_auth(f"Bearer {secret}") is True, "Valid secret Bearer must pass"
        assert verify_admin_auth(f"Bearer {api_key}") is True, "Valid API key Bearer must pass"

        # 2. Invalid Bearer fails
        assert verify_admin_auth("Bearer wrong_token") is False, "Invalid token must fail"

        # 3. Malformed auth headers fail
        assert verify_admin_auth("") is False, "Empty header must fail"
        assert verify_admin_auth("Basic dXNlcjpwYXNz") is False, "Non-Bearer scheme must fail"
        assert verify_admin_auth("Bearer") is False, "Missing token must fail"

    print("ALL ASSERTIONS PASSED: verify_admin_auth is secure and fail-closed.")

if __name__ == "__main__":
    test_signature_verification()
    test_admin_auth_verification()
