import { useState } from "react";
import { HomePage } from "./pages/HomePage";
import { ChatPage } from "./pages/ChatPage";

/**
 * Client-side route for this two-page app.
 *
 * Decision (T-1.2-03): a minimal state-based switch is used instead of
 * react-router-dom. This is a two-page app (HomePage, ChatPage) with no
 * nested routes and no requirement to deep-link a URL to a run yet, so a
 * routing library would add a dependency (and its own supply-chain check)
 * for no functional gain this ticket. Revisit if a later ticket needs
 * URL-addressable runs (e.g. sharing a `run_id` link).
 */
export type Route = { name: "home" } | { name: "chat"; query: string };

function App() {
  const [route, setRoute] = useState<Route>({ name: "home" });

  if (route.name === "chat") {
    return (
      <ChatPage
        initialQuery={route.query}
        onExit={() => setRoute({ name: "home" })}
      />
    );
  }

  return (
    <HomePage
      onSubmitQuery={(query) => setRoute({ name: "chat", query })}
    />
  );
}

export default App;
