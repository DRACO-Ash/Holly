import { describe, expect, it } from "vitest";
import { errorStatus, extractErrorMessage, withJsonErrorBody } from "./errors";

describe("extractErrorMessage", () => {
  it("prefers the server's own detail", () => {
    const err = { response: { status: 502, data: { detail: "UDL returned HTTP 500." } } };
    expect(extractErrorMessage(err, "fallback")).toBe("UDL returned HTTP 500.");
  });

  it("ignores a detail that is not text, such as a validation list", () => {
    const err = Object.assign(new Error("Request failed with status code 422"), {
      response: { status: 422, data: { detail: [{ loc: ["body"], msg: "field required" }] } },
    });
    expect(extractErrorMessage(err, "fallback")).toBe("Request failed with status code 422");
  });

  it("uses the error's message when there is no response", () => {
    expect(extractErrorMessage(new Error("Network Error"), "fallback")).toBe("Network Error");
  });

  it("falls back for anything else", () => {
    expect(extractErrorMessage("boom", "fallback")).toBe("fallback");
    expect(extractErrorMessage(null, "fallback")).toBe("fallback");
  });
});

describe("withJsonErrorBody", () => {
  it("reads the server's detail out of a failed file download", async () => {
    const detail = "The file for this procedure is missing; upload it again.";
    const body = new Blob([JSON.stringify({ detail })], { type: "application/json" });
    const err = Object.assign(new Error("Request failed with status code 404"), {
      response: { status: 404, data: body },
    });
    expect(extractErrorMessage(await withJsonErrorBody(err), "fallback")).toBe(detail);
  });

  it("leaves a body that is not JSON, and an error without a body, as they were", async () => {
    const body = new Blob(["<html>Bad gateway</html>"], { type: "text/html" });
    const err = Object.assign(new Error("Request failed with status code 502"), {
      response: { status: 502, data: body },
    });
    expect(extractErrorMessage(await withJsonErrorBody(err), "fallback")).toBe(
      "Request failed with status code 502",
    );
    const offline = new Error("Network Error");
    expect(await withJsonErrorBody(offline)).toBe(offline);
  });
});

describe("errorStatus", () => {
  it("reads the response status when there is one", () => {
    expect(errorStatus({ response: { status: 403 } })).toBe(403);
    expect(errorStatus(new Error("no response"))).toBeUndefined();
  });
});
