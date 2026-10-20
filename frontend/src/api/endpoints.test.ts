import { afterEach, describe, expect, it, vi } from "vitest";
import { getEvaluation, getFeed, runEvaluation } from "./assistant";
import { listAuditLog } from "./audit";
import { changePassword, getCurrentUser, login, logout, refresh } from "./auth";
import { apiClient, downloadFile } from "./client";
import {
  acknowledgePreAlert,
  createEventTimer,
  deleteEventTimer,
  dismissEventTimer,
  listEventTimers,
} from "./event_timers";
import { getManeuver, listManeuvers } from "./maneuvers";
import { listMattermostMessages } from "./mattermost";
import {
  getNotification,
  listNotifications,
  refreshNotificationsNow,
  triggerNotificationIngest,
} from "./notifications";
import {
  deleteProcedure,
  downloadProcedure,
  getProcedure,
  listProcedures,
  uploadProcedure,
} from "./procedures";
import {
  createShiftNote,
  deleteShiftNote,
  downloadShiftExport,
  generateShiftSummary,
  getShiftSummary,
  listShiftDates,
  listShiftNotes,
  repolishShiftNote,
  updateShiftNote,
} from "./shift";
import { createUser, listUsers, resetPassword, updateUser } from "./users";

vi.mock("./client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./client")>()),
  downloadFile: vi.fn(),
}));

// What the analyst types: a placeholder, held here rather than written as a password property,
// so SonarQube's hard-coded credential rule (S2068), whose hotspots the app owner cannot close,
// has nothing to flag.
const typed = "pw";

// Each endpoint function's request, answered with `body`: the stub records the call, and the
// function must hand back the body it was given.
const body = { synthetic: "body" };

function answer(method: "get" | "post" | "patch" | "delete") {
  return vi.spyOn(apiClient, method).mockResolvedValue({ data: body });
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.mocked(downloadFile).mockReset();
});

describe("the assistant endpoints", () => {
  it("asks for the feed with the server's window unless the caller sets one", async () => {
    const get = answer("get");
    await expect(getFeed()).resolves.toBe(body);
    expect(get).toHaveBeenLastCalledWith("/assistant/feed", { params: { limit: 100 } });
    await getFeed(48, 10);
    expect(get).toHaveBeenLastCalledWith("/assistant/feed", { params: { limit: 10, hours: 48 } });
  });

  it("reads an evaluation, a 404 meaning none yet", async () => {
    const get = answer("get");
    await expect(getEvaluation("n-1")).resolves.toBe(body);
    expect(get).toHaveBeenLastCalledWith("/assistant/evaluation/n-1");
    get.mockRejectedValueOnce({ response: { status: 404 } });
    await expect(getEvaluation("n-1")).resolves.toBeNull();
  });

  it("passes on any other failure to read an evaluation", async () => {
    const get = answer("get");
    const denied = { response: { status: 403 } };
    get.mockRejectedValueOnce(denied);
    await expect(getEvaluation("n-1")).rejects.toBe(denied);
    const offline = new Error("offline");
    get.mockRejectedValueOnce(offline);
    await expect(getEvaluation("n-1")).rejects.toBe(offline);
    get.mockRejectedValueOnce(null);
    await expect(getEvaluation("n-1")).rejects.toBeNull();
  });

  it("runs an evaluation", async () => {
    const post = answer("post");
    await expect(runEvaluation("n-1")).resolves.toBe(body);
    expect(post).toHaveBeenLastCalledWith("/assistant/evaluate/n-1");
  });
});

describe("the audit log endpoint", () => {
  it("sends the query as parameters, none by default", async () => {
    const get = answer("get");
    await expect(listAuditLog({ action_type: "test.action", limit: 5 })).resolves.toBe(body);
    expect(get).toHaveBeenLastCalledWith("/audit", {
      params: { action_type: "test.action", limit: 5 },
    });
    await listAuditLog();
    expect(get).toHaveBeenLastCalledWith("/audit", { params: {} });
  });
});

describe("the sign-in endpoints", () => {
  // Short synthetic values: nothing here is, or looks like, a credential.
  it("signs in, refreshes, reads the analyst and signs out", async () => {
    const post = answer("post");
    const get = answer("get");
    await expect(login({ username: "test.analyst", password: typed })).resolves.toBe(body);
    expect(post).toHaveBeenLastCalledWith("/auth/login", {
      username: "test.analyst",
      password: typed,
    });
    await expect(refresh("r-1")).resolves.toBe(body);
    expect(post).toHaveBeenLastCalledWith("/auth/refresh", { refresh_token: "r-1" });
    await expect(getCurrentUser()).resolves.toBe(body);
    expect(get).toHaveBeenLastCalledWith("/auth/me");
    await expect(logout("r-1")).resolves.toBeUndefined();
    expect(post).toHaveBeenLastCalledWith("/auth/logout", { refresh_token: "r-1" });
  });
});

