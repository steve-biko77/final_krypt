from typing import List, Optional

from ..domain.entities import KYCDocument
from ..ports.kyc_repository import KYCDocumentRepository


class GetKYCStatusUseCase:
    def __init__(self, kyc_repo: KYCDocumentRepository):
        self._kyc_repo = kyc_repo

    def execute(self, user_id: str) -> Optional[KYCDocument]:
        return self._kyc_repo.find_latest_by_user_id(user_id)

    def execute_all(self, user_id: str) -> List[KYCDocument]:
        return self._kyc_repo.find_all_by_user_id(user_id)
