"""Basic tests for memory helpers."""

from memory.services.embedding_service import EmbeddingService
from memory.memory_manager import MemoryManager


def test_embedding_dimensions():
    service = EmbeddingService()
    vector = service.embed("Japan trip under 2 lakhs")
    assert len(vector) == service.dimensions


def test_thread_id_from_username():
    manager = MemoryManager(llm=None, db_pool=None)  # type: ignore[arg-type]
    assert manager.build_thread_id("Rahul") == "rahul_chat"
