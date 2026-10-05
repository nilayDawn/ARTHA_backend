from app.adapters.cache.memory_cache import MemoryCacheAdapter
from app.adapters.database.memory_repo import InMemoryTransactionRepository, InMemoryUserRepository
from app.services.telegram_service import TelegramService


def test_telegram_link_code_direct_lookup():
    user_repo = InMemoryUserRepository()
    cache = MemoryCacheAdapter()
    user_repo.upsert_user(user_id="user_99", email="test@artha.ai", full_name="Nilay")

    telegram_service = TelegramService(
        user_repo=user_repo,
        agent_service=None,
        doc_service=None,
        tx_service=None,
        cache=cache,
    )

    code_data = telegram_service.get_or_create_link_code("user_99")
    code = code_data["code"]
    assert code.startswith("FP-")

    # Verify and bind using direct lookup
    bound_user_id = telegram_service.verify_and_bind_code(code, chat_id="987654321")
    assert bound_user_id == "user_99"

    # User chat_id is now bound
    user = user_repo.get_user_by_telegram_id("987654321")
    assert user is not None
    assert user["id"] == "user_99"

    # Code is single-use: second attempt must fail
    second_try = telegram_service.verify_and_bind_code(code, chat_id="987654321")
    assert second_try is None
