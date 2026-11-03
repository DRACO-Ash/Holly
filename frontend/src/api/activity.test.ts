import { afterEach, describe, expect, it, vi } from "vitest";
import { getActivity } from "./activity";
import { apiClient } from "./client";

afterEach(() => vi.restoreAllMocks());

describe("getActivity", () => {
  it("asks for the default window, or the hours given", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue({ data: { window_hours: 120 } });
    expect(await getActivity()).toEqual({ window_hours: 120 });
    expect(get).toHaveBeenLastCalledWith("/activity", { params: {} });
    await getActivity(48);
    expect(get).toHaveBeenLastCalledWith("/activity", { params: { hours: 48 } });
  });
});
