class UserAlreadyExistsError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class TOTPInvalidError(Exception):
    pass


class TOTPAlreadyEnabledError(Exception):
    pass


class TOTPNotEnabledError(Exception):
    pass
