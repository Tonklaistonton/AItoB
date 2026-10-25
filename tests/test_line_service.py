"""Self-check test for LINE bot gateway signature and webhook security."""
import base64
import hashlib
import hmac
import sys
from pathlib import Path

# Add project/line-bot to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "project" / "line-bot"))
from line_service import verify_signature

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

if __name__ == "__main__":
    test_signature_verification()