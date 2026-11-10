"""The Handover tab's backend: reading an event class, finding each object's story, suggesting
chat threads, and the lead's decisions and notes.

The routes need a signed-in user. The story is read from what Holly already holds; a thread
reaches it only once a lead confirms it, and a decided thread is never suggested again. Every
write is audited. No Handover module may import the assistant (the line the plan draws: nothing
in Handover sends data outside Holly).
"""

import ast
import itertools
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx2
import pytest
from sqlalchemy.dialects import postgresql

from app.models.event_timer import EventTimer
from app.models.handover import HandoverNote, HandoverThreadLink
from app.models.maneuver import Maneuver
from app.models.mattermost_message import MattermostMessage
from app.models.notification import Notification
from app.models.user import User
from app.services.handover import story
from app.services.handover.taxonomy import EventObject, event_object, parse_event_class
from fakes import NOW, FakeSession, make_user, rows_result, scalar_result

UseSession = Callable[[FakeSession], FakeSession]
SignIn = Callable[[User], User]

OBJECTS = "/api/v1/handover/objects"
LINKS = "/api/v1/handover/thread-links"
POSTGRESQL = postgresql.dialect()  # type: ignore[no-untyped-call]
ROOT = Path(__file__).resolve().parent.parent
# Digits that are not ASCII, as a look-alike catalogue number would carry them.
FULLWIDTH = "NAME (" + chr(0xFF11) + chr(0xFF12) + ")"
_IDS = itertools.count(1)


def synthetic_id() -> uuid.UUID:
    return uuid.UUID(f"00000000-0000-4000-8000-{next(_IDS):012d}")


def notice(**fields: Any) -> Notification:
    values: dict[str, Any] = {
        "id": synthetic_id(),
        "udl_id": f"UDL-{next(_IDS)}",
        "notso_identifier": "TEST-0001",
        "event_class": "Maneuver / TEST-SAT 1 (90001) / GEO",
        "status": "OPEN",
        "sat_ids": ["90001"],
        "sat_no": None,
        "source": "TEST-SOURCE",
        "raw": {},
        "created_at": NOW,
        "updated_at": NOW,
        "udl_created_at": NOW - timedelta(hours=3),
    }
    return Notification(**(values | fields))


def maneuver(**fields: Any) -> Maneuver:
    values: dict[str, Any] = {
        "id": synthetic_id(),
        "udl_id": "TEST-MNVR",
        "sat_no": 90001,
        "source": "TEST-PROVIDER",
        "event_start_time": NOW - timedelta(hours=2),
        "raw": {"deltaVel": 0.002},
        "created_at": NOW,
        "updated_at": NOW,
    }
    return Maneuver(**(values | fields))


def message(
    post_id: str, text: str, *, root: str | None = None, minutes: int = 0
) -> MattermostMessage:
    return MattermostMessage(
        id=synthetic_id(),
        mm_post_id=post_id,
        root_id=root,
        channel_id="chan-1",
        channel_name="Example Channel",
        user_id="user-1",
        user_display_name="Example Analyst",
        posted_at=NOW - timedelta(hours=1) + timedelta(minutes=minutes),
        message=text,
        post_type=None,
        raw={},
        created_at=NOW,
        updated_at=NOW,
    )


def link(thread_id: str, event_key: str, decision: str = "confirmed") -> HandoverThreadLink:
    return HandoverThreadLink(
        id=synthetic_id(),
        thread_id=thread_id,
        event_key=event_key,
        decision=decision,
        decided_by=None,
        decided_at=NOW - timedelta(minutes=30),
        created_at=NOW,
        updated_at=NOW,
    )


def sent(session: FakeSession, index: int) -> str:
    query = session.execute.await_args_list[index].args[0].compile(dialect=POSTGRESQL)
    return " ".join(str(query).split())


def params(session: FakeSession, index: int) -> dict[str, Any]:
    return dict(session.execute.await_args_list[index].args[0].compile(dialect=POSTGRESQL).params)


@dataclass
class AuditCall:
    after_commit: bool
    fields: dict[str, Any]


@pytest.fixture(autouse=True)
def audits(monkeypatch: pytest.MonkeyPatch) -> list[AuditCall]:
    calls: list[AuditCall] = []

    def record(db: FakeSession, **fields: Any) -> None:
        calls.append(AuditCall(db.commit.await_count > 0, fields))

    monkeypatch.setattr("app.api.v1.routes.handover.write_audit", AsyncMock(side_effect=record))
    return calls


