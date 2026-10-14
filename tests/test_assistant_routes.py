"""The assistant routes: the dashboard feed with its urgency rollup and order, reading a
notification's latest evaluation, and asking for a new one under the per-user assistant limit
with an audit row. The evaluation service and the audit chain are replaced with recorders, so
these tests read exactly what each route asked of them, and each query is compiled for
PostgreSQL to read the SQL the route would send.

Every value here is synthetic: sequential ids, TEST event keys, dataMode TEST, marking U and
Example names."""

import itertools
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2
import pytest
from sqlalchemy.dialects import postgresql

from app.core.rate_limit import ASSISTANT_LIMIT
from app.models.assistant_evaluation import AssistantEvaluation
from app.models.event_summary import EventSummary
from app.models.notification import Notification
from app.models.user import User
from app.schemas.assistant import AssistantEvaluationRead
from app.services.assistant import EvaluationRun, NotificationNotFoundError
from fakes import NOW, FakeSession, make_user, rows_result, scalar_result

UseSession = Callable[[FakeSession], FakeSession]
SignIn = Callable[[User], User]

FEED = "/api/v1/assistant/feed"
NOT_EVALUATED = "No evaluation exists for this notification yet. POST to /evaluate to create one."
MODEL = "claude-test-model"

POSTGRESQL = postgresql.dialect()  # type: ignore[no-untyped-call]

_SERIALS = itertools.count(1)


def synthetic_id() -> uuid.UUID:
    """The next obviously synthetic id: 00000000-0000-4000-8000-000000000001, then 2, and so on."""
    return uuid.UUID(f"00000000-0000-4000-8000-{next(_SERIALS):012d}")


def evaluation_url(notification_id: object) -> str:
    return f"/api/v1/assistant/evaluation/{notification_id}"


def evaluate_url(notification_id: object) -> str:
    return f"/api/v1/assistant/evaluate/{notification_id}"


class AuditRecorder:
    """Stands in for write_audit: records the fields of each row a route asks it to write."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def write(self, _db: object, **fields: Any) -> None:
        self.rows.append(fields)


class EvaluationService:
    """Stands in for evaluate_once: records each notification asked about, then answers with
    `outcome`, a stored run or an exception to raise."""

    def __init__(self) -> None:
        self.asked: list[uuid.UUID] = []
        self.outcome: EvaluationRun | Exception = NotificationNotFoundError("nothing queued")

    async def evaluate_once(self, notification_id: uuid.UUID) -> EvaluationRun:
        self.asked.append(notification_id)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.fixture(autouse=True)
def audit(monkeypatch: pytest.MonkeyPatch) -> AuditRecorder:
    recorder = AuditRecorder()
    monkeypatch.setattr("app.api.v1.routes.assistant.write_audit", recorder.write)
    return recorder


@pytest.fixture(autouse=True)
def service(monkeypatch: pytest.MonkeyPatch) -> EvaluationService:
    """No test reaches the real service, which would open a database session of its own."""
    fake = EvaluationService()
    monkeypatch.setattr("app.api.v1.routes.assistant.evaluate_once", fake.evaluate_once)
    return fake


@pytest.fixture(autouse=True)
def feed_window(settings_env: Callable[..., None]) -> None:
    """Pin the feed's default window, whatever a local .env file holds."""
    settings_env(BACKGROUND_NOTIFICATION_WINDOW_HOURS="120")


def analyst(sign_in: SignIn, username: str = "example-analyst") -> User:
    """Sign in a synthetic analyst for every request that follows."""
    user = make_user(username=username)
    user.id = synthetic_id()
    return sign_in(user)


def make_notification(**fields: Any) -> Notification:
    """A notification row as the database returns it."""
    values: dict[str, Any] = {
        "id": synthetic_id(),
        "udl_id": None,
        "data_mode": "TEST",
        "classification_marking": "U",
        "raw": {},
        "created_at": NOW,
        "updated_at": NOW,
        "udl_created_at": NOW,
    }
    return Notification(**(values | fields))


def hours_ago(hours: int) -> datetime:
    return NOW - timedelta(hours=hours)


def action(urgency: object, text: object = "Notify the duty officer") -> dict[str, object]:
    return {"action": text, "urgency": urgency, "deadline": None, "rationale": "Example step 1."}


