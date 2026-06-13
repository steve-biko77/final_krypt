import uuid
from typing import List, Optional

from ...domain.entities import DocumentType, KYCDocument, KYCStatus
from ...models import KYCDocumentModel
from ...ports.kyc_repository import KYCDocumentRepository


class DjangoORMKYCRepository(KYCDocumentRepository):
    def save(self, doc: KYCDocument) -> KYCDocument:
        try:
            obj = KYCDocumentModel.objects.get(pk=uuid.UUID(doc.id))
            obj.document_type = doc.document_type.value
            obj.file_path = doc.file_path
            obj.status = doc.status.value
            obj.reviewed_at = doc.reviewed_at
            obj.save()
        except KYCDocumentModel.DoesNotExist:
            obj = KYCDocumentModel(
                id=uuid.UUID(doc.id),
                user_id=uuid.UUID(doc.user_id),
                document_type=doc.document_type.value,
                file_path=doc.file_path,
                status=doc.status.value,
            )
            obj.save()
        return self._to_entity(obj)

    def find_by_id(self, doc_id: str) -> Optional[KYCDocument]:
        try:
            return self._to_entity(KYCDocumentModel.objects.get(pk=doc_id))
        except (KYCDocumentModel.DoesNotExist, ValueError):
            return None

    def find_latest_by_user_id(self, user_id: str) -> Optional[KYCDocument]:
        obj = KYCDocumentModel.objects.filter(user_id=user_id).first()
        return self._to_entity(obj) if obj else None

    def find_all_by_user_id(self, user_id: str) -> List[KYCDocument]:
        return [
            self._to_entity(obj)
            for obj in KYCDocumentModel.objects.filter(user_id=user_id)
        ]

    def _to_entity(self, obj: KYCDocumentModel) -> KYCDocument:
        return KYCDocument(
            id=str(obj.pk),
            user_id=str(obj.user_id),
            document_type=DocumentType(obj.document_type),
            file_path=obj.file_path,
            status=KYCStatus(obj.status),
            submitted_at=obj.submitted_at,
            reviewed_at=obj.reviewed_at,
        )
