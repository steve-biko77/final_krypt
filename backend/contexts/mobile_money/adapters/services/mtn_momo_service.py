"""KRYP-26 — MTN MoMo Remittance adapter (REAL implementation).

Disburses an XAF payout via MTN's Mobile Money Remittance product.

API-version uncertainty (documented deliberately)
--------------------------------------------------
MTN's interactive API console (``momodeveloper.mtn.com/API-collections#api=remittance``)
is a client-side-rendered SPA whose Swagger/Redoc operation specs are gated
behind an authenticated portal session and are NOT retrievable via a plain HTTP
fetch. The endpoint shapes below were therefore cross-validated against
first-party MTN sources (the "Cash Transfer Remittance API" dev-community
announcement) and the extremely consistent request pattern shared across MTN's
Collections/Disbursements/Remittances products, rather than from the live
console.

The Remittance product exposes two transfer generations:
  - legacy   ``POST /remittance/v1_0/transfer``          (widely implemented)
  - newer    ``POST /remittance/v2_0/cashtransfer``      ("set to replace" v1_0)

Both currently coexist in sandbox. We DEFAULT to ``v1_0`` (the classically
stable, most-implemented path) but drive the version from the
``MTN_REMITTANCE_API_VERSION`` setting so switching to ``v2_0`` is a one-line
config change, not a rewrite. The ultimate ground truth is the user's own
``pytest -m integration`` run against real sandbox credentials.

All credentials come from Django settings / env — never hardcoded.
"""
import base64
import logging
import time
import uuid
from decimal import Decimal

import requests
from django.conf import settings

from ...ports.mobile_money_service import MobileMoneyServicePort, PayoutResult

logger = logging.getLogger(__name__)

_OPERATOR = "MTN_MOMO"

# Path segment per remittance API generation. v1_0 uses ``transfer``; v2_0 uses
# ``cashtransfer``. Status checks follow GET /{product}/{version}/{resource}/{id}.
_RESOURCE_BY_VERSION = {
    "v1_0": "transfer",
    "v2_0": "cashtransfer",
}


class MTNMoMoError(RuntimeError):
    """Raised when the MTN MoMo API returns an error or is misconfigured."""


