"""Local development server: `python -m app`, on 127.0.0.1 and PORT, or 8080 when unset.

This module runs only under `python -m app`, so it calls main() without an
`if __name__ == "__main__"` guard, as the Python documentation advises for __main__.py.
"""

import os

import uvicorn

from app.config import resolve_port

# Loopback only: a development server is never reachable from the network. The container never
# runs this module; gunicorn binds every interface there, as the App Store contract requires.
LOOPBACK = "127.0.0.1"


def main() -> None:
    uvicorn.run("app.main:app", host=LOOPBACK, port=resolve_port(os.environ))


main()
