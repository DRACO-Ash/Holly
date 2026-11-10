"""The Handover tab's backend: reading an event class, finding each object's story, suggesting
chat threads, and the lead's decisions and notes.

The routes need a signed-in user. The story is read from what Holly already holds; a thread
reaches it only once a lead confirms it, and a decided thread is never suggested again. Every
write is audited. No Handover module may import the assistant (the line the plan draws: nothing
in Handover sends data outside Holly).
"""

import ast
import itertools
import os
import subprocess
import sys
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

    def test_suggestions_stop_one_past_the_cap_so_the_cut_can_be_told(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(story, "SUGGESTION_CAP", 1)
        posts = [message(f"p{i}", "90001", minutes=i) for i in range(4)]
        assert len(story.suggestions_from(posts, self.mentions(), set())) == 2


class TestWhichNoticesNameTheObject:
    def test_the_database_cut_reads_the_number_as_written_or_zero_padded(self) -> None:
        compiled = story.names_object(123).compile(dialect=POSTGRESQL)
        values = list(compiled.params.values())
        assert ["123"] in values
        assert ["000000123"] in values
        assert "%(000123)%" in values
        assert "notification.sat_no =" in str(compiled)
        assert story.written_forms(123456789) == ["123456789"]

    def test_only_a_notice_the_parser_reads_as_naming_it_counts(self) -> None:
        padded = notice(sat_ids=["090001"], event_class=None)
        loose = notice(sat_ids=[], event_class="Maneuver / OTHER (90001) said once")
        assert story.names(padded, 90001) is True
        assert story.names(loose, 90001) is False


class TestTheThreads:
    def test_a_thread_confirmed_against_two_notices_is_told_once_newest_first(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(story, "POSTS_PER_THREAD", 2)
        posts = [
            message("r2", "third", root="t1", minutes=3),
            message("t1", "first", minutes=1),
            message("r1", "second", root="t1", minutes=2),
            message("t3", "only", minutes=4),
        ]
        newer = link("t3", "EVT-2")
        newer.decided_at = NOW
        links = [
            link("t1", "EVT-2"),
            link("t1", "EVT-1"),
            link("t2", "EVT-1", "rejected"),
            newer,
            link("t4", "EVT-1"),  # confirmed, but none of its posts were read
        ]
        threads = story.threads_from(links, posts)
        assert [(t.thread_id, t.event_keys, t.truncated) for t in threads] == [
            ("t3", ["EVT-2"], False),
            ("t1", ["EVT-1", "EVT-2"], True),
        ]
        assert [p.post_id for p in threads[1].posts] == ["t1", "r1"]
        assert threads[1].channel_name == "Example Channel"

    def test_the_newest_confirmed_threads_are_read_and_the_cut_told(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(story, "THREAD_CAP", 1)
        old, new = link("old", "EVT-1"), link("new", "EVT-1")
        new.decided_at = NOW
        again = link("old", "EVT-2")
        again.decided_at = NOW - timedelta(hours=5)
        assert story.newest_confirmed([old, new, again, link("no", "EVT-1", "rejected")]) == (
            ["new"],
            True,
        )
        assert story.newest_confirmed([old]) == (["old"], False)


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

    async def test_objects_carry_their_maneuver_counts_in_the_window(
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
        assert "maneuver.event_start_time >=" in sent(session, 1)
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


def note_row(author_id: uuid.UUID | None = None, text: str = "Watch the approach.") -> HandoverNote:
    return HandoverNote(
        id=synthetic_id(), sat_no=90001, author_id=author_id, text=text, created_at=NOW
    )


class TestTheStory:
    async def test_an_object_with_nothing_held_has_an_empty_story(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        session = use_session(FakeSession([rows_result([])] * 4))
        body = (await api.get(f"{OBJECTS}/90001")).json()
        assert body["notices"] == body["threads"] == body["suggestions"] == body["notes"] == []
        assert body["name"] is None
        assert body["truncated"] is False
        # Notices, maneuvers, suggestion candidates and notes: no links or timers without notices.
        assert session.execute.await_count == 4
        notices_sql = sent(session, 0)
        assert "notification.udl_created_at >=" in notices_sql
        assert "notification.sat_no =" in notices_sql
        assert "notification.sat_ids @>" in notices_sql
        assert "ORDER BY notification.udl_created_at DESC" in notices_sql
        assert "ORDER BY maneuver.event_start_time DESC" in sent(session, 1)
        candidates_sql = sent(session, 2)
        assert "mattermost_message.posted_at >=" in candidates_sql
        assert "mattermost_channel.following IS false" in candidates_sql
        assert "ORDER BY handover_note.created_at DESC" in sent(session, 3)

    async def test_the_story_brings_every_source_together(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        author = sign_in(make_user(username="example-lead"))
        first = notice(event_id="EVT-1", notso_identifier="ABC-0001")
        later = notice(
            event_id="EVT-1",
            notso_identifier="ABC-0001",
            status="VERIFIED",
            udl_created_at=NOW - timedelta(hours=1),
        )
        other = notice(sat_ids=[], event_class="Maneuver / ELSE (90001) aside")
        timer = EventTimer(
            id=synthetic_id(), label="Closest approach", target_time=NOW, event_key="EVT-1"
        )
        names = MagicMock()
        names.all.return_value = [(author.id, "example-lead")]
        session = use_session(
            FakeSession(
                [
                    rows_result([later, other, first]),
                    rows_result([maneuver()]),
                    rows_result([link("t1", "EVT-1"), link("t2", "EVT-1", "rejected")]),
                    rows_result([message("t1", "ABC-0001 confirmed thread")]),
                    rows_result(
                        [message("t2", "ABC-0001 rejected"), message("t5", "ABC-0001 new")]
                    ),
                    rows_result([timer]),
                    rows_result([note_row(author.id)]),
                    names,
                ]
            )
        )
        body = (await api.get(f"{OBJECTS}/90001")).json()
        assert body["name"] == "TEST-SAT 1"
        # Read newest first, told oldest first; the notice the parser does not read is left out.
        assert [n["status"] for n in body["notices"]] == ["OPEN", "VERIFIED"]
        assert body["notices"][0]["event_key"] == "EVT-1"
        assert body["notices"][0]["kind"] == "Maneuver"
        assert body["maneuvers"][0]["facts"]["delta_vel_kms"] == 0.002
        assert [(t["thread_id"], t["event_keys"]) for t in body["threads"]] == [("t1", ["EVT-1"])]
        assert [s["thread_id"] for s in body["suggestions"]] == ["t5"]
        assert body["timers"][0]["label"] == "Closest approach"
        assert body["notes"][0]["author"] == "example-lead"
        assert body["truncated"] is False
        posts_sql = sent(session, 3)
        assert "row_number() OVER (PARTITION BY coalesce(" in posts_sql
        assert "anon_1.rank <=" in posts_sql
        assert story.POSTS_PER_THREAD + 1 in params(session, 3).values()
        assert "mattermost_message.root_id IN" in posts_sql
        assert "mattermost_channel.following IS false" in posts_sql
        assert "event_timer.dismissed_at IS NULL" in sent(session, 5)

    @pytest.mark.parametrize("cap", ["STORY_NOTICE_CAP", "STORY_MANEUVER_CAP"])
    async def test_over_a_cap_the_newest_are_kept_and_the_cut_told(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        monkeypatch: pytest.MonkeyPatch,
        cap: str,
    ) -> None:
        sign_in(make_user())
        monkeypatch.setattr(story, cap, 1)
        newest = notice(event_id="EVT-NEW", udl_created_at=NOW - timedelta(hours=1))
        oldest = notice(event_id="EVT-OLD", udl_created_at=NOW - timedelta(hours=9))
        new_m = maneuver(udl_id="NEW", event_start_time=NOW - timedelta(hours=1))
        old_m = maneuver(udl_id="OLD", event_start_time=NOW - timedelta(hours=9))
        use_session(
            FakeSession(
                [
                    rows_result([newest, oldest]),
                    rows_result([new_m, old_m]),
                    rows_result([]),
                    rows_result([]),
                    rows_result([]),
                    rows_result([]),
                ]
            )
        )
        body = (await api.get(f"{OBJECTS}/90001")).json()
        assert body["truncated"] is True
        if cap == "STORY_NOTICE_CAP":
            assert [n["event_key"] for n in body["notices"]] == ["EVT-NEW"]
        else:
            assert [m["udl_id"] for m in body["maneuvers"]] == ["NEW"]

    @pytest.mark.parametrize("cap", ["TIMER_CAP", "NOTE_CAP", "SUGGESTION_CAP", "THREAD_CAP"])
    async def test_every_other_cap_is_told_too(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        monkeypatch: pytest.MonkeyPatch,
        cap: str,
    ) -> None:
        sign_in(make_user())
        monkeypatch.setattr(story, cap, 1)
        timer = EventTimer(id=synthetic_id(), label="T", target_time=NOW, event_key="EVT-1")
        names = MagicMock()
        names.all.return_value = []
        use_session(
            FakeSession(
                [
                    rows_result([notice(event_id="EVT-1", notso_identifier="ABC-0001")]),
                    rows_result([]),
                    rows_result([link("t1", "EVT-1"), link("t2", "EVT-1")]),
                    rows_result([message("t1", "kept"), message("t2", "kept")]),
                    rows_result([message("s1", "ABC-0001"), message("s2", "ABC-0001")]),
                    rows_result([timer, timer]),
                    rows_result([note_row(), note_row()]),
                    names,
                ]
            )
        )
        assert (await api.get(f"{OBJECTS}/90001")).json()["truncated"] is True

    async def test_a_note_author_who_is_gone_is_left_unnamed(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        use_session(FakeSession([rows_result([])] * 3 + [rows_result([note_row(text="Old.")])]))
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
        held = notice(event_id="EVT-1")
        return FakeSession([rows_result([held]), scalar_result(uuid.uuid4()), *more])

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
        notice_sql = sent(session, 0)
        assert "notification.event_id =" in notice_sql
        assert "LIMIT" in notice_sql
        assert 50 in params(session, 0).values()
        assert "mattermost_channel.following IS false" in sent(session, 1)
        assert "mattermost_message.root_id IN" in sent(session, 1)
        upsert = sent(session, 2)
        assert "ON CONFLICT ON CONSTRAINT uq_handover_thread_link DO UPDATE SET" in upsert
        updated = upsert.split("DO UPDATE SET", 1)[1]
        for column in ("decision", "decided_by", "decided_at", "updated_at"):
            assert f"{column} =" in updated
        assert params(session, 2)["decided_by"] == user.id
        [call] = audits
        assert call.after_commit is False
        assert call.fields["action_type"] == "handover.thread_link"
        assert call.fields["detail"] == {"event_key": "EVT-1", "decision": "confirmed"}
        session.commit.assert_awaited_once()

    async def test_clearing_needs_no_notice_or_thread_still_held(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        audits: list[AuditCall],
    ) -> None:
        sign_in(make_user())
        session = use_session(FakeSession([MagicMock()]))
        body = {"thread_id": "gone", "event_key": "EVT-GONE", "decision": "clear"}
        assert (await api.post(LINKS, json=body)).status_code == 200
        delete_sql = sent(session, 0)
        assert delete_sql.startswith("DELETE FROM handover_thread_link")
        assert "handover_thread_link.thread_id =" in delete_sql
        assert "handover_thread_link.event_key =" in delete_sql
        assert set(params(session, 0).values()) == {"gone", "EVT-GONE"}
        assert audits[0].after_commit is False

    @pytest.mark.parametrize(
        "answers",
        [
            [rows_result([])],
            # Found by its NOTSO number, but its group key is its event id.
            [rows_result([notice(event_id="EVT-9", notso_identifier="EVT-1")])],
            [rows_result([notice(event_id="EVT-1")]), scalar_result(None)],
        ],
    )
    async def test_an_unknown_notice_or_thread_or_one_switched_off_is_refused(
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
        text = "  Watch the " + chr(0x202E) + "approach." + chr(0x200B) + "  "
        response = await api.post(f"{OBJECTS}/90001/notes", json={"text": text})
        assert response.status_code == 201
        [note] = session.added
        assert (note.sat_no, note.text, note.author_id) == (90001, "Watch the approach.", user.id)
        assert response.json()["author"] == "example-lead"
        [call] = audits
        assert call.fields["action_type"] == "handover.note.create"
        assert call.fields["detail"] == {"sat_no": 90001, "length": 19}
        assert call.after_commit is False
        session.commit.assert_awaited_once()

    @pytest.mark.parametrize("text", ["   ", "", "x" * 4001, "bad\x00text", chr(0x202E)])
    async def test_a_blank_long_or_unstorable_note_is_refused(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn, text: str
    ) -> None:
        sign_in(make_user())
        session = use_session(FakeSession())
        response = await api.post(f"{OBJECTS}/90001/notes", json={"text": text})
        assert response.status_code in {400, 422}
        assert session.added == []

    async def test_a_note_is_deleted_and_audited_before_the_commit(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        audits: list[AuditCall],
    ) -> None:
        sign_in(make_user())
        note = note_row(text="Old.")
        session = use_session(FakeSession([scalar_result(note)]))
        assert (await api.delete(f"/api/v1/handover/notes/{note.id}")).status_code == 204
        session.delete.assert_awaited_once_with(note)
        [call] = audits
        assert call.fields["action_type"] == "handover.note.delete"
        assert call.fields["detail"] == {"sat_no": 90001}
        assert call.after_commit is False
        session.commit.assert_awaited_once()

    async def test_an_unknown_note_is_not_found(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        use_session(FakeSession([scalar_result(None)]))
        assert (await api.delete(f"/api/v1/handover/notes/{uuid.uuid4()}")).status_code == 404


HANDOVER_FILES = sorted(
    [
        ROOT / "src/app/api/v1/routes/handover.py",
        *(ROOT / "src/app/services/handover").glob("*.py"),
    ]
)
HANDOVER_MODULES = [
    ".".join(path.relative_to(ROOT / "src").with_suffix("").parts) for path in HANDOVER_FILES
]
BANNED = (
    "app.services.claude",
    "app.services.assistant",
    "app.services.event_summary",
    "app.api.v1.routes.assistant",
    "anthropic",
)


def test_loading_every_handover_module_loads_no_assistant() -> None:
    """Handover reads chat; the assistant sends text to an outside AI service. The two never
    meet: importing every Handover module, in a fresh interpreter, must load none of the
    assistant, its client or the Anthropic library, however they are reached. With every
    import at module level (the test below), loading is the whole of what a module imports."""
    assert "app.services.handover.story" in HANDOVER_MODULES
    script = (
        "import sys\n"
        + "".join(f"import {m}\n" for m in HANDOVER_MODULES)
        + f"print([m for m in {BANNED!r} if m in sys.modules])"
    )
    result = subprocess.run(  # noqa: S603  a fixed interpreter and script
        [sys.executable, "-c", script],
        cwd=ROOT / "src",
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )
    assert result.stdout.strip() == "[]", result.stderr


def _imported_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [a.name for a in node.names]
    if isinstance(node, ast.ImportFrom) and node.module:
        return [node.module, *(f"{node.module}.{a.name}" for a in node.names)]
    return []


def import_problems(source: str) -> list[str]:
    """What is wrong with how a Handover module imports: an import inside a function or class,
    which loading would not run; a relative import, importlib or __import__; or a banned module
    named directly, as a module or as a name imported from its package."""
    problems = [word for word in ("importlib", "__import__") if word in source]
    tree = ast.parse(source)
    top_level = {id(node) for node in tree.body}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Import | ast.ImportFrom):
            continue
        if id(node) not in top_level:
            problems.append(f"line {node.lineno}: not at module level")
        if isinstance(node, ast.ImportFrom) and node.level:
            problems.append(f"line {node.lineno}: relative import")
        names = _imported_names(node)
        if any(n == b or n.startswith(f"{b}.") for n in names for b in BANNED):
            problems.append(f"line {node.lineno}: banned import")
    return problems


def test_every_handover_import_is_at_module_level_and_plain() -> None:
    assert len(HANDOVER_FILES) >= 4
    for path in HANDOVER_FILES:
        assert import_problems(path.read_text(encoding="utf-8")) == [], path


@pytest.mark.parametrize(
    "source",
    [
        "def f():\n    from app.services import assistant\n",
        "def f():\n    import json\n",
        "from app.services import assistant\n",
        "from app.services import event_summary\n",
        "from app.api.v1.routes import assistant\n",
        "from . import story\n",
        "import anthropic\n",
        "import importlib\n",
        "x = __import__('json')\n",
    ],
)
def test_the_import_guard_refuses_each_way_round_it(source: str) -> None:
    assert import_problems(source) != []


def test_the_import_guard_allows_a_plain_module_level_import() -> None:
    assert import_problems("import json\nfrom app.models.handover import HandoverNote\n") == []