class MTNMoMoService(MobileMoneyServicePort):
    def __init__(
        self,
        base_url: str | None = None,
        subscription_key: str | None = None,
        api_user: str | None = None,
        api_key: str | None = None,
        api_version: str | None = None,
        target_environment: str | None = None,
    ):
        self._base_url = (
            base_url if base_url is not None
            else getattr(settings, "MTN_BASE_URL", "https://sandbox.momodeveloper.mtn.com")
        ).rstrip("/")
        self._subscription_key = (
            subscription_key if subscription_key is not None
            else getattr(settings, "MTN_SUBSCRIPTION_KEY", "")
        )
        self._api_user = (
            api_user if api_user is not None else getattr(settings, "MTN_API_USER", "")
        )
        self._api_key = (
            api_key if api_key is not None else getattr(settings, "MTN_API_KEY", "")
        )
        self._version = (
            api_version if api_version is not None
            else getattr(settings, "MTN_REMITTANCE_API_VERSION", "v1_0")
        )
        self._target_env = (
            target_environment if target_environment is not None
            else getattr(settings, "MTN_TARGET_ENVIRONMENT", "sandbox")
        )
        # In-memory token cache on the instance: {"token": str, "expires_at": float}.
        self._token_cache: dict = {}

    # ------------------------------------------------------------------ helpers
    def _resource(self) -> str:
        return _RESOURCE_BY_VERSION.get(self._version, "transfer")

    def _require_config(self) -> None:
        missing = [
            name for name, val in (
                ("MTN_SUBSCRIPTION_KEY", self._subscription_key),
                ("MTN_API_USER", self._api_user),
                ("MTN_API_KEY", self._api_key),
            ) if not val
        ]
        if missing:
            raise MTNMoMoError(
                f"MTN MoMo non configuré : {', '.join(missing)} manquant(s)."
            )

    def _get_token(self) -> str:
        """Return a cached OAuth2 token, refreshing only when near expiry.

        POST /remittance/token/ with Basic auth base64(apiUser:apiKey) +
        Ocp-Apim-Subscription-Key → {"access_token", "token_type", "expires_in"}.
        This per-product ``/{product}/token/`` Basic-auth pattern is consistent
        across every MTN MoMo product.
        """
        now = time.time()
        cached = self._token_cache.get("token")
        if cached and now < self._token_cache.get("expires_at", 0):
            return cached

        self._require_config()
        basic = base64.b64encode(
            f"{self._api_user}:{self._api_key}".encode()
        ).decode()
        resp = requests.post(
            f"{self._base_url}/remittance/token/",
            headers={
                "Authorization": f"Basic {basic}",
                "Ocp-Apim-Subscription-Key": self._subscription_key,
            },
            timeout=30,
        )
        if resp.status_code >= 400:
            raise MTNMoMoError(
                f"Échec obtention token MTN ({resp.status_code}): {resp.text}"
            )
        data = resp.json()
        token = data["access_token"]
        # Refresh 60s early to avoid using a token that expires mid-request.
        expires_in = int(data.get("expires_in", 3600))
        self._token_cache = {
            "token": token,
            "expires_at": now + max(expires_in - 60, 0),
        }
        return token

    def _auth_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Ocp-Apim-Subscription-Key": self._subscription_key,
            "X-Target-Environment": self._target_env,
        }

    # ------------------------------------------------------------------ ports
    def validate_account(self, momo_number: str, operator: str) -> bool:
        """GET /remittance/v1_0/accountholder/msisdn/{number}/active.

        MTN's account-status endpoint commonly returns ``{"result": true}``. The
        exact field name isn't confirmable from the session-gated console, so we
        parse defensively: honour a ``result`` boolean if present, otherwise
        treat any 2xx with a truthy body as active, and log the raw body at debug
        for future correction.
        """
        assert operator == _OPERATOR, f"MTNMoMoService got operator={operator}"
        headers = self._auth_headers()
        url = (
            f"{self._base_url}/remittance/v1_0/accountholder/msisdn/"
            f"{momo_number}/active"
        )
        resp = requests.get(url, headers=headers, timeout=30)
        logger.debug("validate_account MTN %s → %s %s", momo_number, resp.status_code, resp.text)
        if resp.status_code >= 400:
            return False
        try:
            body = resp.json()
        except ValueError:
            return True  # 2xx without JSON body → treat as active.
        if isinstance(body, dict) and "result" in body:
            return bool(body["result"])
        return bool(body)

    def send_payout(
        self,
        momo_number: str,
        amount_xaf: Decimal,
        transfer_id: str,
        operator: str,
    ) -> PayoutResult:
        """POST /remittance/{version}/{transfer|cashtransfer}.

        ``X-Reference-Id`` is a client-generated UUIDv4 that doubles as the
        idempotency key AND the payout id used for later status polling.

        Business-value assumption: the ``payer*`` identity fields represent KRYPT
        as the sending business entity (the regulated remitter of record), not
        the original EUR sender — real per-sender identity propagation is a
        production compliance concern out of scope for this ticket.
        """
        assert operator == _OPERATOR, f"MTNMoMoService got operator={operator}"
        reference_id = str(uuid.uuid4())
        headers = {
            **self._auth_headers(),
            "X-Reference-Id": reference_id,
            "Content-Type": "application/json",
        }
        amount_str = str(Decimal(amount_xaf).quantize(Decimal("1")))
        body = {
            "amount": amount_str,
            "currency": "XAF",
            "externalId": transfer_id,
            "payee": {"partyIdType": "MSISDN", "partyId": momo_number},
            "payerMessage": "Transfert KRYPT",
            "payeeNote": "Reception fonds KRYPT",
        }
        if self._version == "v2_0":
            # v2_0 cashtransfer enriches the body (confirmed field list).
            body.update({
                "originalAmount": amount_str,
                "originalCurrency": "XAF",
                "payerFirstName": "KRYPT",
                "payerSurName": "Transfer",
                "originatingCountry": "FR",
                "payerLanguageCode": "fr",
            })

        url = f"{self._base_url}/remittance/{self._version}/{self._resource()}"
        resp = requests.post(url, json=body, headers=headers, timeout=30)
        if resp.status_code >= 400:
            raise MTNMoMoError(
                f"Échec send_payout MTN ({resp.status_code}) pour {transfer_id}: {resp.text}"
            )
        # MTN returns 202 Accepted with an empty body; the reference id we
        # generated is the payout id. Status is asynchronous → PENDING.
        logger.info(
            "send_payout MTN accepté (ref=%s, http=%s) pour %s",
            reference_id, resp.status_code, transfer_id,
        )
        return PayoutResult(payout_id=reference_id, status="PENDING")

    def get_payout_status(self, payout_id: str, operator: str) -> str:
        """GET /remittance/{version}/{transfer|cashtransfer}/{payoutId}.

        Every MTN product follows GET /{product}/{version}/{resource}/{referenceId}
        for status; returns the ``status`` string from the response body.
        """
        assert operator == _OPERATOR, f"MTNMoMoService got operator={operator}"
        url = (
            f"{self._base_url}/remittance/{self._version}/"
            f"{self._resource()}/{payout_id}"
        )
        resp = requests.get(url, headers=self._auth_headers(), timeout=30)
        if resp.status_code >= 400:
            raise MTNMoMoError(
                f"Échec get_payout_status MTN ({resp.status_code}) pour {payout_id}: {resp.text}"
            )
        return resp.json().get("status", "UNKNOWN")
