import { FormEvent, useEffect, useState } from "react";
import { createUser, listUsers, resetPassword, updateUser } from "../api/users";
import { useAuth } from "../context/AuthContext";
import type { User, UserRole } from "../types";
import { errorStatus, extractErrorMessage, validationMessage } from "../utils/errors";
import { MIN_PASSWORD_LENGTH, passwordProblem } from "../utils/passwords";

const ROLES: ReadonlyArray<UserRole> = ["analyst", "operator", "admin"];

function usersErrorMessage(err: unknown, fallback: string): string {
  if (errorStatus(err) === 403) return "Insufficient privileges. Admin role required.";
  return validationMessage(err) ?? extractErrorMessage(err, fallback);
}

function byUsername(users: User[]): User[] {
  return [...users].sort((a, b) => a.username.localeCompare(b.username));
}

export default function Users() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<UserRole>("analyst");
  const [temporary, setTemporary] = useState("");
  const [creating, setCreating] = useState(false);
  const [resetFor, setResetFor] = useState<string | null>(null);
  const [resetValue, setResetValue] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listUsers()
      .then((list) => {
        if (!cancelled) setUsers(byUsername(list));
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(usersErrorMessage(err, "Failed to load users."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function replace(updated: User) {
    setUsers((list) => list.map((u) => (u.id === updated.id ? updated : u)));
  }

  function begin() {
    setError(null);
    setNotice(null);
  }

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    begin();
    const problem = passwordProblem(temporary);
    if (problem) {
      setError(`Temporary password: ${problem}`);
      return;
    }
    setCreating(true);
    try {
      const created = await createUser({
        username: username.trim(),
        email: email.trim() || null,
        role,
        temporary_password: temporary,
      });
      setUsers((list) => byUsername([...list, created]));
      setUsername("");
      setEmail("");
      setRole("analyst");
      setTemporary("");
      setNotice(
        `Created ${created.username}. Give them the temporary password; they choose their own at first sign-in.`,
      );
    } catch (err) {
      setError(usersErrorMessage(err, "The user could not be created."));
    } finally {
      setCreating(false);
    }
  }

  async function onReset(event: FormEvent, target: User) {
    event.preventDefault();
    begin();
    const problem = passwordProblem(resetValue);
    if (problem) {
      setError(`Temporary password: ${problem}`);
      return;
    }
    setBusyId(target.id);
    try {
      replace(await resetPassword(target.id, resetValue));
      setResetFor(null);
      setResetValue("");
      setNotice(
        `Reset the password of ${target.username}. Their sessions have ended; they choose a new password at next sign-in.`,
      );
    } catch (err) {
      setError(usersErrorMessage(err, "The password could not be reset."));
    } finally {
      setBusyId(null);
    }
  }

  async function onUpdate(target: User, change: { role?: UserRole; is_active?: boolean }) {
    begin();
    setBusyId(target.id);
    try {
      const updated = await updateUser(target.id, change);
      replace(updated);
      if (change.role !== undefined) {
        setNotice(`${updated.username} is now ${updated.role}.`);
      } else {
        setNotice(
          updated.is_active
            ? `Activated ${updated.username}.`
            : `Deactivated ${updated.username}. Their sessions have ended.`,
        );
      }
    } catch (err) {
      setError(usersErrorMessage(err, "The user could not be changed."));
    } finally {
      setBusyId(null);
    }
  }

  function startReset(target: User) {
    begin();
    setResetFor(target.id);
    setResetValue("");
  }

  function actions(u: User) {
    if (u.id === me?.id) {
      return <span className="muted">Your account: change your password from Password.</span>;
    }
    if (resetFor === u.id) {
      return (
        <form onSubmit={(e) => void onReset(e, u)} className="ingest-form">
          <label>
            Temporary password{" "}
            <input
              type="password"
              autoComplete="new-password"
              value={resetValue}
              onChange={(e) => setResetValue(e.target.value)}
              required
            />
          </label>
          <button type="submit" disabled={busyId === u.id}>
            Save
          </button>{" "}
          <button type="button" onClick={() => setResetFor(null)}>
            Cancel
          </button>
        </form>
      );
    }
    return (
      <>
        <button type="button" onClick={() => startReset(u)} disabled={busyId === u.id}>
          Reset password
        </button>{" "}
        <button
          type="button"
          onClick={() => void onUpdate(u, { is_active: !u.is_active })}
          disabled={busyId === u.id}
        >
          {u.is_active ? "Deactivate" : "Activate"}
        </button>
      </>
    );
  }

  return (
    <div>
      <h1>Users</h1>
      <p className="muted-paragraph">
        Create accounts, reset passwords and deactivate accounts. A password you set is temporary:
        its user chooses their own at their next sign-in. Every change is written to the audit log.
      </p>

      <section className="card">
        <h2>Create a user</h2>
        <form onSubmit={(e) => void onCreate(e)} className="ingest-form">
          <label>
            Username{" "}
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              maxLength={50}
              autoComplete="off"
              aria-describedby="username-rule"
              required
            />
          </label>
          <label>
            Email (optional){" "}
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              maxLength={255}
              autoComplete="off"
            />
          </label>
          <label>
            Role{" "}
            <select value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </label>
          <label>
            Temporary password{" "}
            <input
              type="password"
              value={temporary}
              onChange={(e) => setTemporary(e.target.value)}
              autoComplete="new-password"
              aria-describedby="temporary-rule"
              required
            />
          </label>
          <button type="submit" disabled={creating || !username.trim()}>
            {creating ? "Creating..." : "Create"}
          </button>
        </form>
        <p id="username-rule" className="muted">
          A username uses a to z, 0 to 9 and . _ @ -, so no two can look alike.
        </p>
        <p id="temporary-rule" className="muted">
          At least {MIN_PASSWORD_LENGTH} characters, not spaces alone.
        </p>
      </section>

      {error && (
        <div className="form-error" role="alert">
          {error}
        </div>
      )}
      {notice && <output className="status-line">{notice}</output>}

      <section className="card">
        <h2>Accounts</h2>
        {loading && <div>Loading...</div>}
        <table className="elsets-table">
          <thead>
            <tr>
              <th>Username</th>
              <th>Email</th>
              <th>Role</th>
              <th>Status</th>
              <th>Password</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>
                  <strong>{u.username}</strong>
                </td>
                <td>{u.email ?? ""}</td>
                <td>
                  {u.id === me?.id ? (
                    u.role
                  ) : (
                    <select
                      aria-label={`Role of ${u.username}`}
                      value={u.role}
                      disabled={busyId === u.id}
                      onChange={(e) => void onUpdate(u, { role: e.target.value as UserRole })}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                    </select>
                  )}
                </td>
                <td>{u.is_active ? "Active" : "Deactivated"}</td>
                <td>{u.must_change_password ? "Temporary" : "Own"}</td>
                <td>{actions(u)}</td>
              </tr>
            ))}
            {!loading && users.length === 0 && !error && (
              <tr>
                <td colSpan={6}>No users.</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
