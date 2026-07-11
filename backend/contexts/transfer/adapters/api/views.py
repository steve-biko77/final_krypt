from decimal import Decimal, InvalidOperation

import stripe
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from contexts.compliance.adapters.orm.django_aml_repository import DjangoORMAMLRepository
from contexts.compliance.adapters.orm.django_audit_queue_repository import DjangoAuditQueueRepository
from contexts.compliance.adapters.services.django_transaction_history_service import (
    DjangoTransactionHistoryService,
)
from contexts.compliance.adapters.services.mock_sanctions_checker import MockSanctionsChecker
from contexts.compliance.adapters.services.scorer_factory import get_configured_scorer
from contexts.compliance.use_cases.score_aml import ScoreAMLUseCase

from ...adapters.orm.django_transaction_repository import DjangoORMTransactionRepository
from ...adapters.services.fixed_exchange_rate import FixedExchangeRateService
from ...adapters.services.stripe_payment_service import StripePaymentService
from ...domain.entities import TransactionStatus
from ...domain.exceptions import (
    InvalidAmountError,
    PaymentServiceError,
    TransferBlockedError,
    TransferNotCancellableError,
)
from ...use_cases.cancel_transfer import CancelTransferUseCase
from ...use_cases.initiate_transfer import (
    InitiateTransferInput,
    InitiateTransferUseCase,
)
from ...use_cases.simulate_transfer import SimulateTransferInput, SimulateTransferUseCase
from .serializers import InitiateTransferRequestSerializer


