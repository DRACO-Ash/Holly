// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getActivity } from "../../api/activity";
import { anOverview } from "../../test/activity";
import { ACTIVITY_REFRESH_MS, useActivity } from "./useActivity";

vi.mock("../../api/activity");

beforeEach(() => {
  vi.mocked(getActivity).mockReset();
});
afterEach(() => vi.useRealTimers());

describe("useActivity", () => {
  it("loads the overview and says when", async () => {
    const overview = anOverview({ window_hours: 48 });
    vi.mocked(getActivity).mockResolvedValue(overview);
    const { result } = renderHook(() => useActivity());
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBe(overview);
    expect(result.current.error).toBeNull();
    expect(result.current.refreshing).toBe(false);
    expect(result.current.loadedAt).not.toBeNull();
  });

  it("reloads every minute and on request", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(getActivity).mockResolvedValue(anOverview());
    const { result } = renderHook(() => useActivity());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(getActivity).toHaveBeenCalledTimes(1);
    await act(async () => {
      vi.advanceTimersByTime(ACTIVITY_REFRESH_MS);
    });
    await waitFor(() => expect(getActivity).toHaveBeenCalledTimes(2));
    act(() => result.current.reload());
    await waitFor(() => expect(getActivity).toHaveBeenCalledTimes(3));
    expect(ACTIVITY_REFRESH_MS).toBe(60_000);
  });

  it("keeps the last overview when a reload fails, and says why", async () => {
    const overview = anOverview();
    vi.mocked(getActivity)
      .mockResolvedValueOnce(overview)
      .mockRejectedValueOnce({ response: { data: { detail: "Database unavailable" } } })
      .mockResolvedValueOnce(anOverview({ window_hours: 24 }));
    const { result } = renderHook(() => useActivity());
    await waitFor(() => expect(result.current.data).toBe(overview));
    act(() => result.current.reload());
    await waitFor(() => expect(result.current.error).toBe("Database unavailable"));
    expect(result.current.data).toBe(overview);
    expect(result.current.refreshing).toBe(false);
    act(() => result.current.reload());
    await waitFor(() => expect(result.current.data?.window_hours).toBe(24));
    expect(result.current.error).toBeNull();
  });

  it("falls back to its own words for a failure with no detail", async () => {
    vi.mocked(getActivity).mockRejectedValue({});
    const { result } = renderHook(() => useActivity());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe("Failed to load the activity overview.");
    expect(result.current.data).toBeNull();
  });

  it("ignores an answer that arrives after it is unmounted, and stops its timer", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let answer: (value: ReturnType<typeof anOverview>) => void = () => undefined;
    let fail: (reason: unknown) => void = () => undefined;
    vi.mocked(getActivity)
      .mockReturnValueOnce(new Promise((resolve) => (answer = resolve)))
      .mockReturnValueOnce(new Promise((_resolve, reject) => (fail = reject)));
    const first = renderHook(() => useActivity());
    first.unmount();
    await act(async () => answer(anOverview()));
    expect(first.result.current.data).toBeNull();
    expect(first.result.current.loading).toBe(true);
    const second = renderHook(() => useActivity());
    second.unmount();
    await act(async () => fail(new Error("late")));
    expect(second.result.current.error).toBeNull();
    expect(vi.getTimerCount()).toBe(0);
  });
});
