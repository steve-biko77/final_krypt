"""Tableau de bord admin — vue d'ensemble plateforme (volume, dossiers par
catégorie, clients). N'introduit AUCUNE nouvelle logique de comptage : agrège
des compteurs déjà calculés ailleurs (file PENDING_REVIEW/ESCALATED de
admin_aml_views, cas HARD_BLOCK de admin_hard_block_views, décisions du jour
de admin_daily_report_views) plutôt que de les recalculer en parallèle.
"""
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from contexts.transfer.domain.entities import TransactionStatus

from ...domain.entities import AMLDecision
from ...models import AMLResultModel
from .admin_aml_views import _list_by_transaction_status
from .admin_daily_report_views import _aggregate_daily_report
from .permissions import IsStaffWith2FA


class AdminStatsView(APIView):
    """GET /api/admin/stats — porte d'entrée du tableau de bord admin."""

    permission_classes = [IsStaffWith2FA]

    def get(self, request):
        from contexts.identity.models import UserModel
        from contexts.transfer.models import TransactionModel

        total_users = UserModel.objects.count()
        total_kyc_verified = UserModel.objects.filter(is_kyc_verified=True).count()

        # Tous les statuts, y compris ceux à 0 occurrence — une vraie vue
        # d'ensemble, pas seulement les statuts déjà exposés ailleurs
        # (PENDING_REVIEW/ESCALATED/HARD_BLOCK).
        transactions_by_status = {s.value: 0 for s in TransactionStatus}
        for row in TransactionModel.objects.values("status").annotate(count=Count("id")):
            transactions_by_status[row["status"]] = row["count"]

        total_volume_eur = (
            TransactionModel.objects.filter(status=TransactionStatus.DELIVERED.value)
            .aggregate(total=Sum("amount_eur"))["total"]
            or Decimal("0.00")
        )

        pending_review_count = len(
            _list_by_transaction_status(TransactionStatus.AML_PENDING_REVIEW)
        )
        escalated_count = len(_list_by_transaction_status(TransactionStatus.ESCALATED))
        hard_block_count = AMLResultModel.objects.filter(
            combined_decision=AMLDecision.HARD_BLOCK.value
        ).count()

        today_decisions = _aggregate_daily_report(timezone.localdate())

        return Response(
            {
                "total_users": total_users,
                "total_kyc_verified": total_kyc_verified,
                "transactions_by_status": transactions_by_status,
                "total_volume_eur": str(total_volume_eur),
                "pending_review_count": pending_review_count,
                "escalated_count": escalated_count,
                "hard_block_count": hard_block_count,
                "today_decisions": today_decisions,
            },
            status=status.HTTP_200_OK,
        )