class TestTheEventClass:
    def test_kind_objects_and_regime_are_read_apart(self) -> None:
        parsed = parse_event_class("  Maneuver /  CHINASAT  3B (64062) / geo ")
        assert parsed is not None
        assert parsed.kind_label == "Maneuver"
        assert parsed.objects == (EventObject("CHINASAT 3B", 64062),)
        assert parsed.regime == "GEO"

    def test_both_objects_of_an_rpo_are_read(self) -> None:
        parsed = parse_event_class("RPO / RED-1 (90001) vs. BLUE-1 (90002)")
        assert parsed is not None
        assert parsed.objects == (EventObject("RED-1", 90001), EventObject("BLUE-1", 90002))
        assert parsed.regime is None

    @pytest.mark.parametrize("text", [None, "", " / / "])
    def test_nothing_to_read_is_none(self, text: str | None) -> None:
        assert parse_event_class(text) is None

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("NAME (12A)", EventObject("NAME (12A)", None)),
            ("(64062)", EventObject("64062", 64062)),
            ("NAME (1234567890)", EventObject("NAME (1234567890)", None)),
            (FULLWIDTH, EventObject(FULLWIDTH, None)),
            ("N" * 200, EventObject("N" * 120, None)),
        ],
    )
    def test_a_catalogue_number_is_only_ascii_digits_in_the_last_brackets(
        self, text: str, expected: EventObject
    ) -> None:
        assert event_object(text) == expected


class TestTheObjects:
    def test_a_notice_names_objects_in_its_list_its_number_and_its_class(self) -> None:
        n = notice(
            sat_ids=["90001", "not-a-number", 7],
            sat_no=90003,
            event_class="RPO / RED-1 (90001) vs BLUE-1 (90002)",
        )
        assert story.catalogue_numbers(n) == {90001: "RED-1", 90003: None, 90002: "BLUE-1"}

    def test_a_list_that_is_not_a_list_is_ignored(self) -> None:
        assert story.catalogue_numbers(notice(sat_ids="90001", event_class=None)) == {}

    def test_objects_are_tallied_and_listed_newest_first(self) -> None:
        older = notice(udl_created_at=NOW - timedelta(hours=9))
        newer = notice(
            sat_ids=["90002"],
            event_class="Photometric change / BLUE-1 (90002)",
            udl_created_at=NOW - timedelta(hours=1),
        )
        timeless = notice(sat_ids=["90003"], event_class=None, udl_created_at=None)
        both = notice(udl_created_at=NOW - timedelta(hours=2), event_class="RPO / A (90001)")
        tallies = story.tally_objects([older, newer, timeless, both])
        objects = story.objects_from(tallies, {90001: 4})
        assert [o.sat_no for o in objects] == [90002, 90001, 90003]
        first = objects[1]
        assert (first.name, first.kinds, first.events, first.maneuvers) == (
            "TEST-SAT 1",
            ["Maneuver", "RPO"],
            2,
            4,
        )
        assert first.latest_at == NOW - timedelta(hours=2)


