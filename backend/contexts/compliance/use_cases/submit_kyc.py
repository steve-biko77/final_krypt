from dataclasses import dataclass

from ..domain.entities import DocumentType, KYCDocument, KYCStatus
from ..domain.exceptions import KYCAlreadyApprovedError
from ..ports.kyc_repository import KYCDocumentRepository
from ..ports.storage_service import StorageService


@dataclass
class SubmitKYCInput:
    user_id: str
    document_type: DocumentType
    file_data: bytes
    filename: str
    content_type: str


class SubmitKYCUseCase:
    def __init__(self, kyc_repo: KYCDocumentRepository, storage: StorageService):
        self._kyc_repo = kyc_repo
        self._storage = storage

    def execute(self, data: SubmitKYCInput) -> KYCDocument:
        existing = self._kyc_repo.find_latest_by_user_id(data.user_id)
        if existing and existing.status == KYCStatus.APPROVED:
            raise KYCAlreadyApprovedError("KYC already approved for this user")

        file_path = self._storage.upload_file(
            file_data=data.file_data,
            filename=data.filename,
            content_type=data.content_type,
            prefix=data.user_id,
        )

        doc = KYCDocument(
            user_id=data.user_id,
            document_type=data.document_type,
            file_path=file_path,
            status=KYCStatus.PENDING,
        )
        return self._kyc_repo.save(doc)
