"""Where claims come from: the real local model, or canned replies for a dry run.

`LlamaBackend` imports llama_cpp only when built, so the checks, the scoring and the dry run need
nothing beyond the standard library.
"""

import json
from pathlib import Path
from typing import Any, Protocol

from .claims import Post, Providers
from .prompt import reply_schema, system_prompt, user_prompt


class Backend(Protocol):
    name: str

    def extract(self, thread_id: str, posts: tuple[Post, ...], providers: Providers) -> str:
        """The raw reply text for one run of posts."""


class StubBackend:
    """Replies read from a JSON file: {thread_id: {"claims": [...]}}. For the dry run and tests,
    so the whole pipeline can be exercised with no model and no real data."""

    def __init__(self, replies: Path) -> None:
        self.name = f"stub:{replies.name}"
        self._replies: dict[str, Any] = json.loads(replies.read_text(encoding="utf-8"))
        self._served: set[str] = set()

    def extract(self, thread_id: str, posts: tuple[Post, ...], providers: Providers) -> str:
        # The whole canned reply on a thread's first run of posts, nothing after, so a claim
        # citing a post outside the thread still reaches the checks, as a model's could.
        if thread_id in self._served:
            return json.dumps({"claims": []})
        self._served.add(thread_id)
        return json.dumps(self._replies.get(thread_id, {"claims": []}))


class LlamaBackend:
    """A quantised GGUF model through llama-cpp-python, on the CPU, with the reply constrained to
    the schema. Temperature 0 so a rerun gives the same answer."""

    def __init__(self, model_path: Path, threads: int, context: int, max_tokens: int) -> None:
        from llama_cpp import Llama  # noqa: PLC0415  imported here so the dry run needs no model

        self.name = model_path.name
        self._max_tokens = max_tokens
        self._llm = Llama(
            model_path=str(model_path),
            n_ctx=context,
            n_threads=threads,
            n_threads_batch=threads,
            verbose=False,
        )

    def extract(self, thread_id: str, posts: tuple[Post, ...], providers: Providers) -> str:
        reply = self._llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt(providers)},
                {"role": "user", "content": user_prompt(posts, providers)},
            ],
            temperature=0.0,
            max_tokens=self._max_tokens,
            response_format={"type": "json_object", "schema": reply_schema()},
        )
        return str(reply["choices"][0]["message"]["content"] or "")
