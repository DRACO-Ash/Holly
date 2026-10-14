import axios, { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY, apiClient, downloadFile } from "./client";

const { saveBlob } = vi.hoisted(() => ({ saveBlob: vi.fn() }));
vi.mock("../utils/download", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../utils/download")>()),
  saveBlob,
}));

interface Reply {
  status: number;
  data?: unknown;
  headers?: Record<string, string>;
}
type Handler = (config: InternalAxiosRequestConfig) => Reply;

// An axios adapter that answers from `handler` and rejects a 4xx or 5xx as axios would.
function adapter(handler: Handler) {
  return async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
    const reply = handler(config);
    const response: AxiosResponse = {
      data: reply.data,
      status: reply.status,
      statusText: "",
      headers: reply.headers ?? {},
      config,
      request: {},
    };
    if (reply.status >= 400) {
      throw new AxiosError(
        `Request failed with status code ${reply.status}`,
        "ERR",
        config,
        {},
        response,
      );
    }
    return response;
  };
}

function memoryStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() {
      return values.size;
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => [...values.keys()][index] ?? null,
    removeItem: (key) => void values.delete(key),
    setItem: (key, value) => void values.set(key, value),
  };
}

const assign = vi.fn();

beforeEach(() => {
  saveBlob.mockReset();
  vi.stubGlobal("localStorage", memoryStorage());
  vi.stubGlobal("window", { location: { pathname: "/notifications", assign } });
  assign.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  apiClient.defaults.adapter = undefined;
  axios.defaults.adapter = undefined;
});

function bearer(config: InternalAxiosRequestConfig): string | undefined {
  return config.headers.get("Authorization")?.toString();
}

describe("the API client", () => {
  it("sends the stored access token with every request", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "acc-1");
    const seen: (string | undefined)[] = [];
    apiClient.defaults.adapter = adapter((config) => {
      seen.push(bearer(config));
      return { status: 200, data: { ok: true } };
    });
    await apiClient.get("/notifications");
    expect(seen).toEqual(["Bearer acc-1"]);
  });

  it("refreshes once on a 401, stores the new pair and retries", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "old-acc");
    localStorage.setItem(REFRESH_TOKEN_KEY, "old-ref");
    const refreshBodies: unknown[] = [];
    axios.defaults.adapter = adapter((config) => {
      refreshBodies.push(JSON.parse(String(config.data)));
      return { status: 200, data: { access_token: "new-acc", refresh_token: "new-ref" } };
    });
    apiClient.defaults.adapter = adapter((config) =>
      bearer(config) === "Bearer new-acc" ? { status: 200, data: "done" } : { status: 401 },
    );

    const results = await Promise.all([apiClient.get("/a"), apiClient.get("/b")]);

    expect(results.map((response) => response.data)).toEqual(["done", "done"]);
    expect(refreshBodies).toEqual([{ refresh_token: "old-ref" }]);
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBe("new-acc");
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe("new-ref");
    expect(assign).not.toHaveBeenCalled();
  });

  it("signs out and returns to the sign-in page when the refresh fails", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "old-acc");
    localStorage.setItem(REFRESH_TOKEN_KEY, "old-ref");
    axios.defaults.adapter = adapter(() => ({ status: 401 }));
    apiClient.defaults.adapter = adapter(() => ({ status: 401 }));

    await expect(apiClient.get("/a")).rejects.toThrow("status code 401");
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull();
    expect(assign).toHaveBeenCalledWith("/login");
  });

  it("signs out without a refresh when no refresh token is held", async () => {
    const refresh = vi.fn();
    axios.defaults.adapter = adapter((config) => {
      refresh(config);
      return { status: 200 };
    });
    apiClient.defaults.adapter = adapter(() => ({ status: 401 }));

    await expect(apiClient.get("/a")).rejects.toThrow("status code 401");
    expect(refresh).not.toHaveBeenCalled();
    expect(assign).toHaveBeenCalledWith("/login");
  });

  it("never tries to refresh a failed sign-in", async () => {
    window.location.pathname = "/login";
    apiClient.defaults.adapter = adapter(() => ({ status: 401 }));
    await expect(apiClient.post("/auth/login", {})).rejects.toThrow("status code 401");
    expect(assign).not.toHaveBeenCalled();
  });

  it("passes any other failure straight to the caller", async () => {
    apiClient.defaults.adapter = adapter(() => ({ status: 502, data: { detail: "UDL down" } }));
    await expect(apiClient.get("/elsets")).rejects.toThrow("status code 502");
    expect(assign).not.toHaveBeenCalled();
  });
});

describe("downloadFile", () => {
  it("fetches with the token and saves under the server's file name", async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "acc-1");
    const seen: { url?: string; params?: unknown; auth?: string; type?: string }[] = [];
    apiClient.defaults.adapter = adapter((config) => {
      seen.push({
        url: config.url,
        params: config.params,
        auth: bearer(config),
        type: config.responseType,
      });
      return {
        status: 200,
        data: "file-bytes",
        headers: { "content-disposition": 'attachment; filename="shift-log-2026-06-05.md"' },
      };
    });

    await downloadFile("/shift-log/export", "fallback.md", { shift_date: "2026-06-05" });

    expect(seen).toEqual([
      {
        url: "/shift-log/export",
        params: { shift_date: "2026-06-05" },
        auth: "Bearer acc-1",
        type: "blob",
      },
    ]);
    expect(saveBlob).toHaveBeenCalledWith("file-bytes", "shift-log-2026-06-05.md");
  });

  it("uses the fallback name when the server gives none", async () => {
    apiClient.defaults.adapter = adapter(() => ({ status: 200, data: "bytes" }));
    await downloadFile("/procedures/1/download", "procedure.pdf");
    expect(saveBlob).toHaveBeenCalledWith("bytes", "procedure.pdf");
  });
});
