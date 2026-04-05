import json
import logging
import os

_STORE = "data/conversations.json"
logger = logging.getLogger(__name__)


def _load_store() -> dict:
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(_STORE):
        logger.debug("[memory] Store file not found, starting fresh")
        return {}
    try:
        with open(_STORE) as f:
            store = json.load(f)
        logger.debug("[memory] Store loaded — %d user(s)", len(store))
        return store
    except Exception as e:
        logger.error("[memory] Failed to read store file: %s", e)
        return {}


def _save_store(store: dict) -> None:
    try:
        with open(_STORE, "w") as f:
            json.dump(store, f, indent=2)
        logger.debug("[memory] Store saved — %d user(s)", len(store))
    except Exception as e:
        logger.error("[memory] Failed to write store file: %s", e)


def load_messages(email: str) -> list[dict]:
    msgs = _load_store().get(email, [])
    result = [
        {
            "role": m["role"],
            "content": m["content"],
            "previews": m.get("previews", []),
        }
        for m in msgs
    ]
    logger.info("[memory] Loaded %d messages for %s", len(result), email)
    return result


def save_messages(email: str, messages: list[dict]) -> None:
    store = _load_store()
    store[email] = [
        {
            "role": m["role"],
            "content": m["content"],
            "previews": m.get("previews", []),
        }
        for m in messages
    ]
    _save_store(store)
    logger.info("[memory] Saved %d messages for %s", len(messages), email)


def clear_messages(email: str) -> None:
    store = _load_store()
    if email in store:
        del store[email]
        _save_store(store)
        logger.info("[memory] Cleared conversation for %s", email)
    else:
        logger.info("[memory] Clear requested for %s but no history found", email)
