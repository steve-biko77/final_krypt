from abc import ABC, abstractmethod
from typing import List, Optional

from ..domain.entities import KYCDocument


class KYCDocumentRepository(ABC):
    @abstractmethod
    def save(self, doc: KYCDocument) -> KYCDocument:
        ...

    @abstractmethod
    def find_by_id(self, doc_id: str) -> Optional[KYCDocument]:
        ...

    @abstractmethod
    def find_latest_by_user_id(self, user_id: str) -> Optional[KYCDocument]:
        ...

    @abstractmethod
    def find_all_by_user_id(self, user_id: str) -> List[KYCDocument]:
        ...
