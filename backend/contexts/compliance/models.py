import uuid

from django.conf import settings
from django.db import models


class DocumentType(models.TextChoices):
    ID_CARD = "ID_CARD", "Carte d'identité"
    PASSPORT = "PASSPORT", "Passeport"
    RESIDENCE_PERMIT = "RESIDENCE_PERMIT", "Titre de séjour"


class KYCStatus(models.TextChoices):
    PENDING = "PENDING", "En attente"
    APPROVED = "APPROVED", "Approuvé"
    REJECTED = "REJECTED", "Rejeté"


class KYCDocumentModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="kyc_documents",
    )
    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    file_path = models.CharField(max_length=500)
    status = models.CharField(
        max_length=10, choices=KYCStatus.choices, default=KYCStatus.PENDING
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "compliance"
        db_table = "compliance_kyc_documents"
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"KYC({self.user_id}, {self.document_type}, {self.status})"
