import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { useAsync } from "./useAsync";

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

function Probe({ fetcher }) {
  const [id, setId] = useState("a");
  const state = useAsync((signal) => fetcher(id, signal), [id]);
  return (
    <div>
      <button onClick={() => setId("b")}>switch</button>
      <button onClick={state.reload}>reload</button>
      <span data-testid="out">{state.loading ? "loading" : state.error ? `error:${state.error.message}` : String(state.data)}</span>
    </div>
  );
}

describe("useAsync", () => {
  it("ignores a stale response that arrives after the filter changed", async () => {
    const pending = { a: deferred(), b: deferred() };
    const signals = {};
    render(<Probe fetcher={(id, signal) => { signals[id] = signal; return pending[id].promise; }} />);
    expect(screen.getByTestId("out")).toHaveTextContent("loading");

    await userEvent.click(screen.getByText("switch"));
    expect(signals.a.aborted).toBe(true);

    await act(async () => { pending.b.resolve({ data: "B" }); });
    await waitFor(() => expect(screen.getByTestId("out")).toHaveTextContent("B"));

    await act(async () => { pending.a.resolve({ data: "A" }); });
    expect(screen.getByTestId("out")).toHaveTextContent("B");
  });

  it("exposes errors and refetches on reload", async () => {
    const calls = [];
    render(<Probe fetcher={async () => { calls.push(1); if (calls.length === 1) throw new Error("down"); return { data: "ok" }; }} />);
    await waitFor(() => expect(screen.getByTestId("out")).toHaveTextContent("error:down"));
    await userEvent.click(screen.getByText("reload"));
    await waitFor(() => expect(screen.getByTestId("out")).toHaveTextContent("ok"));
    expect(calls).toHaveLength(2);
  });
});
