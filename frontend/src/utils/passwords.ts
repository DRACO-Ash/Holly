// Holly's rule for a password it sets: 12 to 1024 characters, not spaces alone. The server holds
// the rule (app/schemas/auth.py); checking here first saves a round trip and says why in plain
// words. Both sides count as Python does, so they agree at the edges: a character is a code
// point, not a UTF-16 unit, and a space is any character Python's str.isspace() counts.
// tests/test_password_rule.py holds the numbers and the spaces equal to the server's.
export const MIN_PASSWORD_LENGTH = 12;
export const MAX_PASSWORD_LENGTH = 1024;
const PYTHON_SPACES =
  "\u0009\u000a\u000b\u000c\u000d\u001c\u001d\u001e\u001f\u0020\u0085\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000";

// Why a password Holly would set will not do, or null when it will.
export function passwordProblem(password: string): string | null {
  const characters = [...password];
  if (characters.length < MIN_PASSWORD_LENGTH) {
    return `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
  }
  if (characters.length > MAX_PASSWORD_LENGTH) {
    return `Use at most ${MAX_PASSWORD_LENGTH} characters.`;
  }
  if (characters.every((c) => PYTHON_SPACES.includes(c))) {
    return "A password of spaces alone will not do.";
  }
  return null;
}

// Why a user's new password will not do, before it is sent; null when it will.
export function newPasswordProblem(
  current: string,
  next: string,
  confirmation: string,
): string | null {
  const problem = passwordProblem(next);
  if (problem) return problem;
  if (next !== confirmation) return "The new passwords do not match.";
  if (next === current) return "Choose a new password, not the current one.";
  return null;
}
