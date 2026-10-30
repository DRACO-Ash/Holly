import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import BrandPlate from "../components/BrandPlate";
import { useAuth } from "../context/AuthContext";
import { extractErrorMessage } from "../utils/errors";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      setError(extractErrorMessage(err, "Sign in failed."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-form" onSubmit={onSubmit}>
        <BrandPlate />
        <h1>Sign in</h1>
        <label>
          Username{" "}
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
            required
          />
        </label>
        <label>
          Password{" "}
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && <div className="form-error">{error}</div>}
        <button type="submit" disabled={submitting}>
          {submitting ? "Signing in..." : "Sign in"}
        </button>
        <details className="login-help">
          <summary>Forgotten your password?</summary>
          <ul>
            <li>
              Ask an administrator to reset it on the Users page. They give you a temporary
              password.
            </li>
            <li>Sign in with it, and Holly asks you to choose your own before anything else.</li>
            <li>To change a password you know, sign in and open Password in the navigation.</li>
          </ul>
        </details>
      </form>
    </div>
  );
}