def make_evaluation(
    notification: Notification,
    next_actions: list[Any] | None = None,
    *,
    error: str | None = None,
    evaluated_at: datetime = NOW,
) -> AssistantEvaluation:
    """A stored evaluation; next_actions None leaves the field out of the structured reply."""
    structured: dict[str, Any] = {
        "summary": "Example summary.",
        "applicable_procedures": [],
        "open_questions": [],
    }
    if next_actions is not None:
        structured["next_actions"] = next_actions
    return AssistantEvaluation(
        id=synthetic_id(),
        notification_id=notification.id,
        summary="Example summary.",
        structured=structured,
        procedures_used=[],
        model=MODEL,
        error=error,
        evaluated_at=evaluated_at,
    )


def event_summary(
    event_key: str, narrative: str, publication_count: int, *, error: str | None = None
) -> EventSummary:
    return EventSummary(
        id=synthetic_id(),
        event_key=event_key,
        narrative=narrative,
        source_notification_ids=[],
        publication_count=publication_count,
        error=error,
    )


def feed_session(
    notifications: Sequence[Notification],
    evaluations: Sequence[AssistantEvaluation] = (),
    summaries: Sequence[EventSummary] = (),
) -> FakeSession:
    """A session answering the feed's three queries in order: the window's notifications,
    their evaluations and their event summaries."""
    return FakeSession(
        [
            rows_result(list(notifications)),
            rows_result(list(evaluations)),
            rows_result(list(summaries)),
        ]
    )


def sent(session: FakeSession, index: int) -> tuple[str, dict[str, Any]]:
    """The session's `index`th query as PostgreSQL would receive it: the SQL on one line, and
    the bound values."""
    query = session.execute.await_args_list[index].args[0].compile(dialect=POSTGRESQL)
    return " ".join(str(query).split()), dict(query.params)


