import { useEffect, useRef, useState } from "react";
import {
  createScreen,
  deleteScreen,
  fetchFormFields,
  FormFields,
  listScreens,
  runScreen,
  Screen,
  ScreenInput,
  ScreenRun,
  updateScreen,
} from "../api/screens";
import { addToWatchlist, listWatchlist } from "../api/watchlist";
import { ScreenEditor } from "./ScreenEditor";
import { ScreenResultsTable } from "./ScreenResultsTable";

type EditorState = { isOpen: false } | { isOpen: true; screen: Screen | null };

type RunState =
  | { status: "idle" }
  | { status: "running"; screen: Screen }
  | { status: "done"; screen: Screen; run: ScreenRun };

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}

function describeCriteria(screen: Screen, signalNames: Record<string, string>): string {
  const codeCount = Object.values(screen.form).filter((value) => value != null).length + screen.extra_filters.length;
  const filters = `${codeCount} ${codeCount === 1 ? "filter" : "filters"}`;
  if (!screen.signal) {
    return filters;
  }
  return `${signalNames[screen.signal] ?? screen.signal}, ${filters}`;
}

export function ScreensView() {
  const [screens, setScreens] = useState<Screen[]>([]);
  const [formFields, setFormFields] = useState<FormFields | null>(null);
  const [watchlistTickers, setWatchlistTickers] = useState<Set<string>>(new Set());
  const [editor, setEditor] = useState<EditorState>({ isOpen: false });
  const [runState, setRunState] = useState<RunState>({ status: "idle" });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // Only the most recent run may update the results, so a slow earlier run
  // can't overwrite the screen the user clicked last.
  const latestRunId = useRef(0);

  async function reloadScreens() {
    setScreens(await listScreens());
  }

  useEffect(() => {
    Promise.all([listScreens(), fetchFormFields(), listWatchlist()])
      .then(([loadedScreens, loadedFormFields, entries]) => {
        setScreens(loadedScreens);
        setFormFields(loadedFormFields);
        setWatchlistTickers(new Set(entries.map((entry) => entry.ticker)));
      })
      .catch((loadError) => setError(errorMessage(loadError)));
  }, []);

  async function handleRun(screen: Screen) {
    const runId = ++latestRunId.current;
    setError(null);
    setNotice(null);
    setEditor({ isOpen: false });
    setRunState({ status: "running", screen });
    try {
      const run = await runScreen(screen.id);
      if (runId === latestRunId.current) {
        setRunState({ status: "done", screen, run });
      }
    } catch (runError) {
      if (runId === latestRunId.current) {
        setRunState({ status: "idle" });
        setError(`Couldn't run "${screen.name}": ${errorMessage(runError)}`);
      }
    }
  }

  async function handleDelete(screen: Screen) {
    if (!window.confirm(`Delete the screen "${screen.name}"? This can't be undone.`)) {
      return;
    }
    setError(null);
    try {
      await deleteScreen(screen.id);
      if (runState.status !== "idle" && runState.screen.id === screen.id) {
        setRunState({ status: "idle" });
      }
      await reloadScreens();
    } catch (deleteError) {
      setError(errorMessage(deleteError));
    }
  }

  async function handleSave(input: ScreenInput) {
    // Errors propagate to the editor, which shows them next to the form.
    const saved =
      editor.isOpen && editor.screen ? await updateScreen(editor.screen.id, input) : await createScreen(input);
    setEditor({ isOpen: false });
    await reloadScreens();
    setNotice(`Saved "${saved.name}".`);
  }

  async function handleAddToWatchlist(ticker: string) {
    setError(null);
    setNotice(null);
    try {
      await addToWatchlist(ticker);
      setWatchlistTickers((current) => new Set(current).add(ticker));
    } catch (addError) {
      setError(errorMessage(addError));
    }
  }

  const selectedScreenId = runState.status === "idle" ? null : runState.screen.id;

  return (
    <div className="screens-layout">
      <aside>
        <ul className="screen-list">
          {screens.map((screen) => (
            <li key={screen.id} className="screen-list-item">
              <button
                type="button"
                className="screen-select"
                aria-current={screen.id === selectedScreenId}
                aria-label={`Run ${screen.name}`}
                onClick={() => handleRun(screen)}
              >
                <span className="screen-name">{screen.name}</span>
                <span className="screen-meta">
                  {describeCriteria(screen, formFields?.signals ?? {})}
                  {screen.feeds_watchlist && <>, feeds watchlist</>}
                </span>
              </button>
            </li>
          ))}
        </ul>
        <button
          type="button"
          className="new-screen"
          onClick={() => setEditor({ isOpen: true, screen: null })}
          disabled={!formFields}
        >
          New screen
        </button>
      </aside>

      <section>
        {error && (
          <p role="alert" className="alert">
            {error}
          </p>
        )}
        {notice && (
          <p role="status" className="notice">
            {notice}
          </p>
        )}

        {editor.isOpen && formFields ? (
          <ScreenEditor
            initial={editor.screen}
            formFields={formFields}
            onSave={handleSave}
            onCancel={() => setEditor({ isOpen: false })}
          />
        ) : (
          <ScreenResults
            runState={runState}
            onRunAgain={handleRun}
            onEdit={(screen) => setEditor({ isOpen: true, screen })}
            onDelete={handleDelete}
            onAddToWatchlist={handleAddToWatchlist}
            watchlistTickers={watchlistTickers}
          />
        )}
      </section>
    </div>
  );
}

interface ScreenResultsProps {
  runState: RunState;
  onRunAgain: (screen: Screen) => void;
  onEdit: (screen: Screen) => void;
  onDelete: (screen: Screen) => void;
  onAddToWatchlist: (ticker: string) => void;
  watchlistTickers: Set<string>;
}

function ScreenResults({ runState, onRunAgain, onEdit, onDelete, onAddToWatchlist, watchlistTickers }: ScreenResultsProps) {
  if (runState.status === "idle") {
    return <p className="empty-state">Pick a screen on the left to run it against Finviz.</p>;
  }

  const { screen } = runState;
  return (
    <>
      <div className="results-header">
        <h2 className="results-title">
          {screen.name}
          {runState.status === "done" && (
            <span className="muted"> {runState.run.rows.length} stocks</span>
          )}
        </h2>
        <div className="toolbar">
          <button type="button" onClick={() => onRunAgain(screen)} disabled={runState.status === "running"}>
            Run again
          </button>
          <button type="button" onClick={() => onEdit(screen)}>
            Edit
          </button>
          <a href={screen.finviz_url} target="_blank" rel="noreferrer">
            Open on Finviz
          </a>
          <button type="button" className="button-quiet" onClick={() => onDelete(screen)}>
            Delete
          </button>
        </div>
      </div>
      {runState.status === "running" ? (
        <p className="muted">Running {screen.name} on Finviz…</p>
      ) : (
        <ScreenResultsTable run={runState.run} onAddToWatchlist={onAddToWatchlist} watchlistTickers={watchlistTickers} />
      )}
    </>
  );
}
