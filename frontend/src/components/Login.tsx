import { useState } from "react";
import { api, ApiError, setToken, type User } from "../api";
import { HazardIcon } from "./Icons";

export function Login({ onLoggedIn }: { onLoggedIn: (user: User) => void }) {
  const [email, setEmail] = useState("safety@sitepulse.demo");
  const [password, setPassword] = useState("password123");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const { token, user } = await api.login(email, password);
      setToken(token);
      onLoggedIn(user);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={submit}>
        <div className="login-brand-mark"><HazardIcon size={22} /></div>
        <h1>SitePulse</h1>
        <p className="subtitle">Predictive safety intelligence platform</p>
        <label htmlFor="email">Email</label>
        <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <label htmlFor="password">Password</label>
        <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        {error && <p className="error-text">{error}</p>}
        <button type="submit" className="primary" disabled={loading}>
          {loading ? "Signing in..." : "Sign in"}
        </button>
        <div className="demo-accounts">
          Demo logins (password: password123):<br />
          admin@sitepulse.demo — org admin<br />
          safety@sitepulse.demo — safety officer<br />
          foreman@sitepulse.demo — foreman
        </div>
      </form>
    </div>
  );
}
