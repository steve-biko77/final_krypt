class InvalidAmountError(Exception):
    pass


class KYCNotVerifiedError(Exception):
    pass


class TransferBlockedError(Exception):
    """Raised when the AML pipeline blocks a transfer (HARD_BLOCK / AUTO_BLOCKED /
    MANUALLY_REJECTED). Carries a generic reason — never AML scoring internals."""

    def __init__(self, reason: str = "Transfert non autorisé après vérification de conformité."):
        self.reason = reason
        super().__init__(reason)


class PaymentServiceError(Exception):
    """Raised when the payment provider (Stripe) fails. Wraps provider-specific
    exceptions so they never leak past the hexagonal port boundary."""
    pass


class TransferNotCancellableError(Exception):
    """KRYP-28 — Raised when a cancel is attempted on a transaction that is no
    longer DRAFT/PENDING_AML (Fig. 7: CANCELLED is reachable only from those two
    states), including the race where it changed status between the read and
    the guarded write."""

    def __init__(self, reason: str = "Ce transfert ne peut plus être annulé."):
        self.reason = reason
        super().__init__(reason)


class AdminReviewNotAllowedError(Exception):
    """KRYP-31 — Raised when an admin AML console action (request-docs, decide,
    escalated decide) is attempted on a transaction that isn't in the expected
    status for that action (Fig. 10), including the race where it changed
    between the read and the guarded write."""

    def __init__(self, reason: str = "Action non autorisée pour le statut actuel de ce transfert."):
        self.reason = reason
        super().__init__(reason)


class AdminReasonRequiredError(Exception):
    """KRYP-31 — Raised when an admin rejects a transfer without a motif
    (Fig. 10 point 4b: motif is mandatory for REJECT, validated at the use-case
    boundary so both the first-level and escalated-review entry points enforce
    it identically)."""

    def __init__(self, reason: str = "Un motif est requis pour cette décision."):
        self.reason = reason
        super().__init__(reason)
