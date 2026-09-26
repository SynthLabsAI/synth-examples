from dataclasses import dataclass


@dataclass
class User:
    is_admin: bool
    org_id: str


@dataclass
class Export:
    org_id: str
    contents: bytes = b"private export"


def can_download(user, export):
    return user.is_admin or user.org_id == export.org_id


def download_export(user, export):
    if not can_download(user, export):
        raise PermissionError("Export access denied")
    return export.contents
