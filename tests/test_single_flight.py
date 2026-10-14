"""Single-flight jobs (core/single_flight.py): callers asking for a key that is already running
share that one run, its result and its failure; a cancelled leader takes its joiners with it;
and a run leaves nothing behind once it ends, so the next call for the key starts afresh."""

import asyncio
import gc

import pytest

from app.core.single_flight import SingleFlight


class GatedJob:
    """A job that counts its runs and waits at a gate, so other callers can arrive mid-run.
    Each run answers with its own result, or raises `error` when one is set."""

    def __init__(self) -> None:
        self.runs = 0
        self.started = asyncio.Event()
        self.gate = asyncio.Event()
        self.error: Exception | None = None

    async def __call__(self) -> str:
        self.runs += 1
        run = self.runs
        self.started.set()
        await self.gate.wait()
        if self.error is not None:
            raise self.error
        return f"result of run {run}"


async def settle() -> None:
    """Let every task that is ready take its next step."""
    await asyncio.sleep(0)


async def outcomes(*tasks: asyncio.Task[str]) -> list[str | BaseException]:
    """Each task's result or exception; a task that never ends fails the test, not hangs it."""
    async with asyncio.timeout(1):
        return await asyncio.gather(*tasks, return_exceptions=True)


async def start_with_joiners(
    flight: SingleFlight[str], job: GatedJob, joiners: int
) -> tuple[asyncio.Task[str], list[asyncio.Task[str]]]:
    """Start a leader, wait until its job is running, then send `joiners` more callers in."""
    leader = asyncio.create_task(flight.run("refresh", job))
    await job.started.wait()
    joining = [asyncio.create_task(flight.run("refresh", job)) for _ in range(joiners)]
    await settle()
    # The premise: the later callers are waiting on the leader's run, not running their own.
    assert job.runs == 1
    assert not any(task.done() for task in [leader, *joining])
    return leader, joining


class TestSharedRuns:
    async def test_concurrent_callers_share_one_run_and_its_result(self) -> None:
        flight: SingleFlight[str] = SingleFlight()
        job = GatedJob()
        leader, joiners = await start_with_joiners(flight, job, joiners=3)
        job.gate.set()
        assert await outcomes(leader, *joiners) == ["result of run 1"] * 4
        assert job.runs == 1

    async def test_a_failure_reaches_every_caller_and_the_next_call_runs_again(self) -> None:
        flight: SingleFlight[str] = SingleFlight()
        job = GatedJob()
        error = RuntimeError("upstream unavailable")
        job.error = error
        leader, joiners = await start_with_joiners(flight, job, joiners=2)
        job.gate.set()
        results = await outcomes(leader, *joiners)
        assert all(result is error for result in results)
        # No stale entry is left behind: the next call runs the job again.
        job.error = None
        assert await flight.run("refresh", job) == "result of run 2"

    async def test_cancelling_the_leader_cancels_every_joiner_and_the_next_call_runs_again(
        self,
    ) -> None:
        flight: SingleFlight[str] = SingleFlight()
        job = GatedJob()
        leader, joiners = await start_with_joiners(flight, job, joiners=2)
        leader.cancel()
        results = await outcomes(leader, *joiners)
        assert all(isinstance(result, asyncio.CancelledError) for result in results)
        assert all(task.cancelled() for task in [leader, *joiners])
        job.gate.set()
        assert await flight.run("refresh", job) == "result of run 2"

    async def test_cancelling_a_joiner_leaves_the_run_and_the_other_callers_alone(self) -> None:
        flight: SingleFlight[str] = SingleFlight()
        job = GatedJob()
        leader, (impatient, patient) = await start_with_joiners(flight, job, joiners=2)
        impatient.cancel()
        await settle()
        job.gate.set()
        results = await outcomes(leader, impatient, patient)
        assert impatient.cancelled()
        assert [results[0], results[2]] == ["result of run 1", "result of run 1"]
        assert job.runs == 1


class TestSeparateRuns:
    async def test_different_keys_run_independently(self) -> None:
        flight: SingleFlight[str] = SingleFlight()
        notifications, maneuvers = GatedJob(), GatedJob()
        first = asyncio.create_task(flight.run("notifications", notifications))
        second = asyncio.create_task(flight.run("maneuvers", maneuvers))
        async with asyncio.timeout(1):
            await notifications.started.wait()
            await maneuvers.started.wait()
        maneuvers.gate.set()
        # The second key finishes while the first is still running: neither waits on the other.
        assert await outcomes(second) == ["result of run 1"]
        assert not first.done()
        notifications.gate.set()
        assert await outcomes(first) == ["result of run 1"]
        assert (notifications.runs, maneuvers.runs) == (1, 1)

    async def test_a_call_after_a_run_completes_starts_a_new_run(self) -> None:
        flight: SingleFlight[str] = SingleFlight()
        job = GatedJob()
        job.gate.set()
        assert await flight.run("refresh", job) == "result of run 1"
        assert await flight.run("refresh", job) == "result of run 2"
        assert job.runs == 2

    async def test_a_failed_run_nobody_joined_is_not_reported_as_an_unretrieved_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        flight: SingleFlight[str] = SingleFlight()
        job = GatedJob()
        job.error = RuntimeError("upstream unavailable")
        job.gate.set()
        with pytest.raises(RuntimeError, match="upstream unavailable"):
            await flight.run("refresh", job)
        job.error = None
        # The run's shared future is now garbage; collecting it is when asyncio would report
        # an exception that nobody retrieved.
        gc.collect()
        await settle()
        assert not [record for record in caplog.records if "never retrieved" in record.message]