class TestTheSuggestions:
    def mentions(self) -> story.Mentions:
        older = notice(notso_identifier="ABC-0001", event_id="EVT-1")
        newer = notice(notso_identifier="ABC-0002", notice_id="ABC-0002", event_id="EVT-2")
        short = notice(notso_identifier="X1", event_id="EVT-3")
        return story.mentions_for(90001, [older, newer, short])

    def test_notso_numbers_lead_to_their_event_and_the_number_to_the_latest(self) -> None:
        mentions = self.mentions()
        assert mentions.notice_ids == {"abc-0002": "EVT-2", "abc-0001": "EVT-1"}
        assert mentions.latest_event == "EVT-3"
        assert mentions.match("see abc-0001 please") == ("EVT-1", "Mentions NOTSO ABC-0001")
        assert mentions.match("90001 moved") == ("EVT-3", "Mentions catalogue number 90001")
        assert mentions.match("1900011 and 900010 are other objects") is None

    def test_no_notices_means_no_event_to_suggest(self) -> None:
        mentions = story.mentions_for(90001, [])
        assert mentions.match("90001 moved") is None

    def test_the_database_condition_matches_whole_numbers_and_escapes_wildcards(self) -> None:
        mentions = story.Mentions(90001, {"a%b_c": "EVT-1"}, "EVT-1")
        compiled = mentions.condition().compile(dialect=POSTGRESQL)
        assert "~" in str(compiled)
        assert "(^|[^0-9])90001([^0-9]|$)" in compiled.params.values()
        assert "%a\\%b\\_c%" in compiled.params.values()

    def test_one_suggestion_per_undecided_thread_from_its_earliest_post(self) -> None:
        mentions = self.mentions()
        posts = [
            message("p3", "more on 90001", root="p1", minutes=3),
            message("p1", "ABC-0002 burn seen", minutes=1),
            message("p4", "nothing here", root="p9"),
            message("p5", "decided ABC-0001", root="decided"),
            message("p6", "90001 in another thread", minutes=5),
        ]
        found = story.suggestions_from(posts, mentions, decided_threads={"decided"})
        assert [(s.thread_id, s.event_key, s.matching_posts) for s in found] == [
            ("p1", "EVT-2", 2),
            ("p6", "EVT-3", 1),
        ]
        assert found[0].reason == "Mentions NOTSO ABC-0002"
        assert found[0].first_post.post_id == "p1"

    def test_suggestions_stop_at_the_cap(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(story, "SUGGESTION_CAP", 1)
        posts = [message("p1", "90001", minutes=1), message("p2", "90001", minutes=2)]
        assert len(story.suggestions_from(posts, self.mentions(), set())) == 1


class TestTheThreads:
    def test_only_confirmed_threads_are_told_with_their_posts_in_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(story, "POSTS_PER_THREAD", 2)
        posts = [
            message("r2", "third", root="t1", minutes=3),
            message("t1", "first", minutes=1),
            message("r1", "second", root="t1", minutes=2),
        ]
        links = [link("t1", "EVT-1"), link("t2", "EVT-1", "rejected"), link("t3", "EVT-2")]
        threads = story.threads_from(links, posts)
        assert [(t.thread_id, t.truncated) for t in threads] == [("t1", True), ("t3", False)]
        assert [p.post_id for p in threads[0].posts] == ["t1", "r1"]
        assert threads[0].channel_name == "Example Channel"
        assert threads[1].posts == []
        assert threads[1].channel_name is None


async def test_the_handover_routes_need_sign_in(
    api: httpx2.AsyncClient, use_session: UseSession
) -> None:
    session = use_session(FakeSession())
    for method, url in [
        ("GET", OBJECTS),
        ("GET", f"{OBJECTS}/90001"),
        ("POST", LINKS),
        ("POST", f"{OBJECTS}/90001/notes"),
        ("DELETE", f"/api/v1/handover/notes/{uuid.uuid4()}"),
    ]:
        response = await api.request(method, url)
        assert response.status_code == 401, url
    session.execute.assert_not_awaited()


class TestTheObjectList:
    async def test_an_empty_window_reads_only_the_notices(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        session = use_session(FakeSession([rows_result([])]))
        response = await api.get(OBJECTS, params={"hours": 24})
        body = response.json()
        assert response.status_code == 200
        assert (body["objects"], body["window_hours"], body["truncated"]) == ([], 24, False)
        assert session.execute.await_count == 1

    async def test_objects_carry_their_maneuver_counts(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        counts = MagicMock()
        counts.all.return_value = [(90001, 3), (None, 9)]
        session = use_session(FakeSession([rows_result([notice()]), counts]))
        body = (await api.get(OBJECTS)).json()
        assert body["window_hours"] == 120
        assert body["objects"] == [
            {
                "sat_no": 90001,
                "name": "TEST-SAT 1",
                "kinds": ["Maneuver"],
                "latest_at": "2026-06-05T09:00:00Z",
                "events": 1,
                "maneuvers": 3,
            }
        ]
        assert "DISTINCT ON" in sent(session, 0)
        assert "GROUP BY maneuver.sat_no" in sent(session, 1)

    async def test_more_notices_than_the_cap_is_reported(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sign_in(make_user())
        monkeypatch.setattr(story, "OBJECT_NOTICE_CAP", 1)
        counts = MagicMock()
        counts.all.return_value = []
        use_session(FakeSession([rows_result([notice(), notice()]), counts]))
        assert (await api.get(OBJECTS)).json()["truncated"] is True

    async def test_a_window_out_of_range_is_refused(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        use_session(FakeSession())
        assert (await api.get(OBJECTS, params={"hours": 337})).status_code == 422


class TestTheStory:
    async def test_an_object_with_nothing_held_has_an_empty_story(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        session = use_session(
            FakeSession([rows_result([]), rows_result([]), rows_result([]), rows_result([])])
        )
        body = (await api.get(f"{OBJECTS}/90001")).json()
        assert body["notices"] == body["threads"] == body["suggestions"] == body["notes"] == []
        assert body["name"] is None
        # Notices, maneuvers, suggestion candidates and notes: no links or timers without notices.
        assert session.execute.await_count == 4
        assert "notification.sat_ids @>" in sent(session, 0)
        assert "LIKE" in sent(session, 0)

    async def test_the_story_brings_every_source_together(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        author = sign_in(make_user(username="example-lead"))
        first = notice(event_id="EVT-1", notso_identifier="ABC-0001")
        later = notice(event_id="EVT-1", notso_identifier="ABC-0001", status="VERIFIED")
        note = HandoverNote(
            id=synthetic_id(),
            sat_no=90001,
            author_id=author.id,
            text="Watch the approach.",
            created_at=NOW,
        )
        timer = EventTimer(
            id=synthetic_id(), label="Closest approach", target_time=NOW, event_key="EVT-1"
        )
        names = MagicMock()
        names.all.return_value = [(author.id, "example-lead")]
        session = use_session(
            FakeSession(
                [
                    rows_result([first, later]),
                    rows_result([maneuver()]),
                    rows_result([link("t1", "EVT-1"), link("t2", "EVT-1", "rejected")]),
                    rows_result([message("t1", "ABC-0001 confirmed thread")]),
                    rows_result(
                        [message("t2", "ABC-0001 rejected"), message("t5", "ABC-0001 new")]
                    ),
                    rows_result([timer]),
                    rows_result([note]),
                    names,
                ]
            )
        )
        body = (await api.get(f"{OBJECTS}/90001")).json()
        assert body["name"] == "TEST-SAT 1"
        assert [n["status"] for n in body["notices"]] == ["OPEN", "VERIFIED"]
        assert body["notices"][0]["event_key"] == "EVT-1"
        assert body["notices"][0]["kind"] == "Maneuver"
        assert body["maneuvers"][0]["facts"]["delta_vel_kms"] == 0.002
        assert [t["thread_id"] for t in body["threads"]] == ["t1"]
        assert [s["thread_id"] for s in body["suggestions"]] == ["t5"]
        assert body["timers"][0]["label"] == "Closest approach"
        assert body["notes"][0]["author"] == "example-lead"
        assert body["truncated"] is False
        assert "coalesce(mattermost_message.root_id, mattermost_message.mm_post_id) IN" in sent(
            session, 3
        )
        assert "mattermost_channel.following IS false" in sent(session, 4)
        assert "event_timer.dismissed_at IS NULL" in sent(session, 5)

    async def test_a_note_author_who_is_gone_is_left_unnamed(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        note = HandoverNote(
            id=synthetic_id(), sat_no=90001, author_id=None, text="Old.", created_at=NOW
        )
        use_session(
            FakeSession([rows_result([]), rows_result([]), rows_result([]), rows_result([note])])
        )
        body = (await api.get(f"{OBJECTS}/90001")).json()
        assert body["notes"][0]["author"] is None

    @pytest.mark.parametrize("sat_no", ["0", "1000000000", "abc"])
    async def test_a_number_out_of_range_is_refused(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn, sat_no: str
    ) -> None:
        sign_in(make_user())
        use_session(FakeSession())
        assert (await api.get(f"{OBJECTS}/{sat_no}")).status_code == 422


class TestTheLinkDecisions:
    def found(self, *more: Any) -> FakeSession:
        return FakeSession([scalar_result(uuid.uuid4()), scalar_result(uuid.uuid4()), *more])

    async def test_a_confirmation_is_stored_and_audited_before_the_commit(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        audits: list[AuditCall],
    ) -> None:
        user = sign_in(make_user())
        session = use_session(self.found(MagicMock()))
        body = {"thread_id": "thread-1", "event_key": " EVT-1 ", "decision": "confirmed"}
        response = await api.post(LINKS, json=body)
        assert response.status_code == 200
        assert response.json() == {
            "thread_id": "thread-1",
            "event_key": "EVT-1",
            "decision": "confirmed",
        }
        assert "ON CONFLICT ON CONSTRAINT uq_handover_thread_link DO UPDATE" in sent(session, 2)
        assert params(session, 2)["decided_by"] == user.id
        [call] = audits
        assert call.after_commit is False
        assert call.fields["action_type"] == "handover.thread_link"
        assert call.fields["detail"] == {"event_key": "EVT-1", "decision": "confirmed"}
        session.commit.assert_awaited_once()

    async def test_clearing_deletes_the_decision(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        session = use_session(self.found(MagicMock()))
        body = {"thread_id": "thread-1", "event_key": "EVT-1", "decision": "clear"}
        assert (await api.post(LINKS, json=body)).status_code == 200
        assert sent(session, 2).startswith("DELETE FROM handover_thread_link")

    @pytest.mark.parametrize(
        "answers",
        [
            [scalar_result(None), scalar_result(uuid.uuid4())],
            [scalar_result(uuid.uuid4()), scalar_result(None)],
        ],
    )
    async def test_an_unknown_notice_or_thread_is_refused(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        answers: list[Any],
        audits: list[AuditCall],
    ) -> None:
        sign_in(make_user())
        session = use_session(FakeSession(answers))
        body = {"thread_id": "thread-1", "event_key": "EVT-1", "decision": "rejected"}
        assert (await api.post(LINKS, json=body)).status_code == 404
        assert audits == []
        session.commit.assert_not_awaited()

    @pytest.mark.parametrize(
        "body",
        [
            {"thread_id": "has space", "event_key": "EVT-1", "decision": "confirmed"},
            {"thread_id": "t" * 65, "event_key": "EVT-1", "decision": "confirmed"},
            {"thread_id": "t", "event_key": "", "decision": "confirmed"},
            {"thread_id": "t", "event_key": "EVT-1", "decision": "maybe"},
            {"thread_id": "t", "event_key": "EVT-1", "decision": "confirmed", "extra": 1},
        ],
    )
    async def test_a_malformed_decision_is_refused(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        body: dict[str, Any],
    ) -> None:
        sign_in(make_user())
        session = use_session(FakeSession())
        assert (await api.post(LINKS, json=body)).status_code == 422
        session.execute.assert_not_awaited()


class TestTheNotes:
    async def test_a_note_is_stored_trimmed_and_audited(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        audits: list[AuditCall],
    ) -> None:
        user = sign_in(make_user(username="example-lead"))
        session = use_session(FakeSession())

        def stamp(note: HandoverNote) -> None:
            note.created_at = NOW

        session.refresh.side_effect = stamp
        response = await api.post(
            f"{OBJECTS}/90001/notes", json={"text": "  Watch the approach.  "}
        )
        assert response.status_code == 201
        [note] = session.added
        assert (note.sat_no, note.text, note.author_id) == (90001, "Watch the approach.", user.id)
        assert response.json()["author"] == "example-lead"
        [call] = audits
        assert call.fields["action_type"] == "handover.note.create"
        assert call.fields["detail"] == {"sat_no": 90001, "length": 19}
        assert call.after_commit is False

    @pytest.mark.parametrize("text", ["   ", "", "x" * 4001, "bad\x00text"])
    async def test_a_blank_long_or_unstorable_note_is_refused(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn, text: str
    ) -> None:
        sign_in(make_user())
        session = use_session(FakeSession())
        response = await api.post(f"{OBJECTS}/90001/notes", json={"text": text})
        assert response.status_code in {400, 422}
        assert session.added == []

    async def test_a_note_is_deleted_and_audited(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        audits: list[AuditCall],
    ) -> None:
        sign_in(make_user())
        note = HandoverNote(
            id=synthetic_id(), sat_no=90001, author_id=None, text="Old.", created_at=NOW
        )
        session = use_session(FakeSession([scalar_result(note)]))
        assert (await api.delete(f"/api/v1/handover/notes/{note.id}")).status_code == 204
        session.delete.assert_awaited_once_with(note)
        assert audits[0].fields["detail"] == {"sat_no": 90001}

    async def test_an_unknown_note_is_not_found(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        use_session(FakeSession([scalar_result(None)]))
        assert (await api.delete(f"/api/v1/handover/notes/{uuid.uuid4()}")).status_code == 404


def test_no_handover_module_imports_the_assistant() -> None:
    """Handover reads chat; the assistant sends text to an outside AI service. The two never
    meet: a Handover module that imports the assistant or its client fails the build."""
    files = [
        ROOT / "src/app/api/v1/routes/handover.py",
        *(ROOT / "src/app/services/handover").glob("*.py"),
    ]
    banned = {"app.services.claude", "app.services.assistant", "anthropic"}
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module, *(f"{node.module}.{a.name}" for a in node.names)]
            assert not any(n == b or n.startswith(f"{b}.") for n in names for b in banned), path
    assert len(files) >= 4
