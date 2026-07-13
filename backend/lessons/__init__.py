"""Evidence-backed lesson book for self-improving itinerary planning."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lessons.service import LessonBookService

__all__ = ["LessonBookService"]


def __getattr__(name: str):
    if name == "LessonBookService":
        from lessons.service import LessonBookService

        return LessonBookService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
