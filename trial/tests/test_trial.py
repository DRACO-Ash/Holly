"""Tests for the trial harness. Standard library only: python -m unittest discover -s tests"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from handover_trial.__main__ import main  # noqa: E402
from handover_trial.claims import (  # noqa: E402
    Claim,
    Post,
    Providers,
    Thread,
    check,
    figure_in_post,
    numbers_in,
    parse_claims,
)
from handover_trial.threads import chunks, convert_mattermost  # noqa: E402

PROVIDERS = Providers.from_json(
    {
        "providers": {"NorthStar": {"aliases": ["North Star"]}, "KBR": {"aliases": []}},
        "authors": {"ns-analyst": "NorthStar"},
    }
)


def post(text: str, author: str = "someone", post_id: str = "p1") -> Post:
    return Post(post_id, "2026-01-01T00:00:00Z", author, text)


def claim(
    value: float, provider: str = "NorthStar", signed: bool = False, post_id: str = "p1"
) -> Claim:
    return Claim(post_id, provider, "period_change", value, "s", signed)


class Numbers(unittest.TestCase):
    def test_reads_signs_units_decimals_and_thousands(self) -> None:
        got = numbers_in("+25s and 17km, −12.5 km, 1,000 m, 0,5 deg")
        self.assertEqual(got, [("+", 25.0), ("", 17.0), ("-", 12.5), ("", 1000.0), ("", 0.5)])

    def test_clock_times_and_names_are_not_figures(self) -> None:
        self.assertEqual(numbers_in("RED-1 at 15:05Z"), [])


class FigureInPost(unittest.TestCase):
    def test_written_figure_passes(self) -> None:
        self.assertTrue(figure_in_post(claim(25, signed=True), post("a +25s change")))

    def test_made_up_figure_fails(self) -> None:
        self.assertFalse(figure_in_post(claim(30), post("a +25s change")))

    def test_sign_the_post_writes_must_agree(self) -> None:
        self.assertFalse(figure_in_post(claim(-25, signed=True), post("a +25s change")))
        self.assertTrue(figure_in_post(claim(-25, signed=True), post("a 25s change")))

    def test_part_of_a_clock_time_is_not_support(self) -> None:
        self.assertFalse(figure_in_post(claim(5), post("seen at 15:05Z")))


class ProviderAttributed(unittest.TestCase):
    def test_named_in_post_or_by_alias(self) -> None:
        self.assertTrue(
            check(claim(25), Thread("t", "c", (post("NorthStar: 25s"),)), PROVIDERS).kept
        )
        self.assertTrue(
            check(claim(25), Thread("t", "c", (post("North Star say 25s"),)), PROVIDERS).kept
        )

    def test_author_mapped_to_provider(self) -> None:
        self.assertTrue(
            check(claim(25), Thread("t", "c", (post("we see 25s", "ns-analyst"),)), PROVIDERS).kept
        )

    def test_not_on_list_or_not_attributable(self) -> None:
        thread = Thread("t", "c", (post("we see 25s"),))
        self.assertFalse(check(claim(25), thread, PROVIDERS).provider_attributed)
        self.assertFalse(check(claim(25, provider="Other"), thread, PROVIDERS).provider_attributed)

    def test_a_name_inside_another_word_does_not_count(self) -> None:
        thread = Thread("t", "c", (post("KBRX reports 25s"),))
        self.assertFalse(check(claim(25, provider="KBR"), thread, PROVIDERS).provider_attributed)


class PostInThread(unittest.TestCase):
    def test_post_outside_the_thread_is_dropped(self) -> None:
        verdict = check(
            claim(25, post_id="zz"), Thread("t", "c", (post("NorthStar 25s"),)), PROVIDERS
        )
        self.assertFalse(verdict.kept)
        self.assertEqual(verdict.reason(), "dropped: post_in_thread")


class ParseClaims(unittest.TestCase):
    def test_refuses_every_malformed_shape(self) -> None:
        base = {
            "post_id": "p1",
            "provider": "KBR",
            "quantity": "period_change",
            "value": "5",
            "unit": "s",
        }
        bad = [
            "text",
            {**base, "quantity": "burn_size"},
            {**base, "unit": "km"},
            {**base, "value": "five"},
            {**base, "value": True},
            {**base, "value": "nan"},
            {**base, "value": "1e12"},
            {**base, "provider": " "},
        ]
        claims, refused = parse_claims({"claims": [base, *bad]})
        self.assertEqual(len(claims), 1)
        self.assertEqual(len(refused), len(bad))

    def test_reply_without_a_list_is_refused(self) -> None:
        self.assertEqual(parse_claims({"nope": 1}), ([], ["reply has no claims list"]))

    def test_records_whether_the_value_was_signed(self) -> None:
        claims, _ = parse_claims(
            {
                "claims": [
                    {
                        "post_id": "p",
                        "provider": "KBR",
                        "quantity": "range",
                        "value": "+3",
                        "unit": "km",
                    }
                ]
            }
        )
        self.assertTrue(claims[0].signed)


class Threads(unittest.TestCase):
    def test_converts_a_mattermost_export_oldest_first(self) -> None:
        export = {
            "order": ["r", "x"],
            "posts": {
                "x": {
                    "id": "x",
                    "root_id": "r",
                    "create_at": 2000,
                    "user_id": "u2",
                    "message": "reply",
                },
                "r": {
                    "id": "r",
                    "root_id": "",
                    "create_at": 1000,
                    "user_id": "u1",
                    "message": "root",
                },
                "s": {
                    "id": "s",
                    "root_id": "r",
                    "create_at": 1500,
                    "type": "system_join_channel",
                    "message": "joined",
                },
                "e": {
                    "id": "e",
                    "root_id": "r",
                    "create_at": 1600,
                    "user_id": "u1",
                    "message": "  ",
                },
            },
        }
        out = convert_mattermost(export, "geo", {"u1": "ns-analyst"})
        self.assertEqual(out["thread_id"], "r")
        self.assertEqual([p["post_id"] for p in out["posts"]], ["r", "x"])
        self.assertEqual(out["posts"][0]["author"], "ns-analyst")
        self.assertEqual(out["posts"][1]["author"], "u2")

    def test_chunks_never_split_a_post(self) -> None:
        thread = Thread("t", "c", tuple(post("x" * 100, post_id=str(i)) for i in range(5)))
        runs = chunks(thread, 400)
        self.assertEqual(sum(len(r) for r in runs), 5)
        self.assertTrue(all(len(r) >= 1 for r in runs))


class UsersFile(unittest.TestCase):
    def test_reads_a_map_or_mattermosts_user_list(self) -> None:
        from handover_trial.__main__ import _users

        with tempfile.TemporaryDirectory() as d:
            listed = Path(d) / "list.json"
            listed.write_text(json.dumps([{"id": "u1", "username": "ns-analyst"}]))
            mapped = Path(d) / "map.json"
            mapped.write_text(json.dumps({"u2": "kbr-analyst"}))
            self.assertEqual(_users(listed), {"u1": "ns-analyst"})
            self.assertEqual(_users(mapped), {"u2": "kbr-analyst"})


class DryRun(unittest.TestCase):
    def test_dry_run_scores_the_synthetic_set(self) -> None:
        with tempfile.TemporaryDirectory() as out:
            self.assertEqual(main(["dry-run", "--out", out]), 0)
            score = json.loads((Path(out) / "scores.json").read_text(encoding="utf-8"))[0]
        self.assertEqual(score["key_claims"], 10)
        self.assertEqual(score["matched"], 7)
        self.assertEqual(score["wrong_provider_kept"], 1)
        self.assertEqual(score["unsupported_kept"], 0)
        self.assertEqual(score["refused_malformed"], 1)
        self.assertEqual(
            score["dropped"],
            {
                "dropped: figure_in_post": 1,
                "dropped: provider_attributed": 1,
                "dropped: post_in_thread": 1,
            },
        )
        self.assertFalse(score["go"])
        self.assertIn("baseline_ms", score["probe"])


if __name__ == "__main__":
    unittest.main()
