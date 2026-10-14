"""Facts about the calling client, read once in one place."""

from starlette.requests import Request


def client_ip(request: Request) -> str | None:
    """The client address the server sees, as recorded in the audit log.

    Behind the App Store ingress this is the ingress address unless gunicorn trusts the
    ingress's forwarded headers (the FORWARDED_ALLOW_IPS setting); see SECURITY.md.
    """
    return request.client.host if request.client else None