class SimulateTransferView(APIView):
    """
    GET /api/transfer/simulate?amount=<EUR>

    Fig. 5 — première interaction avant soumission du transfert.
    Retourne le détail de la simulation : frais, taux, montant XAF.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        amount_str = request.query_params.get("amount", "").strip()
        if not amount_str:
            return Response(
                {"error": "Le paramètre 'amount' est requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            amount_eur = Decimal(amount_str)
        except InvalidOperation:
            return Response(
                {"error": "Format de montant invalide."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fig. 5 — vérification KYC avant simulation
        from contexts.identity.models import UserModel
        user = UserModel.objects.get(pk=request.user.pk)
        if not user.is_kyc_verified:
            return Response(
                {
                    "error": "KYC_NOT_VERIFIED",
                    "detail": "Votre identité doit être vérifiée avant d'effectuer un transfert.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        use_case = SimulateTransferUseCase(
            exchange_rate_service=FixedExchangeRateService()
        )
        try:
            sim = use_case.execute(SimulateTransferInput(amount_eur=amount_eur))
        except InvalidAmountError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "amount_eur": str(sim.amount_eur),
                "fees_eur": str(sim.fees_eur),
                "fees_percentage": str(sim.fees_percentage),
                "net_eur": str(sim.net_eur),
                "exchange_rate": str(sim.exchange_rate),
                "amount_xaf": str(sim.amount_xaf),
            },
            status=status.HTTP_200_OK,
        )


def _build_initiate_use_case() -> InitiateTransferUseCase:
    return InitiateTransferUseCase(
        exchange_rate_service=FixedExchangeRateService(),
        payment_service=StripePaymentService(),
        aml_use_case=ScoreAMLUseCase(
            scorer=get_configured_scorer(),
            sanctions_checker=MockSanctionsChecker(),
            aml_repo=DjangoORMAMLRepository(),
            transaction_history=DjangoTransactionHistoryService(),
            audit_queue=DjangoAuditQueueRepository(),
            audit_sample_rate=settings.AML_AUDIT_SAMPLE_RATE,
        ),
        transaction_repo=DjangoORMTransactionRepository(),
    )


class InitiateTransferView(APIView):
    """
    POST /api/transfer/initiate

    Lance le scoring AML AVANT tout appel Stripe. Un Payment Intent n'est créé
    que si l'AML résout en AUTO_APPROVED / MANUALLY_APPROVED.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Vérification KYC avant toute initiation
        from contexts.identity.models import UserModel
        user = UserModel.objects.get(pk=request.user.pk)
        if not user.is_kyc_verified:
            return Response(
                {
                    "error": "KYC_NOT_VERIFIED",
                    "detail": "Votre identité doit être vérifiée avant d'effectuer un transfert.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = InitiateTransferRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        use_case = _build_initiate_use_case()
        try:
            result = use_case.execute(
                InitiateTransferInput(
                    sender_id=str(request.user.pk),
                    beneficiary_name=data["beneficiary_name"],
                    beneficiary_country=data["beneficiary_country"],
                    momo_number=data["momo_number"],
                    operator=data["operator"],
                    amount_eur=data["amount_eur"],
                )
            )
        except InvalidAmountError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except TransferBlockedError as exc:
            # Ne jamais révéler les internes du scoring AML.
            return Response(
                {"error": "AML_BLOCKED", "reason": exc.reason},
                status=status.HTTP_403_FORBIDDEN,
            )
        except PaymentServiceError:
            # Erreur du prestataire de paiement (Stripe) — réponse générique.
            return Response(
                {"error": "PAYMENT_SERVICE_ERROR",
                 "detail": "Le service de paiement est temporairement indisponible."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if result.client_secret is None:
            # PENDING_REVIEW
            # KRYP-31 — Fig. 10 point 1 : notifie l'admin dès qu'un transfert
            # entre en revue manuelle (email — la liste GET /api/admin/aml/pending
            # sert de "dashboard" côté consultation, cf. commentaire de session).
            from contexts.notification.tasks import admin_alert_task
            admin_alert_task.delay(
                "ADMIN_ALERT_PENDING_REVIEW",
                settings.COMPLIANCE_MANAGER_EMAIL,
                {
                    "transaction_id": result.transaction.id,
                    "cta_url": f"{settings.FRONTEND_BASE_URL}/admin/aml",
                },
            )
            return Response(
                {
                    "transaction_id": result.transaction.id,
                    "status": TransactionStatus.AML_PENDING_REVIEW.value,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        # KRYP-30 — notifie uniquement le chemin qui atteint effectivement
        # PROCESSING après approbation AML (pas la revue manuelle ci-dessus, pas
        # le chemin bloqué/annulé-en-course, cf. InitiateTransferUseCase).
        from contexts.notification.tasks import notification_task
        notification_task.delay(
            "TRANSFER_INITIATED",
            result.transaction.sender_id,
            {
                "beneficiary_name": result.transaction.beneficiary_name,
                "amount_eur": str(result.transaction.amount_eur),
                "cta_url": f"{settings.FRONTEND_BASE_URL}/transfer/{result.transaction.id}",
            },
        )

        return Response(
            {
                "transaction_id": result.transaction.id,
                "status": TransactionStatus.PROCESSING.value,
                "client_secret": result.client_secret,
            },
            status=status.HTTP_201_CREATED,
        )


class StripeWebhookView(APIView):
    """
    POST /api/transfer/stripe/webhook

    Appelé par Stripe (non authentifié JWT — signature vérifiée via le secret webhook).
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except (ValueError, stripe.error.SignatureVerificationError):
            return Response(
                {"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST
            )

        event_type = event["type"]
        intent_id = event["data"]["object"]["id"]
        repo = DjangoORMTransactionRepository()

        if event_type == "payment_intent.succeeded":
            transaction = repo.find_by_payment_intent_id(intent_id)
            if transaction:
                # KRYP-25 — le verrouillage escrow est désormais un appel on-chain
                # réel dispatché de façon asynchrone (Fig. 7 : la transition
                # PROCESSING → ESCROWED est réalisée par la tâche, plus ici). La
                # transaction reste PROCESSING à ce stade.
                from contexts.transfer.tasks import escrow_lock_task
                escrow_lock_task.delay(transaction.id)
        elif event_type == "payment_intent.payment_failed":
            transaction = repo.find_by_payment_intent_id(intent_id)
            if transaction:
                repo.update_status(transaction.id, TransactionStatus.PAYMENT_FAILED)

        return Response({"received": True}, status=status.HTTP_200_OK)


class TransferStatusView(APIView):
    """GET /api/transfer/<id>/status — consulter le statut d'un transfert."""
    permission_classes = [IsAuthenticated]

    def get(self, request, id: str):
        repo = DjangoORMTransactionRepository()
        transaction = repo.find_by_id(id)
        if not transaction:
            return Response(
                {"error": "Transaction introuvable"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if transaction.sender_id != str(request.user.pk) and not request.user.is_staff:
            return Response(
                {"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN
            )

        # KRYP-27 — batch Polygon de l'événement de LIVRAISON spécifiquement.
        # Un transfert produit deux PendingAuditHash (ESCROWED puis DELIVERED),
        # potentiellement dans des lots différents : on filtre sur event_type
        # pour lever l'ambiguïté. Null tant que la livraison n'est pas batchée
        # (fenêtre de 15 min). merkle_proof reste en base, jamais exposé ici.
        from contexts.blockchain.models import PendingAuditHash
        delivered_audit = (
            PendingAuditHash.objects.filter(
                transaction_id=transaction.id,
                event_type=PendingAuditHash.EVENT_DELIVERED,
                batched=True,
            ).first()
        )

        return Response(
            {
                "transaction_id": transaction.id,
                "status": transaction.status.value,
                "amount_eur": str(transaction.amount_eur),
                "fees_eur": str(transaction.fees_eur),
                "amount_xaf": str(transaction.amount_xaf),
                "beneficiary_name": transaction.beneficiary_name,
                # KRYP-27 — champs additionnels (lecture seule) pour la timeline
                # de suivi temps réel. Déjà peuplés sur l'entité par _to_entity ;
                # aucune migration ni changement de logique métier.
                "beneficiary_country": transaction.beneficiary_country,
                "operator": transaction.operator,
                "escrow_tx_hash": transaction.escrow_tx_hash,
                "payout_reference": transaction.payout_reference,
                "created_at": (
                    transaction.created_at.isoformat()
                    if transaction.created_at
                    else None
                ),
                "updated_at": (
                    transaction.updated_at.isoformat()
                    if transaction.updated_at
                    else None
                ),
                "escrowed_at": (
                    transaction.escrowed_at.isoformat()
                    if transaction.escrowed_at
                    else None
                ),
                # KRYP-27 — traçabilité de l'étape "Fonds livrés" : lot Merkle
                # AuditTrail dans lequel l'événement DELIVERED a été ancré.
                "batch_id": delivered_audit.batch_id if delivered_audit else None,
                "batch_tx_hash": (
                    delivered_audit.batch_tx_hash if delivered_audit else None
                ),
            },
            status=status.HTTP_200_OK,
        )


class CancelTransferView(APIView):
    """DELETE /api/transfer/<id>/cancel — annuler un transfert avant confirmation
    Stripe (Fig. 7 : CANCELLED n'est accessible que depuis DRAFT/PENDING_AML)."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, id: str):
        repo = DjangoORMTransactionRepository()
        transaction = repo.find_by_id(id)
        if not transaction:
            return Response(
                {"error": "Transaction introuvable"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if transaction.sender_id != str(request.user.pk) and not request.user.is_staff:
            return Response(
                {"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN
            )

        use_case = CancelTransferUseCase(
            payment_service=StripePaymentService(),
            transaction_repo=repo,
        )
        try:
            result = use_case.execute(id)
        except TransferNotCancellableError as exc:
            return Response(
                {"error": "TRANSFER_NOT_CANCELLABLE", "reason": exc.reason},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "transaction_id": result.transaction.id,
                "status": result.transaction.status.value,
            },
            status=status.HTTP_200_OK,
        )
