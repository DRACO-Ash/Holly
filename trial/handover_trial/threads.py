"""Thread files for the trial, and the converter from Mattermost's own thread export.

A trial thread file is JSON:

    {"thread_id": "...", "channel": "...",
     "posts": [{"post_id": "...", "at": "2026-11-02T17:42:00Z", "author": "...", "text": "..."}]}

Mattermost's `GET /api/v4/posts/{post_id}/thread` returns {"order": [...], "posts": {id: post}};
`convert_mattermost` turns that into the trial format, oldest post first.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .claims import Post, Thread

MAX_POST_CHARS = 4000


def load_thread(path: Path) -> Thread:
    data = json.loads(path.read_text(encoding="utf-8"))
    posts = tuple(
        Post(
            post_id=str(p["post_id"]),
            at=str(p.get("at", "")),
            author=str(p.get("author", "")),
            text=str(p.get("text", ""))[:MAX_POST_CHARS],
        )
        for p in data["posts"]
    )
    if not posts:
        raise ValueError(f"{path.name}: a thread needs at least one post")
    return Thread(
        thread_id=str(data["thread_id"]), channel=str(data.get("channel", "")), posts=posts
    )


def load_threads(folder: Path) -> list[Thread]:
    return [load_thread(p) for p in sorted(folder.glob("*.json"))]


def convert_mattermost(
    export: dict[str, Any], channel: str = "", users: dict[str, str] | None = None
) -> dict[str, Any]:
    """Trial format from a Mattermost thread export. `users` maps user ids to display names;
    an unmapped id is kept as the author. System posts and empty posts are left out."""
    users = users or {}
    posts = [p for p in export.get("posts", {}).values() if isinstance(p, dict)]
    posts = [p for p in posts if not str(p.get("type", "")).startswith("system_")]
    posts = [p for p in posts if str(p.get("message", "")).strip()]
    posts.sort(key=lambda p: int(p.get("create_at", 0)))
    if not posts:
        raise ValueError("the export holds no readable posts")
    root = next((p for p in posts if not p.get("root_id")), posts[0])
    return {
        "thread_id": str(root.get("id")),
        "channel": channel,
        "posts": [
            {
                "post_id": str(p.get("id")),
                "at": datetime.fromtimestamp(int(p.get("create_at", 0)) / 1000, UTC)
                .isoformat()
                .replace("+00:00", "Z"),
                "author": users.get(str(p.get("user_id")), str(p.get("user_id", ""))),
                "text": str(p.get("message", "")),
            }
            for p in posts
        ],
    }


def chunks(thread: Thread, max_chars: int) -> list[tuple[Post, ...]]:
    """The thread's posts in runs that fit the model's window, never splitting a post."""
    runs: list[tuple[Post, ...]] = []
    run: list[Post] = []
    size = 0
    for post in thread.posts:
        cost = len(post.text) + 80
        if run and size + cost > max_chars:
            runs.append(tuple(run))
            run, size = [], 0
        run.append(post)
        size += cost
    if run:
        runs.append(tuple(run))
    return runs
