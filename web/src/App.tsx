import { useState } from "react";
import { createClient } from "./api/client";
import type { SentinelClient } from "./api/client";
import type { DocumentClient } from "./api/documents";
import type { SessionView } from "./api/types";
import { SignIn } from "./ui/SignIn";
import { Workbench } from "./ui/Workbench";

function HostedSignIn({
  client,
  onConnected,
}: {
  client: SentinelClient;
  onConnected: (token: string, session: SessionView) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function start() {
    setBusy(true);
    setMessage("Preparing your synthetic case.");
    try {
      const response = await fetch("/demo/session", { method: "POST" });
      if (response.status === 429) {
        setMessage("The public demo has reached its session limit. You can still open the recorded case.");
        return;
      }
      if (!response.ok) throw new Error("session");
      const { token } = await response.json();
      if (typeof token !== "string" || !/^[A-Za-z0-9_-]{43}$/.test(token)) throw new Error("token");
      const session = await client.session(token);
      if (!session.ok) throw new Error("session");
      onConnected(token, session.data);
    } catch {
      setMessage("Couldn't start a demo session. Try again or open the recorded case.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="sign-in">
      <h1>Try the analyst workbench</h1>
      <p>Open an isolated synthetic case. Your session lasts 30 minutes. Approvals and actions are simulated.</p>
      <button type="button" onClick={start} disabled={busy}>Start a demo case</button>
      <p className="status" role="status">{message}</p>
      <p><a href="/walkthrough.html">Open the recorded case</a></p>
    </section>
  );
}

export function App({ client = createClient(), documents }: { client?: SentinelClient; documents?: DocumentClient }) {
  const [auth, setAuth] = useState<{ token: string; session: SessionView } | null>(null);
  if (!auth) {
    if (import.meta.env.VITE_SENTINEL_HOSTED_DEMO === "1") {
      return <HostedSignIn client={client} onConnected={(token, session) => setAuth({ token, session })} />;
    }
    return <SignIn client={client} onConnected={(token, session) => setAuth({ token, session })} />;
  }
  return (
    <Workbench
      client={client}
      token={auth.token}
      session={auth.session}
      onSignOut={() => setAuth(null)}
      documents={documents}
    />
  );
}
