"""Storage-abstraction tests using the in-memory backend (conftest sets it)."""
import pytest

from apps.diary.storage import MemoryStorage, get_storage, reset_storage_cache


def test_conftest_selects_memory_backend():
    assert isinstance(get_storage(), MemoryStorage)


def test_put_get_delete_roundtrip():
    store = get_storage()
    store.put("u1/a.jpg", b"hello", "image/jpeg")
    assert store.get("u1/a.jpg") == b"hello"
    store.delete("u1/a.jpg")
    with pytest.raises(FileNotFoundError):
        store.get("u1/a.jpg")


def test_singleton_is_stable_within_backend():
    assert get_storage() is get_storage()


def test_reset_cache_makes_a_fresh_store(settings):
    reset_storage_cache()
    a = get_storage()
    a.put("k", b"x")
    reset_storage_cache()
    b = get_storage()
    assert a is not b
    with pytest.raises(FileNotFoundError):
        b.get("k")
