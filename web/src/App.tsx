import { useState } from "react";
import { createClient } from "./api/client";
import type { SentinelClient } from "./api/client";
import type { DocumentClient } from "./api/documents";
import type { SessionView } from "./api/types";
import { SignIn } from "./ui/SignIn";
import { Workbench } from "./ui/Workbench";

export function App({ client = createClient(), documents }: { client?: SentinelClient; documents?: DocumentClient }) {
  const [auth, setAuth] = useState<{ token: string; session: SessionView } | null>(null);
  if (!auth) {
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
