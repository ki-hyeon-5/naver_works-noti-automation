"""Common parser interface for source-specific alarm text."""

from abc import ABC, abstractmethod

from ..models import ParseBatchResult


class BaseParser(ABC):
    @abstractmethod
    def parse(self, text: str) -> ParseBatchResult:
        """Parse clipboard text without external I/O."""
