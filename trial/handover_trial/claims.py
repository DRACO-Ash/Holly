"""Claims the model pulls out of a thread, and the checks every claim must pass before it counts.

These are the checks the Handover plan puts between the local model and a synopsis, written here
first so the trial measures exactly what V0.20 would ship. A claim is kept only when all pass:

1. figure_in_post: the claim's number is written in the post it cites. A number the model made up
   is not in the post, so it is dropped.
2. provider_attributed: the provider is on the configured list, and the post either names it (or
   one of its aliases) or was written by an author mapped to it.
3. post_in_thread: the cited post belongs to the thread being read.

A claim whose quantity or unit is outside the fixed vocabulary is refused before the checks run.
"""

import re
from dataclasses import dataclass, field
from typing import Any

# The quantities a provider assessment can carry, each with the units it may be stated in.
QUANTITIES: dict[str, tuple[str, ...]] = {
    "period_change": ("s", "min"),
    "apogee_change": ("km", "m"),
    "perigee_change": ("km", "m"),
    "semi_major_axis_change": ("km", "m"),
    "inclination_change": ("deg",),
    "eccentricity_change": ("none",),
    "delta_v": ("m/s", "km/s", "cm/s"),
    "longitude": ("deg",),
    "drift_rate": ("deg/day",),
    "range": ("km", "m"),
    "brightness_change": ("mag",),
}

# A thousands separator is a comma followed by exactly three digits; any other comma is a decimal.
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
# A number standing on its own: it starts the text or follows a space or opening punctuation, so
# the digit in a name such as RED-1 and the parts of a clock time such as 15:05 never count.
_NUMBER = re.compile(r"(?<![^\s(\[,;/~=])([+\-\u2212]?)(\d+(?:[.,]\d+)?)(?![\d:])")


@dataclass(frozen=True)
class Post:
    post_id: str
    at: str
    author: str
    text: str


@dataclass(frozen=True)
class Thread:
    thread_id: str
    channel: str
    posts: tuple[Post, ...]

    def post(self, post_id: str) -> Post | None:
        return next((p for p in self.posts if p.post_id == post_id), None)


@dataclass(frozen=True)
class Claim:
    post_id: str
    provider: str
    quantity: str
    value: float
    unit: str
    signed: bool = False  # True when the claim states a sign, as in "+25"


@dataclass
class Providers:
    """Provider names with their aliases, and the Mattermost authors who speak for each."""

    aliases: dict[str, tuple[str, ...]]
    authors: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Providers":
        aliases = {
            str(name): tuple(str(a) for a in entry.get("aliases", []))
            for name, entry in data.get("providers", {}).items()
        }
        authors = {str(a).lower(): str(p) for a, p in data.get("authors", {}).items()}
        return cls(aliases=aliases, authors=authors)

    def canonical(self, name: str) -> str | None:
        wanted = name.strip().lower()
        for provider, aliases in self.aliases.items():
            if wanted == provider.lower() or wanted in (a.lower() for a in aliases):
                return provider
        return None

    def named_in(self, provider: str, text: str) -> bool:
        for word in (provider, *self.aliases.get(provider, ())):
            if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text, re.IGNORECASE):
                return True
        return False


def numbers_in(text: str) -> list[tuple[str, float]]:
    """Every number written in the text, with its written sign ('' when none)."""
    found = []
    for sign, digits in _NUMBER.findall(_THOUSANDS.sub("", text)):
        found.append(("-" if sign in "-\u2212" and sign else sign, float(digits.replace(",", "."))))
    return found


def figure_in_post(claim: Claim, post: Post) -> bool:
    for sign, number in numbers_in(post.text):
        if number != abs(claim.value):
            continue
        # A sign the post writes must agree with the claim; an unsigned figure matches either.
        if sign == "" or (sign == "-") == (claim.value < 0):
            return True
    return False


def provider_attributed(claim: Claim, post: Post, providers: Providers) -> bool:
    provider = providers.canonical(claim.provider)
    if provider is None:
        return False
    return providers.authors.get(post.author.lower()) == provider or providers.named_in(
        provider, post.text
    )


@dataclass(frozen=True)
class Verdict:
    claim: Claim
    figure_in_post: bool
    provider_attributed: bool
    post_in_thread: bool

    @property
    def kept(self) -> bool:
        return self.figure_in_post and self.provider_attributed and self.post_in_thread

    def reason(self) -> str:
        if self.kept:
            return "kept"
        if not self.post_in_thread:
            return "dropped: post_in_thread"
        failed = [
            name
            for name, ok in (
                ("post_in_thread", self.post_in_thread),
                ("figure_in_post", self.figure_in_post),
                ("provider_attributed", self.provider_attributed),
            )
            if not ok
        ]
        return "dropped: " + ", ".join(failed)


def check(claim: Claim, thread: Thread, providers: Providers) -> Verdict:
    post = thread.post(claim.post_id)
    if post is None:
        return Verdict(claim, False, False, False)
    return Verdict(
        claim,
        figure_in_post(claim, post),
        provider_attributed(claim, post, providers),
        True,
    )


def parse_claims(data: Any) -> tuple[list[Claim], list[str]]:
    """The model's JSON reply as claims, and a note for each item refused as malformed. Nothing
    in the reply is trusted: anything not of the expected shape is refused, never repaired."""
    claims: list[Claim] = []
    refused: list[str] = []
    items = data.get("claims") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return [], ["reply has no claims list"]
    for i, item in enumerate(items):
        problem = _problem(item)
        if problem:
            refused.append(f"claim {i}: {problem}")
            continue
        raw = str(item["value"]).strip().replace("\u2212", "-")
        claims.append(
            Claim(
                post_id=item["post_id"],
                provider=item["provider"],
                quantity=item["quantity"],
                value=float(raw),
                unit=item["unit"],
                signed=raw[:1] in "+-",
            )
        )
    return claims, refused


def _problem(item: Any) -> str | None:
    if not isinstance(item, dict):
        return "not an object"
    for key in ("post_id", "provider", "quantity", "unit"):
        if not isinstance(item.get(key), str) or not item[key].strip():
            return f"missing {key}"
    if item["quantity"] not in QUANTITIES:
        return f"unknown quantity {item['quantity']!r}"
    if item["unit"] not in QUANTITIES[item["quantity"]]:
        return f"unit {item['unit']!r} not allowed for {item['quantity']}"
    value = item.get("value")
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return "value is not a number"
    try:
        number = float(str(value).strip().replace("\u2212", "-"))
    except ValueError:
        return "value is not a number"
    if number != number or abs(number) > 1e9:
        return "value out of range"
    return None
