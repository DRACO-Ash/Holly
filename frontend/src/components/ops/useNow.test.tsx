// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useNow } from "./useNow";

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(Date.parse("2026-11-02T20:00:00Z"));
});
afterEach(() => vi.useRealTimers());

describe("useNow", () => {
  it("moves on every step, and stops when unmounted", () => {
    const { result, unmount } = renderHook(() => useNow(1000));
    const first = result.current;
    expect(first).toBe(Date.parse("2026-11-02T20:00:00Z"));
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current).toBe(first + 1000);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("steps every 30 seconds by default", () => {
    const { result } = renderHook(() => useNow());
    const first = result.current;
    act(() => {
      vi.advanceTimersByTime(29_999);
    });
    expect(result.current).toBe(first);
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current).toBe(first + 30_000);
  });
});
