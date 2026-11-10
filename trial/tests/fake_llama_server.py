"""A stand-in for llama.cpp's llama-server, for testing the no-container route with no model.

Takes the same arguments the harness passes, answers GET /health, and answers
POST /v1/chat/completions with the canned claims from the synthetic stub replies whose post ids
appear in the request, as a model reading those posts might.
"""

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STUB = Path(__file__).resolve().parent.parent / "samples" / "stub-replies.json"
IDS = re.compile(r"^\[([^\]]+)\]", re.MULTILINE)


def claims_for(text: str) -> list[dict[str, str]]:
    ids = set(IDS.findall(text))
    replies = json.loads(STUB.read_text(encoding="utf-8"))
    return [
        claim
        for key, reply in replies.items()
        if not key.startswith("_")
        for claim in reply["claims"]
        if claim["post_id"] in ids
    ]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:  # quiet
        pass

    def _send(self, code: int, body: dict[str, object]) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        self._send(200 if self.path == "/health" else 404, {"status": "ok"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length))
        user = next(m["content"] for m in request["messages"] if m["role"] == "user")
        content = json.dumps({"claims": claims_for(user)})
        self._send(200, {"choices": [{"message": {"role": "assistant", "content": content}}]})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    args, _unknown = parser.parse_known_args()
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
