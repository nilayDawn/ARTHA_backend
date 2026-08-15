import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from cryptography.fernet import Fernet

from app.core.cache import get_cached_data, invalidate_user_caches, set_cached_data
from app.core.config import settings
from app.core.database import supabase_admin


def _get_fernet_cipher() -> Fernet:
    """Derives a deterministic 32-byte Fernet key from SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY."""
    secret = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY or secrets.token_hex(32)
    key_bytes = hashlib.sha256(secret.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)

def encrypt_code(code: str) -> str:
    """Encrypts a plaintext link code into a secure ciphertext string."""
    cipher = _get_fernet_cipher()
    return cipher.encrypt(code.encode()).decode()

def decrypt_code(encrypted_code: str) -> str | None:
    """Decrypts ciphertext string back to plaintext code."""
    try:
        cipher = _get_fernet_cipher()
        return cipher.decrypt(encrypted_code.encode()).decode()
    except Exception:
        return None

def get_or_create_link_code(user_id: str, force_refresh: bool = False) -> dict:
    """
    Fetches active link code from cache/Supabase DB if valid.
    If force_refresh is True or the code is missing/expired, generates a new code,
    saves to Supabase users table, caches it, and returns it.
    """
    now = datetime.now(UTC)
    cache_key = f"telegram_link_code:{user_id}"

    if not force_refresh:
        cached = get_cached_data(cache_key)
        if cached is not None:
            return cached

        try:
            res = supabase_admin.table("users").select("telegram_link_code_encrypted", "telegram_link_code_expires_at").eq("id", user_id).execute()
            if res.data and res.data[0].get("telegram_link_code_encrypted"):
                row = res.data[0]
                expires_at_str = row.get("telegram_link_code_expires_at")
                if expires_at_str:
                    expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                    if expires_at > now:
                        stored_val = row["telegram_link_code_encrypted"]
                        # Try plain string first, fallback to Fernet decryption
                        raw_code = stored_val if stored_val.startswith("FP-") else decrypt_code(stored_val)
                        if raw_code:
                            remaining_seconds = int((expires_at - now).total_seconds())
                            result = {"code": raw_code, "expires_in_seconds": remaining_seconds}
                            set_cached_data(cache_key, result, ttl_seconds=min(60, remaining_seconds))
                            return result
        except Exception as e:
            print(f"[Telegram Auth] DB lookup error: {e}")

    # Generate new code
    new_code = f"FP-{secrets.randbelow(9000) + 1000}"
    expires_at = now + timedelta(minutes=10)

    try:
        # Store plain code directly to ensure zero key mismatch across environments
        supabase_admin.table("users").update({
            "telegram_link_code_encrypted": new_code,
            "telegram_link_code_expires_at": expires_at.isoformat()
        }).eq("id", user_id).execute()
    except Exception as e:
        print(f"[Telegram Auth] DB update error: {e}")

    result = {"code": new_code, "expires_in_seconds": 600}
    set_cached_data(cache_key, result, ttl_seconds=60)
    return result

def verify_link_code(code: str) -> str | None:
    """
    Verifies incoming code from Telegram webhook against stored codes in Supabase.
    On success, clears the link code (single use) and returns user_id.
    """
    target_code = code.strip().upper()
    now = datetime.now(UTC)

    try:
        # Query users with non-null active link codes
        res = (
            supabase_admin.table("users")
            .select("id", "telegram_link_code_encrypted", "telegram_link_code_expires_at")
            .not_.is_("telegram_link_code_encrypted", "null")
            .execute()
        )

        for row in res.data or []:
            stored_val = row.get("telegram_link_code_encrypted")
            exp_str = row.get("telegram_link_code_expires_at")
            
            if stored_val and exp_str:
                try:
                    exp_dt = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
                    if exp_dt > now:
                        # Match plain text code OR decrypted code
                        match_code = stored_val if stored_val.startswith("FP-") else decrypt_code(stored_val)
                        if match_code and match_code.strip().upper() == target_code:
                            user_id = row["id"]
                            # Clear link code fields (single-use token)
                            supabase_admin.table("users").update({
                                "telegram_link_code_encrypted": None,
                                "telegram_link_code_expires_at": None
                            }).eq("id", user_id).execute()
                            invalidate_user_caches(user_id)
                            return user_id
                except Exception as parse_err:
                    print(f"[Telegram Auth] Expiration parse error for row {row.get('id')}: {parse_err}")
    except Exception as e:
        print(f"[Telegram Auth] DB verification error: {e}")

    return None