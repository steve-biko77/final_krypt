import uuid

from django.conf import settings
from django.db import models


class Operator(models.TextChoices):
    MTN_MOMO = "MTN_MOMO", "MTN Mobile Money"
    ORANGE_MONEY = "ORANGE_MONEY", "Orange Money"


class TransactionStatus(models.TextChoices):
    DRAFT = "DRAFT", "Brouillon"
    PENDING_AML = "PENDING_AML", "En attente scoring AML"
    AML_BLOCKED = "AML_BLOCKED", "Bloqué par AML"
    AML_PENDING_REVIEW = "AML_PENDING_REVIEW", "Révision AML requise"
    PROCESSING = "PROCESSING", "Paiement en cours"
    ESCROWED = "ESCROWED", "Fonds sécurisés (escrow)"
    ESCROW_FAILED = "ESCROW_FAILED", "Échec verrouillage escrow"
    DELIVERED = "DELIVERED", "Livré"
    PAYMENT_FAILED = "PAYMENT_FAILED", "Paiement échoué"
    PAYOUT_FAILED = "PAYOUT_FAILED", "Échec payout mobile money"
    CANCELLED = "CANCELLED", "Annulé"
    AWAITING_DOCS = "AWAITING_DOCS", "Documents complémentaires requis"
    ESCALATED = "ESCALATED", "Escaladé (revue niveau 2)"


class TransactionModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    beneficiary_name = models.CharField(max_length=200)
    beneficiary_country = models.CharField(max_length=2)
    momo_number = models.CharField(max_length=30)
    operator = models.CharField(max_length=20, choices=Operator.choices)
    amount_eur = models.DecimalField(max_digits=10, decimal_places=2)
    fees_eur = models.DecimalField(max_digits=10, decimal_places=2)
    amount_xaf = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(
        max_length=24,
        choices=TransactionStatus.choices,
        default=TransactionStatus.DRAFT,
    )
    aml_result_id = models.CharField(max_length=100, null=True, blank=True)
    stripe_payment_intent_id = models.CharField(
        max_length=255, null=True, blank=True, db_index=True
    )
    escrow_tx_hash = models.CharField(max_length=100, null=True, blank=True)
    # Timestamp précis de l'entrée en statut ESCROWED — source non-ambiguë pour
    # le job timeout 24h (ne pas réutiliser updated_at, modifié par d'autres saves).
    escrowed_at = models.DateTimeField(null=True, blank=True)
    # Référence payout MTN/Orange (pour polling de statut / traçabilité).
    payout_reference = models.CharField(max_length=100, null=True, blank=True)
    # KRYP-31 — hash de la transaction on-chain de la DÉCISION admin elle-même
    # (log_critical_event sur approve/reject), distinct de escrow_tx_hash (verrou
    # de fonds). Jamais renseigné pour ESCALATE (Fig. 10 : pas de log on-chain à
    # cette étape, seulement à la décision finale).
    admin_review_tx_hash = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "transfer"
        db_table = "transfer_transactions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Transaction({self.id}, {self.status}, {self.amount_eur} EUR)"


class SavedBeneficiaryModel(models.Model):
    """Carnet de contacts — bénéficiaire enregistré par un utilisateur (opt-in
    explicite, jamais de sauvegarde automatique silencieuse)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_beneficiaries",
    )
    beneficiary_name = models.CharField(max_length=200)
    beneficiary_country = models.CharField(max_length=2)
    momo_number = models.CharField(max_length=30)
    operator = models.CharField(max_length=20, choices=Operator.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    # Nul tant que jamais réutilisé depuis l'enregistrement — cf.
    # initiate_transfer (mis à jour si le transfert correspond, par numéro, à
    # une entrée déjà enregistrée), jamais renseigné à la création.
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "transfer"
        db_table = "transfer_saved_beneficiaries"
        # Tri réel (nulls_last) fait dans le repository via une expression F() —
        # Meta.ordering ne sert ici que de filet de sécurité par défaut, les
        # NULL de last_used_at se retrouveraient sinon en tête sous Postgres
        # (NULLS FIRST par défaut en DESC), l'inverse de ce qui est voulu.
        ordering = ["-created_at"]

    def __str__(self):
        return f"SavedBeneficiary({self.beneficiary_name}, {self.momo_number})"
