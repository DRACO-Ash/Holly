import { describe, expect, it } from "vitest";
import { errorStatus, extractErrorMessage } from "./errors";

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

describe("errorStatus", () => {
  it("reads the response status when there is one", () => {
    expect(errorStatus({ response: { status: 403 } })).toBe(403);
    expect(errorStatus(new Error("no response"))).toBeUndefined();
  });
});
