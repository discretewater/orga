from abc import ABC, abstractmethod
from typing import List
from orga.model import Document

class FetchStrategy(ABC):
    @abstractmethod
    async def fetch(self, url: str) -> Document:
        pass
