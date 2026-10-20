import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { extractErrorMessage, validationMessage } from "../utils/errors";
import { MIN_PASSWORD_LENGTH, newPasswordProblem } from "../utils/passwords";

export default function ChangePassword() {
  const { user, changePassword } = useAuth();
  const navigate = useNavigate();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [changed, setChanged] = useState(false);
  const due = user?.must_change_password ?? false;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setChanged(false);
    const problem = newPasswordProblem(current, next, confirmation);
    if (problem) {
      setError(problem);
      return;
    }
    setSaving(true);
    try {
      await changePassword(current, next);
      setCurrent("");
      setNext("");
      setConfirmation("");
      if (due) {
        navigate("/");
      } else {
        setChanged(true);
      }
    } catch (err) {
      setError(
        validationMessage(err) ?? extractErrorMessage(err, "The password could not be changed."),
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <h1>Change password</h1>
      <p className="muted-paragraph">
        {due
          ? "An admin set your password. Choose your own to continue."
          : "Changing your password signs you out everywhere else."}
      </p>
      <section className="card">
        <form onSubmit={onSubmit} className="ingest-form">
          <label>
            Current password{" "}
            <input
              type="password"
              autoComplete="current-password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              required
            />
          </label>
          <label>
            New password{" "}
            <input
              type="password"
              autoComplete="new-password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              aria-describedby="password-rule"
              required
            />
          </label>
          <label>
            New password again{" "}
            <input
              type="password"
              autoComplete="new-password"
              value={confirmation}
              onChange={(e) => setConfirmation(e.target.value)}
              required
            />
          </label>
          <button type="submit" disabled={saving}>
            {saving ? "Saving..." : "Change password"}
          </button>
        </form>
        <p id="password-rule" className="muted">
          At least {MIN_PASSWORD_LENGTH} characters, not spaces alone.
        </p>
      </section>
      {error && (
        <div className="form-error" role="alert">
          {error}
        </div>
      )}
      {changed && (
        <output className="status-line">Password changed. Every other session has ended.</output>
      )}
    </div>
  );
}
