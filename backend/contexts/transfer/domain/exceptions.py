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
