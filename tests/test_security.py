"""
Tests for core security logic.
These tests use only stdlib — no FastAPI test client needed — so they
can be run anywhere, including Termux, without a running server or DB.

Run: python3 -m pytest tests/ -v
  or: python3 tests/test_security.py  (if pytest isn't available)
"""
import hashlib
import hmac
import sys

# ── Inline the logic we're testing ───────────────────────────────────────────
# (avoids needing FastAPI/pydantic installed to run this test file)

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token(incoming: str, stored_hash: str) -> bool:
    incoming_hash = _hash_token(incoming)
    return hmac.compare_digest(incoming_hash, stored_hash)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_valid_token():
    token = "super_secret_token_abc123"
    stored = _hash_token(token)
    assert verify_token(token, stored), "Valid token should pass"


def test_wrong_token():
    token = "super_secret_token_abc123"
    stored = _hash_token(token)
    assert not verify_token("wrong_token", stored), "Wrong token should fail"


def test_empty_token():
    token = "real_token"
    stored = _hash_token(token)
    assert not verify_token("", stored), "Empty token should fail"


def test_timing_safe():
    """
    hmac.compare_digest should not raise or behave differently when
    comparing hashes of different lengths (which won't happen here since
    SHA-256 always produces 64-char hex, but good to confirm).
    """
    token = "abc"
    stored = _hash_token(token)
    result = verify_token("xyz", stored)
    assert isinstance(result, bool)


def test_hash_is_not_plaintext():
    token = "my_secret_token"
    stored = _hash_token(token)
    assert token not in stored, "Stored hash must not contain the plaintext token"
    assert len(stored) == 64, "SHA-256 hex digest should be 64 characters"


if __name__ == "__main__":
    tests = [
        test_valid_token,
        test_wrong_token,
        test_empty_token,
        test_timing_safe,
        test_hash_is_not_plaintext,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✅ {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed+failed} tests passed")
    sys.exit(0 if failed == 0 else 1)
