"""Operator-uploaded procedures: what an upload stores and what it refuses, how a stored file
comes back as a download or a preview, that a delete removes the row before the file, and
that every route needs a signed-in user.

Files land in the per-test store that conftest.py points PROCEDURE_STORAGE_PATH at, the
database is a FakeSession, and the audit chain is replaced with a recorder, so each test reads
exactly what the route asked for. The caps are written as literals on purpose: a test that
read them from the module would move with them and could never see them drift.
"""

import asyncio
import hashlib
import uuid
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import httpx2
import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.sql import ClauseElement

from app.api.v1.routes import procedures
from app.config import get_settings
from app.models.procedure import Procedure
from app.models.user import User
from app.services.procedure_storage import delete_file, prepare_storage, write_file
from fakes import NOW, FakeSession, make_user, rows_result, scalar_result

UseSession = Callable[[FakeSession], FakeSession]
SignIn = Callable[[User], User]

TEN_MIB = 10 * 1024 * 1024  # the shipped upload cap
PREVIEW_BYTES = 64 * 1024  # the shipped preview cap
STEPS = b"Step 1: confirm the feed is live.\n"
DUPLICATE = IntegrityError("INSERT INTO procedure", {}, Exception("uq_procedure_file_hash"))
# SQLAlchemy leaves the dialect constructor untyped, so one instance serves the whole file.
POSTGRESQL = postgresql.dialect()  # type: ignore[no-untyped-call]


