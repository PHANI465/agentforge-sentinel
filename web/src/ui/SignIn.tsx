import { useState } from "react";
import type { FormEvent } from "react";
import type { SentinelClient } from "../api/client";
import type { SessionView } from "../api/types";

export function SignIn({
  client,
  onConnected,
}: {
  client: SentinelClient;
  onConnected: (token: string, session: SessionView) => void;
}) {
  const [token, setToken] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const next = token.trim();
    if (!next) {
      setMessage("Enter the session token issued for this analyst.");
      return;
    }
    setBusy(true);
    setMessage("Checking the session.");
    const health = await client.health();
    if (!health.ok) {
      setBusy(false);
      setMessage(health.message);
      return;
    }
    const session = await client.session(next);
    setBusy(false);
    if (!session.ok) {
      setMessage(session.message);
      return;
    }
    onConnected(next, session.data);
  }

  return (
    <form className="sign-in" onSubmit={onSubmit}>
      <h1>Sentinel analyst</h1>
      <p>Connect with a session token. It stays in memory for this tab and leaves when you sign out or reload.</p>
      <label>
        Session token
        <input
          name="session-token"
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={token}
          onChange={(event) => setToken(event.target.value)}
        />
      </label>
      <button type="submit" disabled={busy}>
        Connect
      </button>
      <p className="status" role="status">
        {message}
      </p>
    </form>
  );
}