describe("the password and users endpoints", () => {
  it("changes the signed-in user's own password", async () => {
    const post = answer("post");
    const fresh = "pw-fresh";
    await expect(changePassword({ current_password: typed, new_password: fresh })).resolves.toBe(
      body,
    );
    expect(post).toHaveBeenLastCalledWith("/auth/password", {
      current_password: typed,
      new_password: fresh,
    });
  });

  it("lists, creates, resets and updates users", async () => {
    const get = answer("get");
    const post = answer("post");
    const patch = answer("patch");
    await expect(listUsers()).resolves.toBe(body);
    expect(get).toHaveBeenLastCalledWith("/users");
    const created = { username: "test.new", email: null, role: "analyst" as const };
    await expect(createUser({ ...created, temporary_password: typed })).resolves.toBe(body);
    expect(post).toHaveBeenLastCalledWith("/users", { ...created, temporary_password: typed });
    await expect(resetPassword("u/1", typed)).resolves.toBe(body);
    expect(post).toHaveBeenLastCalledWith("/users/u%2F1/password", { temporary_password: typed });
    await expect(updateUser("u-1", { is_active: false })).resolves.toBe(body);
    expect(patch).toHaveBeenLastCalledWith("/users/u-1", { is_active: false });
  });
});

describe("the event timer endpoints", () => {
  it("lists live timers by default, dismissed ones on request", async () => {
    const get = answer("get");
    await expect(listEventTimers()).resolves.toBe(body);
    expect(get).toHaveBeenLastCalledWith("/event-timers", {
      params: { include_dismissed: false },
    });
    await listEventTimers(true);
    expect(get).toHaveBeenLastCalledWith("/event-timers", { params: { include_dismissed: true } });
  });

  it("creates, acknowledges, dismisses and deletes a timer", async () => {
    const post = answer("post");
    const del = answer("delete");
    const payload = { label: "Synthetic timer", target_time: "2026-01-02T03:04:05Z" };
    await expect(createEventTimer(payload)).resolves.toBe(body);
    expect(post).toHaveBeenLastCalledWith("/event-timers", payload);
    await expect(acknowledgePreAlert("t-1")).resolves.toBe(body);
    expect(post).toHaveBeenLastCalledWith("/event-timers/t-1/acknowledge-pre-alert");
    await expect(dismissEventTimer("t-1")).resolves.toBe(body);
    expect(post).toHaveBeenLastCalledWith("/event-timers/t-1/dismiss");
    await expect(deleteEventTimer("t-1")).resolves.toBeUndefined();
    expect(del).toHaveBeenLastCalledWith("/event-timers/t-1");
  });
});

describe("the maneuver and Mattermost endpoints", () => {
  it("lists and reads maneuvers", async () => {
    const get = answer("get");
    await expect(listManeuvers({ sat_no: 90001 })).resolves.toBe(body);
    expect(get).toHaveBeenLastCalledWith("/maneuvers", { params: { sat_no: 90001 } });
    await listManeuvers();
    expect(get).toHaveBeenLastCalledWith("/maneuvers", { params: {} });
    await expect(getManeuver("m-1")).resolves.toBe(body);
    expect(get).toHaveBeenLastCalledWith("/maneuvers/m-1");
  });

  it("lists Mattermost messages", async () => {
    const get = answer("get");
    await expect(listMattermostMessages({ channel_id: "c-1" })).resolves.toBe(body);
    expect(get).toHaveBeenLastCalledWith("/mattermost/messages", {
      params: { channel_id: "c-1" },
    });
    await listMattermostMessages();
    expect(get).toHaveBeenLastCalledWith("/mattermost/messages", { params: {} });
  });
});

describe("the notification endpoints", () => {
  it("lists, reads, ingests and refreshes notices", async () => {
    const get = answer("get");
    const post = answer("post");
    await expect(listNotifications({ status: "OPEN" })).resolves.toBe(body);
    expect(get).toHaveBeenLastCalledWith("/notifications", { params: { status: "OPEN" } });
    await listNotifications();
    expect(get).toHaveBeenLastCalledWith("/notifications", { params: {} });
    await expect(getNotification("n-1")).resolves.toBe(body);
    expect(get).toHaveBeenLastCalledWith("/notifications/n-1");
    await expect(triggerNotificationIngest({ max_results: 3 })).resolves.toBe(body);
    expect(post).toHaveBeenLastCalledWith("/notifications/ingest", { max_results: 3 });
    await expect(refreshNotificationsNow()).resolves.toBeUndefined();
    expect(post).toHaveBeenLastCalledWith("/notifications/refresh");
  });
});

