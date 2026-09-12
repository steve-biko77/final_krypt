from decimal import Decimal, InvalidOperation

import stripe
from django.conf import settings
from django.http import HttpResponse
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

from ...adapters.orm.django_saved_beneficiary_repository import (
    DjangoORMSavedBeneficiaryRepository,
)
from ...adapters.orm.django_transaction_repository import DjangoORMTransactionRepository
from ...adapters.services.fixed_exchange_rate import FixedExchangeRateService
from ...adapters.services.receipt_generator import generate_transfer_receipt_pdf
from ...adapters.services.stripe_payment_service import StripePaymentService
from ...domain.entities import TransactionStatus
from ...domain.exceptions import (
    BeneficiaryNotFoundError,
    InvalidAmountError,
    PaymentServiceError,
    TransferBlockedError,
    TransferNotCancellableError,
)
from ...use_cases.cancel_transfer import CancelTransferUseCase
from ...use_cases.delete_beneficiary import DeleteBeneficiaryUseCase
from ...use_cases.initiate_transfer import (
    InitiateTransferInput,
    InitiateTransferUseCase,
)
from ...use_cases.list_beneficiaries import ListBeneficiariesUseCase
from ...use_cases.save_beneficiary import SaveBeneficiaryInput, SaveBeneficiaryUseCase
from ...use_cases.simulate_transfer import SimulateTransferInput, SimulateTransferUseCase
from .serializers import (
    InitiateTransferRequestSerializer,
    SaveBeneficiaryRequestSerializer,
)


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
        beneficiary_repo=DjangoORMSavedBeneficiaryRepository(),
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

        # KRYP-31 (partie 2/3) — compte gelé suite à un cas HARD_BLOCK (image 2,
        # section 4) : message volontairement générique, ne révèle jamais au
        # concerné qu'il s'agit d'un gel lié à une alerte de conformité.
        if user.is_frozen:
            return Response(
                {
                    "error": "TRANSFER_NOT_ALLOWED",
                    "detail": "Impossible d'initier ce transfert pour le moment. "
                              "Contactez le support pour plus d'informations.",
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


def _build_beneficiary_payload(beneficiary) -> dict:
    return {
        "id": beneficiary.id,
        "beneficiary_name": beneficiary.beneficiary_name,
        "beneficiary_country": beneficiary.beneficiary_country,
        "momo_number": beneficiary.momo_number,
        "operator": beneficiary.operator,
        "created_at": (
            beneficiary.created_at.isoformat() if beneficiary.created_at else None
        ),
        "last_used_at": (
            beneficiary.last_used_at.isoformat() if beneficiary.last_used_at else None
        ),
    }


class BeneficiariesView(APIView):
    """GET/POST /api/transfer/beneficiaries — carnet de contacts de
    l'utilisateur connecté. Isolation stricte : toujours filtré/rattaché à
    request.user, jamais à un id transmis par le client."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        use_case = ListBeneficiariesUseCase(
            beneficiary_repo=DjangoORMSavedBeneficiaryRepository()
        )
        beneficiaries = use_case.execute(str(request.user.pk))
        return Response(
            [_build_beneficiary_payload(b) for b in beneficiaries],
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = SaveBeneficiaryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        use_case = SaveBeneficiaryUseCase(
            beneficiary_repo=DjangoORMSavedBeneficiaryRepository()
        )
        beneficiary = use_case.execute(
            SaveBeneficiaryInput(
                user_id=str(request.user.pk),
                beneficiary_name=data["beneficiary_name"],
                beneficiary_country=data["beneficiary_country"],
                momo_number=data["momo_number"],
                operator=data["operator"],
            )
        )
        return Response(
            _build_beneficiary_payload(beneficiary), status=status.HTTP_201_CREATED
        )


class BeneficiaryDetailView(APIView):
    """DELETE /api/transfer/beneficiaries/<id> — supprime un bénéficiaire
    enregistré. La garde d'isolation (uniquement le sien) est atomique dans le
    repository (filtre pk + user_id dans la même requête) : un id valide
    appartenant à un autre utilisateur renvoie 404, jamais 403 (n'expose pas
    l'existence du bénéficiaire chez quelqu'un d'autre)."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, id: str):
        use_case = DeleteBeneficiaryUseCase(
            beneficiary_repo=DjangoORMSavedBeneficiaryRepository()
        )
        try:
            use_case.execute(beneficiary_id=id, user_id=str(request.user.pk))
        except BeneficiaryNotFoundError:
            return Response(
                {"error": "Bénéficiaire introuvable"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


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


def _build_transfer_status_payload(transaction) -> dict:
    """Projection Transaction -> payload JSON, partagée entre TransferStatusView
    (un transfert) et MyTransfersView (refonte frontend partie 3/4 — liste des
    transferts récents du tableau de bord) : même forme exacte, pour que le
    frontend puisse réutiliser ``buildTimeline()`` telle quelle sur les deux,
    sans une seconde projection divergente."""
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

    return {
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
            transaction.created_at.isoformat() if transaction.created_at else None
        ),
        "updated_at": (
            transaction.updated_at.isoformat() if transaction.updated_at else None
        ),
        "escrowed_at": (
            transaction.escrowed_at.isoformat() if transaction.escrowed_at else None
        ),
        # KRYP-27 — traçabilité de l'étape "Fonds livrés" : lot Merkle
        # AuditTrail dans lequel l'événement DELIVERED a été ancré.
        "batch_id": delivered_audit.batch_id if delivered_audit else None,
        "batch_tx_hash": (
            delivered_audit.batch_tx_hash if delivered_audit else None
        ),
    }


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

        return Response(_build_transfer_status_payload(transaction), status=status.HTTP_200_OK)


class MyTransfersView(APIView):
    """GET /api/transfer/mine?limit=5 — transferts récents de l'émetteur
    connecté (refonte frontend partie 3/4, tableau de bord). Même forme de
    payload que TransferStatusView (voir _build_transfer_status_payload)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            limit = min(max(int(request.query_params.get("limit", 5)), 1), 20)
        except ValueError:
            limit = 5

        repo = DjangoORMTransactionRepository()
        transactions = repo.find_by_sender(str(request.user.pk), limit=limit)

        results = [_build_transfer_status_payload(t) for t in transactions]
        return Response({"count": len(results), "results": results}, status=status.HTTP_200_OK)


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


class TransferReceiptView(APIView):
    """GET /api/transfer/<id>/receipt — reçu PDF téléchargeable, généré à la
    volée (pas de persistance/stockage, contrairement au rapport TRACFIN).

    Isolation : 404 si le transfert n'existe pas OU n'appartient pas à
    l'utilisateur connecté — jamais 403, même pattern que les bénéficiaires
    enregistrés (n'expose pas l'existence d'un transfert appartenant à
    quelqu'un d'autre). Pas de dérogation staff ici, contrairement à
    /status et /cancel : le reçu est un document personnel de l'émetteur.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, id: str):
        repo = DjangoORMTransactionRepository()
        transaction = repo.find_by_id(id)
        if transaction is None or transaction.sender_id != str(request.user.pk):
            return Response(
                {"error": "Transaction introuvable"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if transaction.status != TransactionStatus.DELIVERED:
            return Response(
                {
                    "error": "RECEIPT_NOT_AVAILABLE",
                    "detail": "Le reçu n'est disponible qu'une fois le transfert livré.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        pdf_bytes = generate_transfer_receipt_pdf({
            "transaction_id": transaction.id,
            "created_at": (
                transaction.created_at.strftime("%d/%m/%Y à %H:%M UTC")
                if transaction.created_at else "—"
            ),
            "amount_eur": str(transaction.amount_eur),
            "amount_xaf": str(transaction.amount_xaf),
            "beneficiary_name": transaction.beneficiary_name,
            "beneficiary_country": transaction.beneficiary_country,
            "status": transaction.status.value,
            "escrow_tx_hash": transaction.escrow_tx_hash,
        })

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="recu-krypt-{transaction.id}.pdf"'
        )
        return response
