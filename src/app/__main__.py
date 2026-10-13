"""Local development server: `python -m app`, on 0.0.0.0 and PORT, or 8080 when unset.

This module runs only under `python -m app`, so it calls main() without an
`if __name__ == "__main__"` guard, as the Python documentation advises for __main__.py.
"""

import os

import uvicorn

from app.config import resolve_port

# The App Store contract binds every interface, so the dev server matches the container.
BIND_ALL_INTERFACES = "0.0.0.0"  # noqa: S104


def main() -> None:
    uvicorn.run("app.main:app", host=BIND_ALL_INTERFACES, port=resolve_port(os.environ))


main()
