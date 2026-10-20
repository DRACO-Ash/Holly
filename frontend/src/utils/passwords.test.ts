import { describe, expect, it } from "vitest";
import {
  MAX_PASSWORD_LENGTH,
  MIN_PASSWORD_LENGTH,
  newPasswordProblem,
  passwordProblem,
} from "./passwords";

// Synthetic values of the lengths the rule turns on; none is, or looks like, a credential.
const twelve = "x".repeat(MIN_PASSWORD_LENGTH);
const eleven = "x".repeat(MIN_PASSWORD_LENGTH - 1);
const other = "y".repeat(MIN_PASSWORD_LENGTH);

describe("the password rule", () => {
  it("takes 12 characters or more that are not spaces alone", () => {
    expect(passwordProblem(twelve)).toBeNull();
    expect(passwordProblem(eleven)).toBe("Use at least 12 characters.");
    expect(passwordProblem(" ".repeat(MIN_PASSWORD_LENGTH))).toBe(
      "A password of spaces alone will not do.",
    );
  });

  it("counts characters as the server does, one to a code point", () => {
    // Each emoji is two UTF-16 units but one character: 6 of them are 6, not 12.
    expect(passwordProblem("\u{1F680}".repeat(6))).toBe("Use at least 12 characters.");
    expect(passwordProblem("\u{1F680}".repeat(MIN_PASSWORD_LENGTH))).toBeNull();
    expect(passwordProblem("x".repeat(MAX_PASSWORD_LENGTH))).toBeNull();
    expect(passwordProblem("x".repeat(MAX_PASSWORD_LENGTH + 1))).toBe(
      "Use at most 1024 characters.",
    );
  });

  it("counts as spaces what the server counts, and nothing more", () => {
    // A no-break space and a file separator are spaces to Python; a zero-width no-break
    // space is not, though JavaScript's trim() removes it.
    for (const space of ["\u00a0", "\u001c", "\u3000", "\t"]) {
      expect(passwordProblem(space.repeat(MIN_PASSWORD_LENGTH))).toBe(
        "A password of spaces alone will not do.",
      );
    }
    expect(passwordProblem("\ufeff".repeat(MIN_PASSWORD_LENGTH))).toBeNull();
  });

  it("wants a new password typed twice alike, and not the current one", () => {
    expect(newPasswordProblem("now", twelve, twelve)).toBeNull();
    expect(newPasswordProblem("now", eleven, eleven)).toBe("Use at least 12 characters.");
    expect(newPasswordProblem("now", twelve, other)).toBe("The new passwords do not match.");
    expect(newPasswordProblem(twelve, twelve, twelve)).toBe(
      "Choose a new password, not the current one.",
    );
  });
});