def stored_run(notification_id: uuid.UUID, *, error: str | None = None) -> EvaluationRun:
    """What evaluate_once returns once an evaluation is stored."""
    failed = error is not None
    evaluation = AssistantEvaluationRead(
        id=synthetic_id(),
        notification_id=notification_id,
        summary="Assistant evaluation could not be generated." if failed else "Example summary.",
        structured={
            "summary": "Example summary.",
            "applicable_procedures": [],
            "next_actions": [] if failed else [action("high")],
            "open_questions": [],
        },
        procedures_used=["00000000-0000-4000-8000-000000000999"],
        model=MODEL,
        error=error,
        evaluated_at=NOW,
    )
    return EvaluationRun(evaluation=evaluation, persistent_failure=False)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", FEED),
        ("GET", evaluation_url("00000000-0000-4000-8000-000000000001")),
        ("POST", evaluate_url("00000000-0000-4000-8000-000000000001")),
    ],
)
async def test_every_assistant_route_requires_sign_in(
    api: httpx2.AsyncClient,
    use_session: UseSession,
    service: EvaluationService,
    method: str,
    path: str,
) -> None:
    session = use_session(FakeSession())
    response = await api.request(method, path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    session.execute.assert_not_awaited()
    assert service.asked == []


class TestFeed:
    async def test_an_empty_window_has_no_items_and_reads_nothing_more(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        analyst(sign_in)
        session = use_session(FakeSession([rows_result([])]))
        response = await api.get(FEED)
        assert response.status_code == 200
        assert response.json() == {"items": [], "window_hours": 120}
        assert session.execute.await_count == 1

    async def test_the_window_and_limit_default_to_the_background_window_and_100(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        settings_env: Callable[..., None],
    ) -> None:
        settings_env(BACKGROUND_NOTIFICATION_WINDOW_HOURS="48")
        analyst(sign_in)
        session = use_session(FakeSession([rows_result([])]))
        before = datetime.now(UTC)
        response = await api.get(FEED)
        after = datetime.now(UTC)
        assert response.json()["window_hours"] == 48
        _sql, params = sent(session, 0)
        window = timedelta(hours=48)
        assert before - window <= params["udl_created_at_1"] <= after - window
        assert params["param_1"] == 100

    async def test_hours_and_limit_shape_the_deduplicated_query(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        analyst(sign_in)
        session = use_session(FakeSession([rows_result([])]))
        before = datetime.now(UTC)
        response = await api.get(FEED, params={"hours": 6, "limit": 7})
        after = datetime.now(UTC)
        assert response.json() == {"items": [], "window_hours": 6}
        sql, params = sent(session, 0)
        assert (
            "SELECT DISTINCT ON (coalesce(notification.event_id, "
            "notification.notso_identifier, notification.udl_id))"
        ) in sql
        assert "WHERE notification.udl_created_at >= %(udl_created_at_1)s" in sql
        assert sql.endswith("ORDER BY anon_1.udl_created_at DESC LIMIT %(param_1)s::INTEGER")
        window = timedelta(hours=6)
        assert before - window <= params["udl_created_at_1"] <= after - window
        assert params["param_1"] == 7

    @pytest.mark.parametrize(
        "params",
        [{"limit": 0}, {"limit": 501}, {"hours": 0}, {"hours": 721}, {"hours": "soon"}],
    )
    async def test_a_limit_or_window_outside_its_bounds_is_422(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        params: dict[str, int | str],
    ) -> None:
        analyst(sign_in)
        session = use_session(FakeSession())
        assert (await api.get(FEED, params=params)).status_code == 422
        session.execute.assert_not_awaited()

    async def test_each_item_carries_its_evaluation_and_its_event_summary(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        analyst(sign_in)
        by_event = make_notification(
            event_id="TEST-EVENT-1", notso_identifier="TEST-NOTSO-1", udl_id="TEST-UDL-1"
        )
        by_notice = make_notification(
            notso_identifier="TEST-NOTSO-2", udl_id="TEST-UDL-2", udl_created_at=hours_ago(1)
        )
        by_record = make_notification(udl_id="TEST-UDL-3", udl_created_at=hours_ago(2))
        evaluation = make_evaluation(by_event, [action("medium", "Brief the shift lead")])
        summaries = [
            event_summary("TEST-EVENT-1", "Example narrative of three publications.", 3),
            event_summary("TEST-NOTSO-2", "", 2, error="Example failure"),
        ]
        session = use_session(
            feed_session([by_event, by_notice, by_record], [evaluation], summaries)
        )
        response = await api.get(FEED)
        assert response.status_code == 200
        items = response.json()["items"]
        assert [
            (
                item["notification"]["id"],
                item["event_key"],
                item["event_summary"],
                item["event_publication_count"],
            )
            for item in items
        ] == [
            (str(by_event.id), "TEST-EVENT-1", "Example narrative of three publications.", 3),
            (str(by_notice.id), "TEST-NOTSO-2", None, 2),
            (str(by_record.id), "TEST-UDL-3", None, None),
        ]
        first = items[0]
        assert first["evaluation"]["id"] == str(evaluation.id)
        assert (first["urgency"], first["top_action"]) == ("medium", "Brief the shift lead")
        notice = first["notification"]
        assert (notice["data_mode"], notice["classification_marking"]) == ("TEST", "U")
        assert [item["evaluation"] for item in items[1:]] == [None, None]
        sql, params = sent(session, 1)
        assert sql.endswith(
            "WHERE assistant_evaluation.notification_id IN (__[POSTCOMPILE_notification_id_1])"
        )
        assert set(params["notification_id_1"]) == {by_event.id, by_notice.id, by_record.id}
        sql, params = sent(session, 2)
        assert sql.endswith("WHERE event_summary.event_key IN (__[POSTCOMPILE_event_key_1])")
        assert set(params["event_key_1"]) == {"TEST-EVENT-1", "TEST-NOTSO-2", "TEST-UDL-3"}

    @pytest.mark.parametrize("newest_first", [True, False])
    async def test_only_the_latest_evaluation_of_a_notification_is_shown(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        newest_first: bool,
    ) -> None:
        analyst(sign_in)
        notification = make_notification()
        older = make_evaluation(notification, [action("high")], evaluated_at=hours_ago(1))
        newer = make_evaluation(notification, [action("low", "Log it")])
        rows = [newer, older] if newest_first else [older, newer]
        use_session(feed_session([notification], rows))
        [item] = (await api.get(FEED)).json()["items"]
        assert item["evaluation"]["id"] == str(newer.id)
        assert (item["urgency"], item["top_action"]) == ("low", "Log it")

    async def test_items_are_ordered_by_urgency_then_by_recency(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        analyst(sign_in)
        nothing_to_do = make_notification(udl_created_at=NOW)
        unevaluated = make_notification(udl_created_at=hours_ago(1))
        medium = make_notification(udl_created_at=hours_ago(2))
        newer_high = make_notification(udl_created_at=hours_ago(3))
        older_high = make_notification(udl_created_at=hours_ago(4))
        failed = make_notification(udl_created_at=hours_ago(5))
        evaluations = [
            make_evaluation(nothing_to_do, []),
            make_evaluation(medium, [action("medium")]),
            make_evaluation(newer_high, [action("high")]),
            make_evaluation(older_high, [action("low"), action("high")]),
            make_evaluation(failed, [], error="Model response contained no JSON object"),
        ]
        # The database returns the window newest first.
        window = [nothing_to_do, unevaluated, medium, newer_high, older_high, failed]
        use_session(feed_session(window, evaluations))
        items = (await api.get(FEED)).json()["items"]
        assert [(item["notification"]["id"], item["urgency"]) for item in items] == [
            (str(newer_high.id), "high"),
            (str(older_high.id), "high"),
            (str(medium.id), "medium"),
            (str(nothing_to_do.id), "none"),
            (str(unevaluated.id), "pending"),
            (str(failed.id), "pending"),
        ]

    @pytest.mark.parametrize(
        ("next_actions", "urgency", "top_action"),
        [
            pytest.param(None, "none", None, id="no-next-actions-field"),
            pytest.param([], "none", None, id="no-next-actions"),
            pytest.param(
                [
                    action("low", "Log it"),
                    action("high", "Call the owner"),
                    action("medium", "Brief"),
                ],
                "high",
                "Call the owner",
                id="most-urgent-wins",
            ),
            pytest.param(
                [action("medium", "Brief"), action("medium", "Log it")],
                "medium",
                "Brief",
                id="first-of-equals-wins",
            ),
            pytest.param(
                [action("HIGH", "Call the owner")], "high", "Call the owner", id="any-case"
            ),
            pytest.param(
                [{"action": "Log it", "rationale": "Routine."}],
                "low",
                "Log it",
                id="missing-urgency-counts-as-low",
            ),
            pytest.param(
                ["Call the owner", action("low", "Log it")],
                "low",
                "Log it",
                id="non-object-actions-ignored",
            ),
            pytest.param(["Call the owner"], "none", None, id="only-non-object-actions"),
            pytest.param([action("high", ["not", "text"])], "high", None, id="action-not-text"),
        ],
    )
    async def test_the_urgency_is_that_of_the_most_urgent_next_action(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        next_actions: list[Any] | None,
        urgency: str,
        top_action: str | None,
    ) -> None:
        analyst(sign_in)
        notification = make_notification()
        use_session(feed_session([notification], [make_evaluation(notification, next_actions)]))
        [item] = (await api.get(FEED)).json()["items"]
        assert (item["urgency"], item["top_action"]) == (urgency, top_action)

    @pytest.mark.parametrize(
        "evaluated", [False, True], ids=["never-evaluated", "evaluation-failed"]
    )
    async def test_a_notification_without_a_usable_evaluation_is_pending(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        evaluated: bool,
    ) -> None:
        analyst(sign_in)
        notification = make_notification()
        failure = make_evaluation(notification, [], error="Model response contained no JSON object")
        use_session(feed_session([notification], [failure] if evaluated else []))
        [item] = (await api.get(FEED)).json()["items"]
        assert (item["urgency"], item["top_action"]) == ("pending", None)
        assert (item["evaluation"] is not None) is evaluated
        assert item["assistant_cleared"] is True

    async def test_a_notice_kept_from_the_assistant_says_so(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        analyst(sign_in)
        notification = make_notification(classification_marking="U//TEST-NOT-CLEARED")
        use_session(feed_session([notification], []))
        [item] = (await api.get(FEED)).json()["items"]
        assert (item["urgency"], item["assistant_cleared"]) == ("pending", False)


class TestGetEvaluation:
    async def test_the_latest_evaluation_is_returned(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        analyst(sign_in)
        notification = make_notification()
        row = make_evaluation(notification, [action("high", "Call the owner")])
        session = use_session(FakeSession([scalar_result(row)]))
        response = await api.get(evaluation_url(notification.id))
        assert response.status_code == 200
        body = response.json()
        assert (body["id"], body["notification_id"]) == (str(row.id), str(notification.id))
        assert (body["model"], body["error"]) == (MODEL, None)
        assert body["evaluated_at"] == "2026-06-05T12:00:00Z"
        assert body["structured"]["next_actions"][0]["action"] == "Call the owner"
        _sql, params = sent(session, 0)
        assert params["notification_id_1"] == notification.id

    async def test_a_notification_never_evaluated_is_404(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        analyst(sign_in)
        use_session(FakeSession([scalar_result(None)]))
        response = await api.get(evaluation_url(synthetic_id()))
        assert response.status_code == 404
        assert response.json() == {"detail": NOT_EVALUATED}

    @pytest.mark.parametrize(
        ("method", "path"),
        [("GET", evaluation_url("not-a-uuid")), ("POST", evaluate_url("not-a-uuid"))],
    )
    async def test_a_malformed_notification_id_is_422(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        service: EvaluationService,
        method: str,
        path: str,
    ) -> None:
        analyst(sign_in)
        session = use_session(FakeSession())
        assert (await api.request(method, path)).status_code == 422
        session.execute.assert_not_awaited()
        assert service.asked == []


class TestEvaluate:
    async def test_a_new_evaluation_is_returned_audited_and_committed(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        service: EvaluationService,
        audit: AuditRecorder,
    ) -> None:
        user = analyst(sign_in)
        session = use_session(FakeSession())
        audit_rows_at_commit: list[int] = []
        session.commit.side_effect = lambda: audit_rows_at_commit.append(len(audit.rows))
        notification_id = synthetic_id()
        run = stored_run(notification_id)
        service.outcome = run
        response = await api.post(evaluate_url(notification_id))
        assert response.status_code == 200
        body = response.json()
        assert (body["id"], body["notification_id"]) == (
            str(run.evaluation.id),
            str(notification_id),
        )
        assert (body["summary"], body["error"]) == ("Example summary.", None)
        assert body["evaluated_at"] == "2026-06-05T12:00:00Z"
        assert service.asked == [notification_id]
        assert audit.rows == [
            {
                "action_type": "assistant.evaluate",
                "entity_type": "notification",
                "entity_id": str(notification_id),
                "user_id": user.id,
                "ip_address": "127.0.0.1",
                "detail": {
                    "evaluation_id": str(run.evaluation.id),
                    "model": MODEL,
                    "procedures_used": ["00000000-0000-4000-8000-000000000999"],
                    "had_error": False,
                },
            }
        ]
        # The audit row is written before the commit, so it is committed with the request.
        assert audit_rows_at_commit == [1]

    async def test_a_stored_failure_is_returned_and_audited_as_one(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        service: EvaluationService,
        audit: AuditRecorder,
    ) -> None:
        analyst(sign_in)
        session = use_session(FakeSession())
        notification_id = synthetic_id()
        service.outcome = stored_run(notification_id, error="ANTHROPIC_API_KEY is not configured")
        response = await api.post(evaluate_url(notification_id))
        assert response.status_code == 200
        assert response.json()["error"] == "ANTHROPIC_API_KEY is not configured"
        [row] = audit.rows
        assert row["detail"]["had_error"] is True
        session.commit.assert_awaited_once()

    async def test_an_unknown_notification_is_404_and_nothing_is_audited(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        service: EvaluationService,
        audit: AuditRecorder,
    ) -> None:
        analyst(sign_in)
        session = use_session(FakeSession())
        notification_id = synthetic_id()
        service.outcome = NotificationNotFoundError(str(notification_id))
        response = await api.post(evaluate_url(notification_id))
        assert response.status_code == 404
        assert response.json() == {"detail": "Notification not found"}
        assert service.asked == [notification_id]
        assert audit.rows == []
        session.commit.assert_not_awaited()

    async def test_the_assistant_limit_refuses_a_caller_over_it_but_not_another_user(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        service: EvaluationService,
        audit: AuditRecorder,
    ) -> None:
        user = analyst(sign_in)
        use_session(FakeSession())
        notification_id = synthetic_id()
        service.outcome = stored_run(notification_id)
        for _ in range(ASSISTANT_LIMIT.limit - 1):
            ASSISTANT_LIMIT.record(str(user.id))
        url = evaluate_url(notification_id)
        assert (await api.post(url)).status_code == 200  # the last call the window allows
        refused = await api.post(url)
        assert refused.status_code == 429
        assert int(refused.headers["retry-after"]) >= 1
        assert len(service.asked) == 1
        assert len(audit.rows) == 1
        analyst(sign_in, username="example-analyst-2")
        assert (await api.post(url)).status_code == 200
