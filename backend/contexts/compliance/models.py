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
    ESCALATED = "ESCALATED", "Escaladé (revue niveau 2)"


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
    # KRYP-22 v2 — architecture de décision 4 couches (seuils_production.md)
    is_new_beneficiary = models.BooleanField(default=False)
    sender_tx_count_30d = models.IntegerField(default=0)
    tag_ml_score = models.FloatField(default=0.0)
    triggered_rules = models.JSONField(default=list, blank=True)
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


class AMLAdminAuditLog(models.Model):
    """KRYP-31 — Trace immuable de chaque décision admin sur un transfert en
    revue AML (Fig. 10, points 4/5). ``motif`` reste STRICTEMENT interne : il ne
    doit jamais être injecté tel quel dans une notification utilisateur (voir
    DecideAMLReviewUseCase)."""

    class Action(models.TextChoices):
        REQUEST_DOCS = "REQUEST_DOCS", "Documents complémentaires demandés"
        APPROVE = "APPROVE", "Approuvé (1er niveau)"
        REJECT = "REJECT", "Rejeté (1er niveau)"
        ESCALATE = "ESCALATE", "Escaladé"
        ESCALATED_APPROVE = "ESCALATED_APPROVE", "Approuvé (2e niveau)"
        ESCALATED_REJECT = "ESCALATED_REJECT", "Rejeté (2e niveau)"
        # KRYP-31 (partie 2/3) — section HARD_BLOCK (image 2, section 4) : ce ne
        # sont PAS des décisions (le blocage est déjà acté, le statut du
        # transfert ne change pas), seulement des actions de dossier — réutilise
        # le même journal d'audit plutôt que d'en créer un second.
        DOCUMENT = "DOCUMENT", "Cas documenté"
        FREEZE_ACCOUNT = "FREEZE_ACCOUNT", "Compte gelé"
        TRACFIN_REPORT_GENERATED = "TRACFIN_REPORT_GENERATED", "Déclaration TRACFIN générée"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_id = models.CharField(max_length=100, db_index=True)
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="aml_admin_decisions",
    )
    action = models.CharField(max_length=24, choices=Action.choices)
    # Motif (REJECT, obligatoire) ou commentaire (ESCALATE, optionnel) — interne
    # uniquement, jamais exposé à l'utilisateur final.
    motif = models.TextField(blank=True, default="")
    # Hash de la transaction on-chain de CETTE décision (log_critical_event) —
    # null pour ESCALATE (Fig. 10 : pas de log on-chain à cette étape précise).
    tx_hash = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "compliance"
        db_table = "compliance_aml_admin_audit_log"
        ordering = ["-created_at"]

    def __str__(self):
        return f"AMLAdminAuditLog({self.transaction_id}, {self.action}, admin={self.admin_id})"


class AMLSupportingDocumentModel(models.Model):
    """KRYP-31 — Document complémentaire resoumis par l'utilisateur après une
    demande admin (AWAITING_DOCS -> AML_PENDING_REVIEW), symétrique aux
    documents KYC (KYCDocumentModel) mais scopé à un dossier AML plutôt qu'à la
    vérification d'identité."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_id = models.CharField(max_length=100, db_index=True)
    file_path = models.CharField(max_length=500)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "compliance"
        db_table = "compliance_aml_supporting_documents"
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"AMLSupportingDocument({self.transaction_id})"


class TracfinReportModel(models.Model):
    """KRYP-31 (partie 2/3) — Déclaration TRACFIN générée pour un cas HARD_BLOCK
    (image 2, section 4). Distinct de ``AMLSupportingDocumentModel`` : celui-ci
    est un document RESOUMIS PAR L'UTILISATEUR (preuve), celui-là un document
    GÉNÉRÉ PAR UN ADMIN (déclaration réglementaire) — sémantique différente,
    d'où un ``admin`` FK ici et pas là-bas."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_id = models.CharField(max_length=100, db_index=True)
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="generated_tracfin_reports",
    )
    file_path = models.CharField(max_length=500)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "compliance"
        db_table = "compliance_tracfin_reports"
        ordering = ["-generated_at"]

    def __str__(self):
        return f"TracfinReport({self.transaction_id})"


class AuditQueueModel(models.Model):
    """
    Couche 4 — file d'audit a posteriori (seuils_production.md §2).

    Échantillon aléatoire de transactions AUTO_APPROVED sélectionnées pour une
    review humaine différée (contrôle détectif, non préventif). `tag_ml_score`
    est conservé pour permettre un tri/priorisation futur de la file par un
    backoffice.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="aml_audit_queue_items",
    )
    transfer_id = models.CharField(max_length=100, db_index=True)
    aml_result_id = models.CharField(max_length=100)
    tag_ml_score = models.FloatField(default=0.0)
    reviewed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "compliance"
        db_table = "compliance_audit_queue"
        ordering = ["-created_at"]

    def __str__(self):
        return f"AuditQueue({self.transfer_id}, reviewed={self.reviewed})"
