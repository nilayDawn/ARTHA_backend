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
    encrypts it with Fernet, saves to Supabase users table, caches it, and returns it.
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
                        raw_code = decrypt_code(row["telegram_link_code_encrypted"])
                        if raw_code:
                            remaining_seconds = int((expires_at - now).total_seconds())
                            result = {"code": raw_code, "expires_in_seconds": remaining_seconds}
                            set_cached_data(cache_key, result, ttl_seconds=min(60, remaining_seconds))
                            return result
        except Exception as e:
            print(f"[Telegram Auth] DB lookup error (migration needed?): {e}")

    # Generate new code
    new_code = f"FP-{secrets.randbelow(9000) + 1000}"
    encrypted_code = encrypt_code(new_code)
    expires_at = now + timedelta(minutes=10)

    try:
        supabase_admin.table("users").update({
            "telegram_link_code_encrypted": encrypted_code,
            "telegram_link_code_expires_at": expires_at.isoformat()
        }).eq("id", user_id).execute()
    except Exception as e:
        print(f"[Telegram Auth] DB update error (migration needed?): {e}")

    result = {"code": new_code, "expires_in_seconds": 600}
    set_cached_data(cache_key, result, ttl_seconds=60)
    return result

def verify_link_code(code: str) -> str | None:
    """
    Verifies incoming code from Telegram webhook against encrypted codes in Supabase.
    On success, clears the link code (single use) and returns user_id.
    """
    target_code = code.strip().upper()
    now_iso = datetime.now(UTC).isoformat()

    try:
        # Query users with active link codes
        res = (
            supabase_admin.table("users")
            .select("id", "telegram_link_code_encrypted", "telegram_link_code_expires_at")
            .not_.is_("telegram_link_code_encrypted", "null")
            .gt("telegram_link_code_expires_at", now_iso)
            .execute()
        )

        for row in res.data or []:
            enc_code = row.get("telegram_link_code_encrypted")
            if enc_code:
                decrypted = decrypt_code(enc_code)
                if decrypted and decrypted.upper() == target_code:
                    user_id = row["id"]
                    # Clear link code fields (single-use token)
                    supabase_admin.table("users").update({
                        "telegram_link_code_encrypted": None,
                        "telegram_link_code_expires_at": None
                    }).eq("id", user_id).execute()
                    invalidate_user_caches(user_id)
                    return user_id
    except Exception as e:
        print(f"[Telegram Auth] DB verification error: {e}")

    return None