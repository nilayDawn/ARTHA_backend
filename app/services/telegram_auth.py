#n in-memory or DB store for active codes.
import secrets
import time

# In-memory store: { code: {"user_id": str, "expires_at": float} }
LINK_CODES: dict[str, dict] = {}

def generate_link_code(user_id: str) -> str:
    # Clean expired
    now = time.time()
    expired = [k for k, v in LINK_CODES.items() if v["expires_at"] < now]
    for k in expired:
        del LINK_CODES[k]

    code = f"FP-{secrets.randbelow(9000) + 1000}"
    LINK_CODES[code] = {
        "user_id": user_id,
        "expires_at": now + 600 # 10 minutes valid
    }
    return code

def verify_link_code(code: str) -> str | None:
    data = LINK_CODES.get(code.upper().strip())
    if not data:
        return None
    if time.time() > data["expires_at"]:
        del LINK_CODES[code.upper().strip()]
        return None
    
    user_id = data["user_id"]
    del LINK_CODES[code.upper().strip()] # Single use
    return user_id