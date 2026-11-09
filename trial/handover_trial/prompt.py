"""The instruction and reply schema the local model gets: extraction only, never free writing."""

from .claims import QUANTITIES, Post, Providers

SYSTEM = """You read a chat thread about a space object event and list the assessments that \
companies (providers) have made, as figures written in the posts.

Rules:
- Only list a figure that is written in a post. Copy the number exactly as written, with its \
sign only if the post writes one (+ or -).
- provider is the company whose assessment it is: one named in the post, or the company shown \
for the post's author. Use only these providers: {providers}.
- If a post gives a figure but you cannot tell which provider it belongs to, leave it out.
- quantity must be one of: {quantities}. unit must be one allowed for that quantity.
- post_id is the id in square brackets before the post.
- Do not guess, average, convert or work anything out. If there is nothing to list, return \
{{"claims": []}}.

Reply with JSON only."""


def system_prompt(providers: Providers) -> str:
    quantities = "; ".join(f"{q} ({', '.join(units)})" for q, units in QUANTITIES.items())
    return SYSTEM.format(providers=", ".join(providers.aliases) or "none", quantities=quantities)


def user_prompt(posts: tuple[Post, ...], providers: Providers) -> str:
    lines = []
    for post in posts:
        company = providers.authors.get(post.author.lower(), "unknown")
        text = " ".join(post.text.split())
        lines.append(f"[{post.post_id}] {post.at} {post.author} (company: {company}): {text}")
    return "Thread:\n" + "\n".join(lines)


def reply_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "post_id": {"type": "string"},
                        "provider": {"type": "string"},
                        "quantity": {"type": "string", "enum": list(QUANTITIES)},
                        "value": {"type": "string"},
                        "unit": {"type": "string"},
                    },
                    "required": ["post_id", "provider", "quantity", "value", "unit"],
                },
            }
        },
        "required": ["claims"],
    }