@pytest.fixture(autouse=True)
def audit_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def record(_db: object, **kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr("app.api.v1.routes.procedures.write_audit", AsyncMock(side_effect=record))
    return calls


@pytest.fixture
def store(tmp_path: Path) -> Path:
    """The procedure directory conftest.py gives this test."""
    return tmp_path / "procedures"


def stored_files(root: Path) -> list[Path]:
    """Every file anywhere under `root`, sorted; empty when nothing was ever written."""
    return sorted(path for path in root.rglob("*") if path.is_file()) if root.exists() else []


def sql(statement: ClauseElement) -> str:
    compiled = statement.compile(dialect=POSTGRESQL, compile_kwargs={"literal_binds": True})
    return " ".join(str(compiled).split())


def make_procedure(**overrides: Any) -> Procedure:
    """A procedure row as the database would return it."""
    fields: dict[str, Any] = {
        "id": uuid.uuid4(),
        "name": "Handover checklist",
        "description": None,
        "filename": "handover.txt",
        "content_type": "text/plain",
        "size_bytes": 0,
        "file_hash": "0" * 64,
        "uploaded_by": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    return Procedure(**(fields | overrides))


def stored_procedure(data: bytes, **overrides: Any) -> Procedure:
    """A procedure row whose file is already in the store, as a completed upload leaves it."""
    procedure = make_procedure(
        size_bytes=len(data), file_hash=hashlib.sha256(data).hexdigest(), **overrides
    )
    write_file(procedure.id, procedure.filename, data)
    return procedure


def database_defaults(session: FakeSession) -> FakeSession:
    """Have flush and refresh do what PostgreSQL does for a new procedure row: the INSERT
    fills the id default when the row has none, a second copy of the same bytes breaks the
    unique constraint on file_hash, and refresh reads back the server-side timestamps."""
    hashes: set[str] = set()

    def flush() -> None:
        procedure = session.added[-1]
        if procedure.file_hash in hashes:
            raise DUPLICATE
        hashes.add(procedure.file_hash)
        if procedure.id is None:
            procedure.id = uuid.uuid4()

    def refresh(procedure: Procedure) -> None:
        procedure.created_at = procedure.updated_at = NOW

    session.flush.side_effect = flush
    session.refresh.side_effect = refresh
    return session


async def upload(
    api: httpx2.AsyncClient,
    data: bytes = STEPS,
    *,
    filename: str = "handover.txt",
    content_type: str = "text/plain",
    form: dict[str, str] | None = None,
) -> httpx2.Response:
    return await api.post(
        "/api/v1/procedures",
        data={"name": "Handover checklist"} if form is None else form,
        files={"file": (filename, data, content_type)},
    )


def bare_upload(data: bytes) -> tuple[bytes, dict[str, str]]:
    """A multipart body whose file part names no file and declares no type: a browser never
    sends one, but any script can."""
    boundary = "holly-test-boundary"
    head = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="name"\r\n\r\n'
        "Handover checklist\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename=""\r\n\r\n'
    )
    body = head.encode() + data + f"\r\n--{boundary}--\r\n".encode()
    return body, {"Content-Type": f"multipart/form-data; boundary={boundary}"}


class TestUpload:
    async def test_an_upload_is_stored_indexed_and_audited(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        audit_calls: list[dict[str, Any]],
        store: Path,
    ) -> None:
        user = sign_in(make_user())
        session = use_session(database_defaults(FakeSession()))
        response = await upload(
            api, form={"name": "  Handover checklist ", "description": " Read first. "}
        )
        assert response.status_code == 201
        [procedure] = session.added
        assert response.json() == {
            "id": str(procedure.id),
            "name": "Handover checklist",
            "description": "Read first.",
            "filename": "handover.txt",
            "content_type": "text/plain",
            "size_bytes": len(STEPS),
            "file_hash": hashlib.sha256(STEPS).hexdigest(),
            "uploaded_by": str(user.id),
            "created_at": "2026-06-05T12:00:00Z",
            "updated_at": "2026-06-05T12:00:00Z",
        }
        assert [path.read_bytes() for path in stored_files(store)] == [STEPS]
        assert audit_calls == [
            {
                "action_type": "procedure.upload",
                "entity_type": "procedure",
                "entity_id": str(procedure.id),
                "user_id": user.id,
                "ip_address": "127.0.0.1",
                "detail": {
                    "name": "Handover checklist",
                    "filename": "handover.txt",
                    "size_bytes": len(STEPS),
                },
            }
        ]
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once_with(procedure)

    async def test_an_upload_of_exactly_10_mib_is_accepted(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn, store: Path
    ) -> None:
        sign_in(make_user())
        use_session(database_defaults(FakeSession()))
        response = await upload(api, b"a" * TEN_MIB)
        assert response.status_code == 201
        assert response.json()["size_bytes"] == TEN_MIB
        assert response.json()["description"] is None
        assert [path.stat().st_size for path in stored_files(store)] == [TEN_MIB]

    async def test_an_upload_over_10_mib_is_refused_with_413_and_never_stored(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        audit_calls: list[dict[str, Any]],
        store: Path,
    ) -> None:
        sign_in(make_user())
        session = use_session(FakeSession())
        response = await upload(api, b"a" * (TEN_MIB + 1))
        assert response.status_code == 413
        assert response.json() == {"detail": "File exceeds 10MB limit"}
        assert stored_files(store) == []
        assert session.added == []
        assert audit_calls == []

    async def test_an_anonymous_upload_is_refused_before_its_body_is_read(
        self, api: httpx2.AsyncClient, store: Path
    ) -> None:
        pulled = 0

        async def ten_mib() -> AsyncIterator[bytes]:
            nonlocal pulled
            for _ in range(10):
                await asyncio.sleep(0)  # a network body arrives a chunk at a time
                pulled += 1
                yield b"x" * (1024 * 1024)

        response = await api.post(
            "/api/v1/procedures",
            content=ten_mib(),
            headers={"content-type": "multipart/form-data; boundary=example"},
        )
        assert response.status_code == 401
        assert pulled <= 1, f"{pulled} MiB of an anonymous upload were read"
        assert stored_files(store) == []

    async def test_a_write_that_fails_part_way_leaves_no_file(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        store: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sign_in(make_user())
        session = use_session(FakeSession())

        def disk_full(procedure_id: uuid.UUID, filename: str, data: bytes) -> None:
            write_file(procedure_id, filename, data[:3])
            msg = "No space left on device"
            raise OSError(msg)

        monkeypatch.setattr(procedures, "write_file", disk_full)
        with pytest.raises(OSError, match="No space left on device"):
            await upload(api)
        assert stored_files(store) == []
        assert session.added == []

    async def test_an_empty_file_is_refused_with_400(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn, store: Path
    ) -> None:
        sign_in(make_user())
        session = use_session(FakeSession())
        response = await upload(api, b"")
        assert response.status_code == 400
        assert response.json() == {"detail": "Uploaded file is empty"}
        assert stored_files(store) == []
        assert session.added == []

    @pytest.mark.parametrize(
        ("form", "files"),
        [
            ({}, {"file": ("handover.txt", STEPS, "text/plain")}),
            ({"name": ""}, {"file": ("handover.txt", STEPS, "text/plain")}),
            ({"name": "n" * 201}, {"file": ("handover.txt", STEPS, "text/plain")}),
            (
                {"name": "Handover checklist", "description": "d" * 4001},
                {"file": ("handover.txt", STEPS, "text/plain")},
            ),
            ({"name": "Handover checklist"}, None),
        ],
        ids=["no-name", "empty-name", "name-201", "description-4001", "no-file"],
    )
    async def test_a_malformed_form_is_422_and_never_stored(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        store: Path,
        form: dict[str, str],
        files: dict[str, tuple[str, bytes, str]] | None,
    ) -> None:
        sign_in(make_user())
        session = use_session(FakeSession())
        response = await api.post("/api/v1/procedures", data=form, files=files)
        assert response.status_code == 422
        assert stored_files(store) == []
        assert session.added == []

    async def test_the_longest_allowed_name_and_description_are_accepted(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        use_session(database_defaults(FakeSession()))
        response = await upload(api, form={"name": "n" * 200, "description": "d" * 4000})
        assert response.status_code == 201
        assert len(response.json()["name"]) == 200
        assert len(response.json()["description"]) == 4000

    async def test_an_over_long_file_name_and_type_are_cut_to_their_columns(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        use_session(database_defaults(FakeSession()))
        filename = "f" * 296 + ".txt"
        content_type = "text/plain; profile=" + "p" * 130
        response = await upload(api, filename=filename, content_type=content_type)
        assert response.status_code == 201
        assert response.json()["filename"] == filename[:255]
        assert response.json()["content_type"] == content_type[:100]

    async def test_a_file_part_without_a_name_or_type_gets_safe_defaults(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        use_session(database_defaults(FakeSession()))
        body, headers = bare_upload(STEPS)
        response = await api.post("/api/v1/procedures", content=body, headers=headers)
        assert response.status_code == 201
        assert response.json()["filename"] == "procedure"
        assert response.json()["content_type"] == "application/octet-stream"

    @pytest.mark.parametrize(
        ("filename", "suffix"), [("../../etc/passwd", ""), ("x.php;.txt", ".txt")]
    )
    async def test_a_hostile_file_name_never_reaches_the_filesystem(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        tmp_path: Path,
        store: Path,
        filename: str,
        suffix: str,
    ) -> None:
        sign_in(make_user())
        use_session(database_defaults(FakeSession()))
        response = await upload(api, filename=filename)
        assert response.status_code == 201
        # Searched from tmp_path, the store's parent, so a file that escaped is found too.
        [stored] = stored_files(tmp_path)
        assert stored.parent == store
        assert stored.suffix == suffix
        for fragment in ("..", "/", "etc", "passwd", "php", ";"):
            assert fragment not in stored.name

    async def test_the_stored_file_is_named_by_the_procedure_id(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn, store: Path
    ) -> None:
        sign_in(make_user())
        use_session(database_defaults(FakeSession()))
        response = await upload(api, filename="x.php;.txt")
        assert [path.name for path in stored_files(store)] == [f"{response.json()['id']}.txt"]

    async def test_a_duplicate_is_refused_with_409_and_its_file_removed(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        audit_calls: list[dict[str, Any]],
        store: Path,
    ) -> None:
        sign_in(make_user())
        session = use_session(FakeSession())
        session.flush.side_effect = DUPLICATE
        response = await upload(api)
        assert response.status_code == 409
        assert response.json() == {"detail": "A procedure with identical content already exists"}
        session.rollback.assert_awaited_once()
        session.commit.assert_not_awaited()
        assert stored_files(store) == []
        assert audit_calls == []

    async def test_a_refused_duplicate_leaves_the_original_file_in_place(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn, store: Path
    ) -> None:
        sign_in(make_user())
        use_session(database_defaults(FakeSession()))
        first = await upload(api, filename="handover.txt")
        second = await upload(api, filename="handover-copy.txt")
        assert (first.status_code, second.status_code) == (201, 409)
        assert [(path.name, path.read_bytes()) for path in stored_files(store)] == [
            (f"{first.json()['id']}.txt", STEPS)
        ]


class TestUploadHygiene:
    @pytest.mark.parametrize("name", ["   ", "\t\n"])
    async def test_a_blank_name_is_refused_and_nothing_is_stored(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        store: Path,
        name: str,
    ) -> None:
        sign_in(make_user())
        session = use_session(database_defaults(FakeSession()))
        response = await upload(api, form={"name": name})
        assert response.status_code == 422
        assert session.added == []
        assert stored_files(store) == []

    async def test_a_blank_description_is_stored_as_none(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        session = use_session(database_defaults(FakeSession()))
        response = await upload(api, form={"name": "Handover checklist", "description": "  "})
        assert response.status_code == 201
        assert session.added[0].description is None

    async def test_any_failure_after_the_file_is_written_removes_it(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        store: Path,
        audit_calls: list[dict[str, Any]],
    ) -> None:
        sign_in(make_user())
        session = use_session(database_defaults(FakeSession()))
        session.commit.side_effect = OperationalError("COMMIT", {}, Exception("connection lost"))
        with pytest.raises(OperationalError):
            await upload(api)
        assert stored_files(store) == []
        assert len(audit_calls) == 1


class TestStorage:
    @pytest.mark.parametrize(
        ("filename", "suffix"),
        [
            ("SOP.pdf", ".pdf"),
            ("archive.tar.gz", ".gz"),
            ("x.php;.txt", ".txt"),
            ("../../etc/passwd", ""),
            ("..\\..\\boot.ini", ".ini"),
            (".bashrc", ""),
            ("notes.t xt", ""),
            ("report.txt;rm -rf", ""),
            ("evil.sh\n", ""),
            ("x.\u0442\u0445\u0442", ""),
            ("x." + "e" * 16, "." + "e" * 16),
            ("x." + "e" * 17, ""),
        ],
    )
    def test_a_file_is_stored_as_its_id_and_a_plain_extension_only(
        self, store: Path, filename: str, suffix: str
    ) -> None:
        procedure_id = uuid.uuid4()
        stored = write_file(procedure_id, filename, STEPS)
        assert stored.path == store / f"{procedure_id}{suffix}"
        assert stored_files(store) == [stored.path]

    def test_a_stored_file_reports_its_size_and_hash(self) -> None:
        stored = write_file(uuid.uuid4(), "handover.txt", STEPS)
        assert stored.size_bytes == len(STEPS)
        assert stored.file_hash == hashlib.sha256(STEPS).hexdigest()
        assert stored.path.read_bytes() == STEPS

    def test_deleting_a_file_that_is_already_gone_is_not_an_error(self, store: Path) -> None:
        procedure_id = uuid.uuid4()
        write_file(procedure_id, "handover.txt", STEPS)
        delete_file(procedure_id, "handover.txt")
        delete_file(procedure_id, "handover.txt")
        assert stored_files(store) == []

    def test_boot_creates_the_store_and_leaves_no_probe_behind(self, store: Path) -> None:
        assert not store.exists()
        assert prepare_storage(get_settings()) == store
        assert store.is_dir()
        assert list(store.iterdir()) == []

    def test_boot_fails_on_a_store_that_takes_a_directory_but_not_a_file(
        self, monkeypatch: pytest.MonkeyPatch, store: Path
    ) -> None:
        # The probe file's name is pinned and a directory put in its place, so creating the
        # store succeeds and only the probe write itself can fail: the case of a mount that
        # exists but refuses writes, which a root-run test cannot build from permissions.
        fixed = uuid.UUID(int=7)
        monkeypatch.setattr(uuid, "uuid4", lambda: fixed)
        probe = store / f".write-check-{fixed.hex}"
        probe.mkdir(parents=True)
        with pytest.raises(IsADirectoryError):
            prepare_storage(get_settings())
        assert probe.is_dir()


class TestReading:
    async def test_the_list_is_newest_first_with_a_total(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        rows = [make_procedure(name="Newer"), make_procedure(name="Older")]
        session = use_session(FakeSession([rows_result(rows), scalar_result(7)]))
        response = await api.get("/api/v1/procedures")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 7
        assert [item["name"] for item in body["items"]] == ["Newer", "Older"]
        assert [item["id"] for item in body["items"]] == [str(row.id) for row in rows]
        listed, counted = (call.args[0] for call in session.execute.await_args_list)
        assert sql(listed).endswith("FROM procedure ORDER BY procedure.created_at DESC")
        assert sql(counted) == "SELECT count(*) AS count_1 FROM procedure"

    @pytest.mark.parametrize(
        "content_type", ["text/plain", "text/markdown", "application/json", "text/csv"]
    )
    async def test_a_text_procedure_is_previewed_with_its_metadata(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn, content_type: str
    ) -> None:
        sign_in(make_user())
        procedure = stored_procedure(STEPS, content_type=content_type)
        use_session(FakeSession([scalar_result(procedure)]))
        response = await api.get(f"/api/v1/procedures/{procedure.id}")
        assert response.status_code == 200
        body = response.json()
        assert (body["content"], body["content_truncated"]) == (STEPS.decode(), False)
        assert body["id"] == str(procedure.id)
        assert body["file_hash"] == hashlib.sha256(STEPS).hexdigest()

    @pytest.mark.parametrize(
        "content_type",
        ["application/pdf", "text/html", "image/svg+xml", "application/octet-stream"],
    )
    async def test_any_other_type_is_never_previewed(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn, content_type: str
    ) -> None:
        sign_in(make_user())
        procedure = stored_procedure(b"<script>alert(1)</script>", content_type=content_type)
        use_session(FakeSession([scalar_result(procedure)]))
        body = (await api.get(f"/api/v1/procedures/{procedure.id}")).json()
        assert (body["content"], body["content_truncated"]) == (None, False)
        assert body["content_type"] == content_type

    @pytest.mark.parametrize(
        ("size", "truncated"), [(PREVIEW_BYTES, False), (PREVIEW_BYTES + 1, True), (TEN_MIB, True)]
    )
    async def test_the_preview_stops_at_64_kib(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        size: int,
        truncated: bool,
    ) -> None:
        sign_in(make_user())
        procedure = stored_procedure(b"a" * size, content_type="text/plain")
        use_session(FakeSession([scalar_result(procedure)]))
        body = (await api.get(f"/api/v1/procedures/{procedure.id}")).json()
        assert body["content"] == "a" * PREVIEW_BYTES
        assert body["content_truncated"] is truncated
        assert body["size_bytes"] == size

    async def test_bytes_that_are_not_utf8_are_replaced_in_the_preview(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user())
        procedure = stored_procedure(b"caf\xe9 \xff", content_type="text/plain")
        use_session(FakeSession([scalar_result(procedure)]))
        body = (await api.get(f"/api/v1/procedures/{procedure.id}")).json()
        assert body["content"] == "caf\ufffd \ufffd"

    async def test_a_missing_file_leaves_the_metadata_readable(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn, store: Path
    ) -> None:
        sign_in(make_user())
        procedure = make_procedure(content_type="text/plain")
        use_session(FakeSession([scalar_result(procedure)]))
        response = await api.get(f"/api/v1/procedures/{procedure.id}")
        assert stored_files(store) == []
        assert response.status_code == 200
        assert (response.json()["content"], response.json()["content_truncated"]) == (None, False)
        assert response.json()["name"] == "Handover checklist"

    async def test_a_download_whose_file_is_missing_is_404_not_a_crash(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        sign_in(make_user())
        procedure = make_procedure()
        use_session(FakeSession([scalar_result(procedure)]))
        response = await api.get(f"/api/v1/procedures/{procedure.id}/download")
        assert response.status_code == 404
        assert response.json() == {
            "detail": "The file for this procedure is missing; upload it again."
        }
        assert f"Procedure {procedure.id} has no file in the store" in caplog.text

    @pytest.mark.parametrize(
        ("filename", "disposition"),
        [
            (
                "SOP-7 handover.txt",
                'attachment; filename="SOP-7_handover.txt"; '
                "filename*=UTF-8''SOP-7%20handover.txt",
            ),
            (
                "Prozedur f\u00fcr \u00dcbung.txt",
                'attachment; filename="Prozedur_f_r__bung.txt"; '
                "filename*=UTF-8''Prozedur%20f%C3%BCr%20%C3%9Cbung.txt",
            ),
            (
                "\u624b\u9806\u66f8.pdf",
                'attachment; filename="___.pdf"; '
                "filename*=UTF-8''%E6%89%8B%E9%A0%86%E6%9B%B8.pdf",
            ),
            (
                'x"; filename=evil.html',
                'attachment; filename="x___filename_evil.html"; '
                "filename*=UTF-8''x%22%3B%20filename%3Devil.html",
            ),
            (
                "evil\r\nSet-Cookie: session=1.txt",
                'attachment; filename="evil__Set-Cookie__session_1.txt"; '
                "filename*=UTF-8''evil%0D%0ASet-Cookie%3A%20session%3D1.txt",
            ),
            (
                "../../etc/passwd",
                'attachment; filename=".._.._etc_passwd"; '
                "filename*=UTF-8''..%2F..%2Fetc%2Fpasswd",
            ),
            ("", "attachment; filename=\"procedure\"; filename*=UTF-8''"),
            (
                "a" * 150 + ".pdf",
                f"attachment; filename=\"{'a' * 100}\"; filename*=UTF-8''{'a' * 150}.pdf",
            ),
        ],
        ids=["space", "latin", "cjk", "quote", "crlf", "path", "empty", "long"],
    )
    async def test_a_download_is_an_octet_stream_attachment_named_safely(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        filename: str,
        disposition: str,
    ) -> None:
        sign_in(make_user())
        # Whatever type the uploader claimed, the download never renders as a page.
        procedure = stored_procedure(
            b"<html><script>alert(1)</script></html>", filename=filename, content_type="text/html"
        )
        use_session(FakeSession([scalar_result(procedure)]))
        response = await api.get(f"/api/v1/procedures/{procedure.id}/download")
        assert response.status_code == 200
        assert response.headers["content-disposition"] == disposition
        assert response.headers["content-type"] == "application/octet-stream"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "set-cookie" not in response.headers
        assert response.content == b"<html><script>alert(1)</script></html>"

    @pytest.mark.parametrize(
        ("method", "suffix"), [("GET", ""), ("GET", "/download"), ("DELETE", "")]
    )
    async def test_an_unknown_procedure_is_404(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        audit_calls: list[dict[str, Any]],
        method: str,
        suffix: str,
    ) -> None:
        sign_in(make_user())
        procedure_id = uuid.uuid4()
        session = use_session(FakeSession([scalar_result(None)]))
        response = await api.request(method, f"/api/v1/procedures/{procedure_id}{suffix}")
        assert response.status_code == 404
        assert response.json() == {"detail": "Procedure not found"}
        [lookup] = session.execute.await_args_list
        assert sql(lookup.args[0]).endswith(f"WHERE procedure.id = '{procedure_id}'")
        session.delete.assert_not_awaited()
        assert audit_calls == []


class TestDelete:
    async def test_delete_removes_the_row_then_the_file_and_is_audited(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        audit_calls: list[dict[str, Any]],
        store: Path,
    ) -> None:
        user = sign_in(make_user())
        procedure = stored_procedure(STEPS)
        [path] = stored_files(store)
        session = use_session(FakeSession([scalar_result(procedure)]))
        file_present_at_commit: list[bool] = []
        session.commit.side_effect = lambda: file_present_at_commit.append(path.exists())
        response = await api.delete(f"/api/v1/procedures/{procedure.id}")
        assert response.status_code == 204
        session.delete.assert_awaited_once_with(procedure)
        assert file_present_at_commit == [True]
        assert stored_files(store) == []
        assert audit_calls == [
            {
                "action_type": "procedure.delete",
                "entity_type": "procedure",
                "entity_id": str(procedure.id),
                "user_id": user.id,
                "ip_address": "127.0.0.1",
                "detail": {"name": "Handover checklist", "filename": "handover.txt"},
            }
        ]

    async def test_a_failed_commit_keeps_the_file(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn, store: Path
    ) -> None:
        sign_in(make_user())
        procedure = stored_procedure(STEPS)
        session = use_session(FakeSession([scalar_result(procedure)]))
        session.commit.side_effect = OperationalError("COMMIT", {}, Exception("connection lost"))
        with pytest.raises(OperationalError):
            await api.delete(f"/api/v1/procedures/{procedure.id}")
        assert [path.read_bytes() for path in stored_files(store)] == [STEPS]


class TestSignIn:
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/api/v1/procedures"),
            ("POST", "/api/v1/procedures"),
            ("GET", "/api/v1/procedures/00000000-0000-4000-8000-000000000001"),
            ("GET", "/api/v1/procedures/00000000-0000-4000-8000-000000000001/download"),
            ("DELETE", "/api/v1/procedures/00000000-0000-4000-8000-000000000001"),
        ],
    )
    async def test_every_route_requires_sign_in_and_touches_nothing(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        audit_calls: list[dict[str, Any]],
        store: Path,
        method: str,
        path: str,
    ) -> None:
        session = use_session(FakeSession())
        upload_parts: dict[str, Any] = (
            {"data": {"name": "Handover checklist"}, "files": {"file": ("a.txt", STEPS)}}
            if method == "POST"
            else {}
        )
        response = await api.request(method, path, **upload_parts)
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        session.execute.assert_not_awaited()
        assert stored_files(store) == []
        assert audit_calls == []
