"""KRYP-31 — Console admin AML (Fig. 8/9/10) : revue PENDING_REVIEW + ESCALATED.

Gate d'accès : is_staff ET 2FA activée (IsStaffWith2FA) sur les 8 endpoints
/api/admin/aml/*. Le tri par tag_ml_score DÉCROISSANT dans la liste `pending`
est un usage explicitement autorisé par seuils_production.md §2 (Couche 3) :
prioriser l'ordre d'affichage, jamais décider automatiquement — le score n'est
jamais utilisé comme critère de filtrage/blocage ici.
"""
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from contexts.blockchain.adapters.services.web3_blockchain_service import (
    Web3BlockchainService,
)
from contexts.transfer.adapters.orm.django_transaction_repository import (
    DjangoORMTransactionRepository,
)
from contexts.transfer.adapters.services.stripe_payment_service import (
    StripePaymentService,
)
from contexts.transfer.domain.entities import TransactionStatus
from contexts.transfer.domain.exceptions import (
    AdminReasonRequiredError,
    AdminReviewNotAllowedError,
)
from contexts.transfer.use_cases.decide_aml_review import (
    APPROVE,
    REJECT,
    ESCALATE,
    DecideAMLReviewUseCase,
)
from contexts.transfer.use_cases.request_aml_docs import RequestAMLDocsUseCase

from ...adapters.orm.django_aml_repository import DjangoORMAMLRepository
from ...models import AMLAdminAuditLog, AMLResultModel
from .admin_aml_serializers import AMLDecisionSerializer, EscalatedDecisionSerializer
from .permissions import IsStaffWith2FA

_POLYGONSCAN_TX = "https://amoy.polygonscan.com/tx"


def _polygonscan_url(tx_hash):
    return f"{_POLYGONSCAN_TX}/{tx_hash}" if tx_hash else None


def _pending_summary(result: AMLResultModel) -> dict:
    return {
        "transfer_id": result.transfer_id,
        "tag_ml_score": result.tag_ml_score,
        "xgboost_score": result.xgboost_score,
        "ofac_match": result.ofac_match,
        "triggered_rules": result.triggered_rules,
        "created_at": result.created_at.isoformat() if result.created_at else None,
    }


def _list_by_transaction_status(txn_status: TransactionStatus) -> list:
    """Transactions dans ``txn_status``, triées par tag_ml_score DÉCROISSANT via
    leur AMLResultModel associé (transfer_id = transaction.id, pas de FK — voir
    DjangoORMAMLRepository)."""
    from contexts.transfer.models import TransactionModel

    txn_ids = [
        str(i)
        for i in TransactionModel.objects.filter(
            status=txn_status.value
        ).values_list("id", flat=True)
    ]
    results = AMLResultModel.objects.filter(transfer_id__in=txn_ids).order_by(
        "-tag_ml_score"
    )
    return [_pending_summary(r) for r in results]


class AMLAdminPendingListView(APIView):
    """GET /api/admin/aml/pending — file d'attente triée par score DÉCROISSANT."""

    permission_classes = [IsStaffWith2FA]

    def get(self, request):
        results = _list_by_transaction_status(TransactionStatus.AML_PENDING_REVIEW)
        return Response(
            {"count": len(results), "results": results}, status=status.HTTP_200_OK
        )


class AMLAdminDetailView(APIView):
    """GET /api/admin/aml/{id} — dossier complet d'un transfert en revue."""

    permission_classes = [IsStaffWith2FA]

    def get(self, request, id: str):
        return _build_detail_response(id)


