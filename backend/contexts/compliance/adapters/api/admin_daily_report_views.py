"""KRYP-31 (partie 3/3) — Rapport de fin de journée (image 2, section 5) :
generate daily compliance report, export CSV (decisions + audit trail),
archive in DB + Polygon reference.

Agrège UNIQUEMENT des données déjà persistées par les parties 1/3 et 2/3
(AMLAdminAuditLog) et référence le batch Polygon du jour déjà produit par le
mécanisme AuditTrail existant (KRYP-25/27, PendingAuditHash) — aucune nouvelle
logique de décision, aucun nouveau mécanisme d'ancrage on-chain.
"""
import csv
import datetime as dt
import io

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ...models import AMLAdminAuditLog, DailyComplianceReportModel
from .permissions import IsStaffWith2FA

_DECISION_BUCKETS = {
    AMLAdminAuditLog.Action.APPROVE: "approve",
    AMLAdminAuditLog.Action.ESCALATED_APPROVE: "approve",
    AMLAdminAuditLog.Action.REJECT: "reject",
    AMLAdminAuditLog.Action.ESCALATED_REJECT: "reject",
    AMLAdminAuditLog.Action.ESCALATE: "escalate",
}
_HARD_BLOCK_BUCKETS = {
    AMLAdminAuditLog.Action.DOCUMENT: "hard_block_documented",
    AMLAdminAuditLog.Action.FREEZE_ACCOUNT: "hard_block_frozen",
    AMLAdminAuditLog.Action.TRACFIN_REPORT_GENERATED: "hard_block_tracfin_generated",
}
_EMPTY_COUNTS = {
    "approve": 0,
    "reject": 0,
    "escalate": 0,
    "hard_block_documented": 0,
    "hard_block_frozen": 0,
    "hard_block_tracfin_generated": 0,
}


class InvalidReportDateError(Exception):
    """Format de date invalide passé en query param (?date=)."""


def _parse_date_param(request) -> dt.date:
    raw = request.query_params.get("date") if hasattr(request, "query_params") else None
    if raw is None:
        raw = request.GET.get("date")
    if not raw:
        return timezone.localdate()
    try:
        return dt.datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        raise InvalidReportDateError(f"Date invalide : {raw!r} (attendu YYYY-MM-DD).")


def _day_bounds(report_date: dt.date):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(dt.datetime.combine(report_date, dt.time.min), tz)
    return start, start + dt.timedelta(days=1)


def _aggregate_daily_report(report_date: dt.date) -> dict:
    """Point d'agrégation UNIQUE, réutilisé par le GET et l'archivage — ne
    recalcule ni ne duplique aucune logique métier, se contente de lire
    AMLAdminAuditLog (déjà écrit par les parties 1/3 et 2/3)."""
    start, end = _day_bounds(report_date)
    logs = list(
        AMLAdminAuditLog.objects.filter(created_at__gte=start, created_at__lt=end)
        .order_by("created_at")
    )

    from contexts.identity.models import UserModel
    admin_emails = {
        str(u.pk): u.email
        for u in UserModel.objects.filter(pk__in={log.admin_id for log in logs})
    }

    counts = dict(_EMPTY_COUNTS)
    decisions = []
    for log in logs:
        bucket = _DECISION_BUCKETS.get(log.action) or _HARD_BLOCK_BUCKETS.get(log.action)
        if bucket:
            counts[bucket] += 1
        decisions.append({
            "id": str(log.pk),
            "created_at": log.created_at.isoformat(),
            "admin_id": str(log.admin_id),
            "admin_email": admin_emails.get(str(log.admin_id)),
            "action": log.action,
            "transaction_id": log.transaction_id,
            "motif": log.motif,
            "tx_hash": log.tx_hash,
        })

    return {
        "date": report_date.isoformat(),
        "counts": counts,
        "total_decisions": len(decisions),
        "decisions": decisions,
    }


def _polygon_batch_reference(report_date: dt.date):
    """Réutilise le batch AuditTrail déjà produit (KRYP-25/27) : le dernier
    batch commit ayant intégré une feuille créée ce jour-là. Ne déclenche
    AUCUN appel on-chain — lecture seule de PendingAuditHash."""
    from contexts.blockchain.models import PendingAuditHash

    start, end = _day_bounds(report_date)
    row = (
        PendingAuditHash.objects.filter(
            batched=True, created_at__gte=start, created_at__lt=end
        )
        .exclude(batch_id__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if row is None:
        return None, None
    return row.batch_id, row.batch_tx_hash


class AMLAdminDailyReportView(APIView):
    """GET /api/admin/aml/daily-report?date=YYYY-MM-DD (défaut : aujourd'hui)."""

    permission_classes = [IsStaffWith2FA]

    def get(self, request):
        try:
            report_date = _parse_date_param(request)
        except InvalidReportDateError as exc:
            return Response(
                {"error": "INVALID_DATE", "reason": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        report = _aggregate_daily_report(report_date)
        return Response(report, status=status.HTTP_200_OK)


class AMLAdminDailyReportExportCSVView(APIView):
    """GET /api/admin/aml/daily-report/export-csv?date=YYYY-MM-DD — une ligne
    par décision, motif interne inclus (destinataire = admin, pas l'usager
    final, contrairement aux notifications)."""

    permission_classes = [IsStaffWith2FA]

    def get(self, request):
        try:
            report_date = _parse_date_param(request)
        except InvalidReportDateError as exc:
            return Response(
                {"error": "INVALID_DATE", "reason": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        report = _aggregate_daily_report(report_date)

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            ["timestamp", "admin", "type_decision", "transaction_id", "motif", "tx_hash"]
        )
        for d in report["decisions"]:
            writer.writerow([
                d["created_at"],
                d["admin_email"] or d["admin_id"],
                d["action"],
                d["transaction_id"],
                d["motif"],
                d["tx_hash"] or "",
            ])

        response = HttpResponse(buffer.getvalue(), content_type="text/csv")
        filename = f"rapport-conformite-{report_date.isoformat()}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class AMLAdminDailyReportArchiveView(APIView):
    """POST /api/admin/aml/daily-report/archive — figeage du rapport agrégé du
    jour (ou de la date spécifiée) + référence du batch Polygon déjà émis.
    Un double archivage de la même date est refusé (400)."""

    permission_classes = [IsStaffWith2FA]

    def post(self, request):
        try:
            report_date = _parse_date_param(request)
        except InvalidReportDateError as exc:
            return Response(
                {"error": "INVALID_DATE", "reason": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if DailyComplianceReportModel.objects.filter(report_date=report_date).exists():
            return Response(
                {
                    "error": "ALREADY_ARCHIVED",
                    "reason": f"Le rapport du {report_date.isoformat()} est déjà archivé.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        report = _aggregate_daily_report(report_date)
        batch_id, batch_tx_hash = _polygon_batch_reference(report_date)

        archive = DailyComplianceReportModel.objects.create(
            report_date=report_date,
            counts=report["counts"],
            decisions=report["decisions"],
            polygon_batch_id=str(batch_id) if batch_id is not None else None,
            polygon_batch_tx_hash=batch_tx_hash,
            archived_by_id=request.user.pk,
        )

        return Response(
            {
                "date": report_date.isoformat(),
                "counts": archive.counts,
                "total_decisions": len(archive.decisions),
                "polygon_batch_id": archive.polygon_batch_id,
                "polygon_batch_tx_hash": archive.polygon_batch_tx_hash,
                "archived_at": archive.archived_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )
