from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ...adapters.services.fixed_exchange_rate import FixedExchangeRateService
from ...domain.exceptions import InvalidAmountError
from ...use_cases.simulate_transfer import SimulateTransferInput, SimulateTransferUseCase


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