class AMLAdminRequestDocsView(APIView):
    """POST /api/admin/aml/{id}/request-docs — AML_PENDING_REVIEW -> AWAITING_DOCS."""

    permission_classes = [IsStaffWith2FA]

    def post(self, request, id: str):
        use_case = RequestAMLDocsUseCase(
            transaction_repo=DjangoORMTransactionRepository()
        )
        try:
            transaction = use_case.execute(id, admin_id=str(request.user.pk))
        except AdminReviewNotAllowedError as exc:
            return Response(
                {"error": "ADMIN_REVIEW_NOT_ALLOWED", "reason": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Message générique — aucun détail AML interne exposé à l'utilisateur.
        from contexts.notification.tasks import notification_task
        notification_task.delay(
            "DOCS_REQUESTED",
            transaction.sender_id,
            {"cta_url": f"{settings.FRONTEND_BASE_URL}/transfer/{transaction.id}"},
        )

        return Response(
            {"transaction_id": transaction.id, "status": transaction.status.value},
            status=status.HTTP_200_OK,
        )


class AMLAdminDecideView(APIView):
    """PATCH /api/admin/aml/{id}/decide — approve/reject/escalate (Fig. 10 pt 4)."""

    permission_classes = [IsStaffWith2FA]

    def patch(self, request, id: str):
        serializer = AMLDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        use_case = DecideAMLReviewUseCase(
            transaction_repo=DjangoORMTransactionRepository(),
            aml_repo=DjangoORMAMLRepository(),
            payment_service=StripePaymentService(),
            blockchain_service=Web3BlockchainService(),
        )
        try:
            result = use_case.execute(
                transaction_id=id,
                expected_status=TransactionStatus.AML_PENDING_REVIEW,
                action=data["action"],
                admin_id=str(request.user.pk),
                motif=data.get("motif", ""),
                audit_action_label=data["action"].upper(),
            )
        except AdminReasonRequiredError as exc:
            return Response(
                {"error": "MOTIF_REQUIRED", "reason": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except AdminReviewNotAllowedError as exc:
            return Response(
                {"error": "ADMIN_REVIEW_NOT_ALLOWED", "reason": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        _dispatch_decision_notification(result)

        return Response(
            {
                "transaction_id": result.transaction.id,
                "status": result.transaction.status.value,
                "polygonscan_url": _polygonscan_url(result.tx_hash),
            },
            status=status.HTTP_200_OK,
        )


class AMLAdminEscalatedListView(APIView):
    """GET /api/admin/aml/escalated — file des dossiers escaladés."""

    permission_classes = [IsStaffWith2FA]

    def get(self, request):
        results = _list_by_transaction_status(TransactionStatus.ESCALATED)
        return Response(
            {"count": len(results), "results": results}, status=status.HTTP_200_OK
        )


class AMLAdminEscalatedDetailView(APIView):
    """GET /api/admin/aml/escalated/{id} — détail + commentaire de l'admin qui a
    escaladé (Fig. 10 point 5)."""

    permission_classes = [IsStaffWith2FA]

    def get(self, request, id: str):
        escalation_log = (
            AMLAdminAuditLog.objects.filter(
                transaction_id=id, action=AMLAdminAuditLog.Action.ESCALATE
            )
            .order_by("-created_at")
            .first()
        )
        return _build_detail_response(
            id,
            extra={
                "escalation_comment": escalation_log.motif if escalation_log else None,
                "escalated_by": (
                    str(escalation_log.admin_id) if escalation_log else None
                ),
                "escalated_at": (
                    escalation_log.created_at.isoformat() if escalation_log else None
                ),
            },
        )


class AMLAdminEscalatedDecideView(APIView):
    """PATCH /api/admin/aml/escalated/{id}/decide — SEULEMENT approve/reject,
    jamais de ré-escalade (Fig. 10 point 5)."""

    permission_classes = [IsStaffWith2FA]

    def patch(self, request, id: str):
        serializer = EscalatedDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        use_case = DecideAMLReviewUseCase(
            transaction_repo=DjangoORMTransactionRepository(),
            aml_repo=DjangoORMAMLRepository(),
            payment_service=StripePaymentService(),
            blockchain_service=Web3BlockchainService(),
            allowed_actions=frozenset({APPROVE, REJECT}),
        )
        try:
            result = use_case.execute(
                transaction_id=id,
                expected_status=TransactionStatus.ESCALATED,
                action=data["action"],
                admin_id=str(request.user.pk),
                motif=data.get("motif", ""),
                audit_action_label=(
                    AMLAdminAuditLog.Action.ESCALATED_APPROVE
                    if data["action"] == APPROVE
                    else AMLAdminAuditLog.Action.ESCALATED_REJECT
                ),
            )
        except AdminReasonRequiredError as exc:
            return Response(
                {"error": "MOTIF_REQUIRED", "reason": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except AdminReviewNotAllowedError as exc:
            return Response(
                {"error": "ADMIN_REVIEW_NOT_ALLOWED", "reason": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        _dispatch_decision_notification(result)

        return Response(
            {
                "transaction_id": result.transaction.id,
                "status": result.transaction.status.value,
                "polygonscan_url": _polygonscan_url(result.tx_hash),
            },
            status=status.HTTP_200_OK,
        )


class AMLAdminHistoryView(APIView):
    """GET /api/admin/aml/history — décisions passées de L'ADMIN AUTHENTIFIÉ
    (PENDING_REVIEW et ESCALATED confondus), filtrable par type de décision via
    ``?action=``."""

    permission_classes = [IsStaffWith2FA]

    def get(self, request):
        qs = AMLAdminAuditLog.objects.filter(admin_id=request.user.pk).order_by(
            "-created_at"
        )
        action_filter = request.query_params.get("action")
        if action_filter:
            qs = qs.filter(action=action_filter.upper())

        results = [
            {
                "id": str(log.pk),
                "transaction_id": log.transaction_id,
                "action": log.action,
                "motif": log.motif,
                "tx_hash": log.tx_hash,
                "polygonscan_url": _polygonscan_url(log.tx_hash),
                "created_at": log.created_at.isoformat(),
            }
            for log in qs
        ]
        return Response(
            {"count": len(results), "results": results}, status=status.HTTP_200_OK
        )


# --------------------------------------------------------------------- helpers
def _build_detail_response(transaction_id: str, extra: dict = None) -> Response:
    repo = DjangoORMTransactionRepository()
    transaction = repo.find_by_id(transaction_id)
    if not transaction:
        return Response(
            {"error": "Transaction introuvable"}, status=status.HTTP_404_NOT_FOUND
        )

    aml_repo = DjangoORMAMLRepository()
    aml_result = aml_repo.find_by_transfer_id(transaction_id)

    from contexts.identity.models import UserModel
    sender = UserModel.objects.filter(pk=transaction.sender_id).first()

    # Fig. 10 point 2 — historique transactions de l'émetteur.
    from contexts.transfer.models import TransactionModel
    history_qs = (
        TransactionModel.objects.filter(sender_id=transaction.sender_id)
        .exclude(pk=transaction_id)
        .order_by("-created_at")[:10]
        .values("id", "status", "amount_eur", "beneficiary_name", "created_at")
    )

    payload = {
        "transaction_id": transaction.id,
        "status": transaction.status.value,
        "amount_eur": str(transaction.amount_eur),
        "amount_xaf": str(transaction.amount_xaf),
        "beneficiary_name": transaction.beneficiary_name,
        "beneficiary_country": transaction.beneficiary_country,
        "sender_email": sender.email if sender else None,
        "sender_is_kyc_verified": sender.is_kyc_verified if sender else None,
        "aml": (
            {
                "tag_ml_score": aml_result.tag_ml_score,
                "tag_ml_score_label": "Signal indicatif, non décisionnaire",
                "xgboost_score": aml_result.xgboost_score,
                "ofac_match": aml_result.ofac_match,
                "ofac_details": aml_result.ofac_details,
                "triggered_rules": aml_result.triggered_rules,
                "is_new_beneficiary": aml_result.is_new_beneficiary,
                "sender_tx_count_30d": aml_result.sender_tx_count_30d,
            }
            if aml_result
            else None
        ),
        "sender_transaction_history": [
            {
                "transaction_id": str(h["id"]),
                "status": h["status"],
                "amount_eur": str(h["amount_eur"]),
                "beneficiary_name": h["beneficiary_name"],
                "created_at": h["created_at"].isoformat(),
            }
            for h in history_qs
        ],
    }
    if extra:
        payload.update(extra)

    return Response(payload, status=status.HTTP_200_OK)


def _dispatch_decision_notification(result) -> None:
    if result.action == APPROVE:
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
    elif result.action == REJECT:
        # KRYP-31 — le motif admin (audit_log) reste STRICTEMENT interne : il
        # n'est JAMAIS injecté dans le contexte de la notification utilisateur,
        # qui réutilise le message générique existant TRANSFER_FAILED (KRYP-30).
        from contexts.notification.tasks import notification_task
        notification_task.delay(
            "TRANSFER_FAILED",
            result.transaction.sender_id,
            {
                "beneficiary_name": result.transaction.beneficiary_name,
                "cta_url": f"{settings.FRONTEND_BASE_URL}/transfer/{result.transaction.id}",
            },
        )
    elif result.action == ESCALATE:
        from contexts.notification.tasks import admin_alert_task
        admin_alert_task.delay(
            "ADMIN_ALERT_ESCALATED",
            settings.COMPLIANCE_MANAGER_EMAIL,
            {
                "transaction_id": result.transaction.id,
                "cta_url": f"{settings.FRONTEND_BASE_URL}/admin/aml/escalated",
            },
        )
