class KYCAlreadyApprovedError(Exception):
    pass


class KYCDocumentNotFoundError(Exception):
    pass


class KYCInvalidStatusTransitionError(Exception):
    pass
