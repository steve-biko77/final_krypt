import uuid

from django.conf import settings
from django.db import models


class AMLDecision(models.TextChoices):
    HARD_BLOCK = "HARD_BLOCK", "Blocage OFAC/EU"
    AUTO_APPROVED = "AUTO_APPROVED", "Approuvé automatiquement"
    AUTO_BLOCKED = "AUTO_BLOCKED", "Bloqué automatiquement"
    PENDING_REVIEW = "PENDING_REVIEW", "Révision admin requise"
    MANUALLY_APPROVED = "MANUALLY_APPROVED", "Approuvé manuellement"
    MANUALLY_REJECTED = "MANUALLY_REJECTED", "Rejeté manuellement"


class DocumentType(models.TextChoices):
    ID_CARD = "ID_CARD", "Carte d'identité"
    PASSPORT = "PASSPORT", "Passeport"
    RESIDENCE_PERMIT = "RESIDENCE_PERMIT", "Titre de séjour"


class KYCStatus(models.TextChoices):
    SUBMITTED = "SUBMITTED", "Soumis"
    ANALYZING = "ANALYZING", "En analyse IA"
    APPROVED = "APPROVED", "Validé (IA)"
    PENDING_REVIEW = "PENDING_REVIEW", "Validation manuelle requise"
    APPROVED_MANUAL = "APPROVED_MANUAL", "Validé manuellement"
    COMPLEMENT_REQUESTED = "COMPLEMENT_REQUESTED", "Complément demandé"
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
        max_length=24, choices=KYCStatus.choices, default=KYCStatus.ANALYZING
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # IA analysis
    analysis_score = models.FloatField(null=True, blank=True)
    analysis_details = models.JSONField(null=True, blank=True)

    # Admin review
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_kyc_documents",
    )
    review_comment = models.TextField(null=True, blank=True)

    class Meta:
        app_label = "compliance"
        db_table = "compliance_kyc_documents"
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"KYC({self.user_id}, {self.document_type}, {self.status})"


class AMLResultModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer_id = models.CharField(max_length=100, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="aml_results",
    )
    xgboost_score = models.FloatField()
    ofac_match = models.BooleanField(default=False)
    ofac_details = models.JSONField(null=True, blank=True)
    combined_decision = models.CharField(max_length=20, choices=AMLDecision.choices)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="aml_reviews",
    )
    review_decision = models.CharField(max_length=20, null=True, blank=True)
    audit_hash = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "compliance"
        db_table = "compliance_aml_results"
        ordering = ["-created_at"]

    def __str__(self):
        return f"AML({self.transfer_id}, {self.combined_decision})"