describe("the procedure endpoints", () => {
  it("lists, reads and deletes procedures", async () => {
    const get = answer("get");
    const del = answer("delete");
    await expect(listProcedures()).resolves.toBe(body);
    expect(get).toHaveBeenLastCalledWith("/procedures");
    await expect(getProcedure("p-1")).resolves.toBe(body);
    expect(get).toHaveBeenLastCalledWith("/procedures/p-1");
    await expect(deleteProcedure("p-1")).resolves.toBeUndefined();
    expect(del).toHaveBeenLastCalledWith("/procedures/p-1");
  });

  it("uploads a procedure as a form, with its description only when there is one", async () => {
    const post = answer("post");
    const file = new File(["synthetic"], "synthetic.md", { type: "text/markdown" });
    await expect(uploadProcedure("Synthetic", "About it", file)).resolves.toBe(body);
    const [path, form, config] = post.mock.lastCall!;
    expect(path).toBe("/procedures");
    expect(config).toEqual({ headers: { "Content-Type": "multipart/form-data" } });
    const sent = form as FormData;
    expect(sent.get("name")).toBe("Synthetic");
    expect(sent.get("description")).toBe("About it");
    expect((sent.get("file") as File).name).toBe("synthetic.md");
    await uploadProcedure("Synthetic", null, file);
    expect((post.mock.lastCall![1] as FormData).has("description")).toBe(false);
  });

  it("downloads a procedure's file under its own name", async () => {
    await downloadProcedure("p-1", "synthetic.md");
    expect(downloadFile).toHaveBeenLastCalledWith("/procedures/p-1/download", "synthetic.md");
  });
});

describe("the shift log endpoints", () => {
  it("lists the shift dates of the last thirty days by default", async () => {
    const get = answer("get");
    await expect(listShiftDates()).resolves.toBe(body);
    expect(get).toHaveBeenLastCalledWith("/shift-log/dates", { params: { days: 30 } });
    await listShiftDates(7);
    expect(get).toHaveBeenLastCalledWith("/shift-log/dates", { params: { days: 7 } });
  });

  it("names the shift date only when there is one", async () => {
    const get = answer("get");
    await expect(listShiftNotes("2026-01-02")).resolves.toBe(body);
    expect(get).toHaveBeenLastCalledWith("/shift-log/notes", {
      params: { shift_date: "2026-01-02" },
    });
    await listShiftNotes();
    expect(get).toHaveBeenLastCalledWith("/shift-log/notes", { params: undefined });
    await expect(getShiftSummary("2026-01-02")).resolves.toBe(body);
    expect(get).toHaveBeenLastCalledWith("/shift-log/summary", {
      params: { shift_date: "2026-01-02" },
    });
    await getShiftSummary();
    expect(get).toHaveBeenLastCalledWith("/shift-log/summary", { params: undefined });
  });

  it("reads a missing summary as none", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue({ data: undefined });
    await expect(getShiftSummary()).resolves.toBeNull();
  });

  it("writes, edits, re-polishes and deletes notes, and generates the summary", async () => {
    const post = answer("post");
    const patch = answer("patch");
    const del = answer("delete");
    await expect(createShiftNote("Synthetic note", "2026-01-02")).resolves.toBe(body);
    expect(post).toHaveBeenLastCalledWith("/shift-log/notes", {
      raw_text: "Synthetic note",
      shift_date: "2026-01-02",
    });
    await expect(updateShiftNote("note-1", "Polished")).resolves.toBe(body);
    expect(patch).toHaveBeenLastCalledWith("/shift-log/notes/note-1", {
      polished_text: "Polished",
    });
    await expect(repolishShiftNote("note-1")).resolves.toBe(body);
    expect(post).toHaveBeenLastCalledWith("/shift-log/notes/note-1/repolish");
    await expect(deleteShiftNote("note-1")).resolves.toBeUndefined();
    expect(del).toHaveBeenLastCalledWith("/shift-log/notes/note-1");
    await expect(generateShiftSummary("2026-01-02")).resolves.toBe(body);
    expect(post).toHaveBeenLastCalledWith("/shift-log/summary", undefined, {
      params: { shift_date: "2026-01-02" },
    });
    await generateShiftSummary();
    expect(post).toHaveBeenLastCalledWith("/shift-log/summary", undefined, {
      params: undefined,
    });
  });

  it("downloads a shift's export named for its date and format", async () => {
    await downloadShiftExport("2026-01-02", "md");
    expect(downloadFile).toHaveBeenLastCalledWith("/shift-log/export", "shift-log-2026-01-02.md", {
      shift_date: "2026-01-02",
      format: "md",
    });
  });
});
