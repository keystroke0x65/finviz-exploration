import { useEffect, useState } from "react";
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
import { addToWatchlist } from "../api/watchlist";
import { ScreenEditor } from "./ScreenEditor";
import { ScreenResultsTable } from "./ScreenResultsTable";

type EditorState = { isOpen: false } | { isOpen: true; screen: Screen | null };

type RunState =
  | { status: "idle" }
  | { status: "running"; screenName: string }
  | { status: "done"; screenName: string; run: ScreenRun };

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}

export function ScreensView() {
  const [screens, setScreens] = useState<Screen[]>([]);
  const [formFields, setFormFields] = useState<FormFields | null>(null);
  const [editor, setEditor] = useState<EditorState>({ isOpen: false });
  const [runState, setRunState] = useState<RunState>({ status: "idle" });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function reloadScreens() {
    setScreens(await listScreens());
  }

  useEffect(() => {
    Promise.all([listScreens(), fetchFormFields()])
      .then(([loadedScreens, loadedFormFields]) => {
        setScreens(loadedScreens);
        setFormFields(loadedFormFields);
      })
      .catch((loadError) => setError(errorMessage(loadError)));
  }, []);

  async function handleRun(screen: Screen) {
    setError(null);
    setRunState({ status: "running", screenName: screen.name });
    try {
      const run = await runScreen(screen.id);
      setRunState({ status: "done", screenName: screen.name, run });
    } catch (runError) {
      setRunState({ status: "idle" });
      setError(errorMessage(runError));
    }
  }

  async function handleDelete(screen: Screen) {
    if (!window.confirm(`Delete the screen "${screen.name}"?`)) {
      return;
    }
    setError(null);
    try {
      await deleteScreen(screen.id);
      await reloadScreens();
    } catch (deleteError) {
      setError(errorMessage(deleteError));
    }
  }

  async function handleSave(input: ScreenInput) {
    // Errors propagate to the editor, which shows them next to the form.
    if (editor.isOpen && editor.screen) {
      await updateScreen(editor.screen.id, input);
    } else {
      await createScreen(input);
    }
    setEditor({ isOpen: false });
    await reloadScreens();
  }

  async function handleAddToWatchlist(ticker: string) {
    setError(null);
    setNotice(null);
    try {
      await addToWatchlist(ticker);
      setNotice(`${ticker} added to the watchlist.`);
    } catch (addError) {
      setError(errorMessage(addError));
    }
  }

  if (editor.isOpen && formFields) {
    return (
      <ScreenEditor
        initial={editor.screen}
        formFields={formFields}
        onSave={handleSave}
        onCancel={() => setEditor({ isOpen: false })}
      />
    );
  }

  return (
    <section>
      <h2>Screens</h2>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      <ul>
        {screens.map((screen) => (
          <li key={screen.id}>
            <strong>{screen.name}</strong> {screen.feeds_watchlist && <em>feeds watchlist</em>}{" "}
            <button type="button" aria-label={`Run ${screen.name}`} onClick={() => handleRun(screen)}>
              Run
            </button>{" "}
            <button type="button" onClick={() => setEditor({ isOpen: true, screen })}>
              Edit
            </button>{" "}
            <button type="button" onClick={() => handleDelete(screen)}>
              Delete
            </button>{" "}
            <a href={screen.finviz_url} target="_blank" rel="noreferrer">
              Open on Finviz
            </a>
          </li>
        ))}
      </ul>
      <button type="button" onClick={() => setEditor({ isOpen: true, screen: null })}>
        New screen
      </button>

      {runState.status === "running" && <p>Running {runState.screenName}…</p>}
      {runState.status === "done" && (
        <>
          <h3>{runState.screenName}</h3>
          <ScreenResultsTable run={runState.run} onAddToWatchlist={handleAddToWatchlist} />
        </>
      )}
    </section>
  );
}
