import re


class AppError(Exception):
    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def raise_app_error(code, message):
    raise AppError(code, message)


def normalize_header(text):
    return " ".join(str(text).split())


def header_key(text):
    return re.sub(r"[^a-z0-9]", "", normalize_header(text).lower())
