// LAMBDA Workbench view script.
//
// Renders the state returned by the server and forwards user actions to
// the controller's JSON routes. It makes no decisions of its own: which
// controls are enabled, and why, comes from the model via `state`. All
// text is inserted with textContent, so source and output are shown
// literally, never as markup.
"use strict";

const EDIT_DELAY_MS = 400;
const POLL_MS = 1000;

const byId = (id) => document.getElementById(id);
const el = {
  fileInput: byId("file-input"),
  chooseFile: byId("choose-file"),
  manual: byId("manual-input"),
  sourceInfo: byId("source-info"),
  editor: byId("editor"),
  apply: byId("apply"),
  discard: byId("discard"),
  status: byId("status"),
  error: byId("error"),
  noResults: byId("no-results"),
  results: byId("results"),
};
const loadButtons = document.querySelectorAll("[data-load]");
const actionButtons = document.querySelectorAll("[data-action]");
const OUTCOME_CLASS = { "ok": "outcome-ok", "not implemented": "outcome-pending" };

let state = null;                  // last state received from the server
let working = false;               // a request from this page is in flight
let localDraft = false;            // the editor holds the user's own typing
let editTimer = null;              // pending debounced draft update
let pendingEdit = Promise.resolve();
let pollTimer = null;

// --- talking to the controller ------------------------------------------

async function send(url, options = {}) {
  let response;
  try {
    response = await fetch(url, { method: "POST", ...options });
  } catch {
    return { state, error: { message: "Cannot reach the local server. Is it still running?" } };
  }
  try {
    return await response.json();
  } catch {
    return { state, error: { message: `Unexpected response from the server (HTTP ${response.status}).` } };
  }
}

function postJson(url, body) {
  return send(url, { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

// Runs one user request: shows `label` while it is in flight, keeps the
// controls disabled until the response arrives, then renders whatever
// state the server returns and describes the outcome.
async function run(label, request, describe) {
  if (working) return;
  working = true;
  clearTimeout(editTimer);
  setControlsDisabled();
  showStatus(label);
  showError(null);
  await pendingEdit;
  const data = await request();
  working = false;
  render(data.state);
  showError(data.error);
  if (!state.busy) {
    showStatus(data.error ? "Not done; see the message below." : describe(state));
  }
}

async function refresh() {
  let data;
  try {
    data = await (await fetch("/api/state")).json();
  } catch {
    showError({ message: "Cannot reach the local server. Is it still running?" });
    return;
  }
  render(data.state);
  if (!state.busy) showStatus(state.source ? "Ready." : "Load a source to begin.");
}

async function syncDraft() {
  if (working) return;             // Apply and Discard send their own text
  pendingEdit = postJson("/api/source/edit", { text: el.editor.value });
  const data = await pendingEdit;
  if (working) return;
  render(data.state);
  showError(data.error);
}

// --- rendering ------------------------------------------------------------

function render(newState) {
  if (!newState) return;           // server unreachable: keep the last state
  state = newState;
  renderSource();
  renderControls();
  renderResults();
  clearTimeout(pollTimer);
  if (state.busy) {
    showStatus(`${state.busy} is running…`);
    if (!working) pollTimer = setTimeout(refresh, POLL_MS);
  }
}

function renderSource() {
  const { source, draft } = state;
  let info = "No source loaded.";
  if (source) {
    info = `${source.name} (${source.origin}) · revision ${source.revision}`;
    if (draft !== null) info += " · unapplied edits";
  } else if (draft !== null) {
    info = "Manual input · not applied yet";
  }
  el.sourceInfo.textContent = info;

  // Replace the editor text only when it should show the server's copy:
  // the applied source, or a draft this page did not type (manual input
  // opened, or a reload while edits were pending).
  if (draft === null) {
    localDraft = false;
    setEditor(source ? source.text : "");
  } else if (!localDraft) {
    setEditor(draft);
  }
}

function setEditor(text) {
  if (el.editor.value !== text) el.editor.value = text;
}

function renderControls() {
  for (const button of loadButtons) button.disabled = !state.can_change_source;
  el.apply.disabled = !state.can_apply_or_discard;
  el.discard.disabled = !state.can_apply_or_discard;
  el.editor.readOnly = state.busy !== null;

  // Each disabled action gets its reason; identical reasons are shown
  // once, naming every action they apply to.
  const shown = new Map();
  for (const action of state.actions) {
    byId(`action-${action.id}`).disabled = !action.enabled;
    const line = byId(`reason-${action.id}`);
    line.textContent = action.enabled ? "" : `${action.label}: ${action.reason}`;
    line.hidden = true;
    if (action.enabled) continue;
    const group = shown.get(action.reason);
    if (group) {
      group.labels.push(action.label);
      group.line.textContent = `${group.labels.join(", ")}: ${action.reason}`;
    } else {
      shown.set(action.reason, { line, labels: [action.label] });
      line.hidden = false;
    }
  }
}

function renderResults() {
  el.results.replaceChildren(...state.results.map(resultItem));
  el.noResults.hidden = state.results.length > 0;
}

function resultItem(result) {
  const item = document.createElement("li");
  const summary = document.createElement("p");
  const outcome = document.createElement("span");
  outcome.className = `outcome ${OUTCOME_CLASS[result.outcome] ?? "outcome-error"}`;
  outcome.textContent = result.outcome;
  summary.append(`${result.operation} · revision ${result.revision} · `, outcome,
                 ` — ${result.message}`);
  item.append(summary);
  if (result.output) {
    const output = document.createElement("pre");
    output.textContent = result.output;
    item.append(output);
  }
  return item;
}

function setControlsDisabled() {
  for (const button of [...loadButtons, ...actionButtons, el.apply, el.discard]) {
    button.disabled = true;
  }
  el.editor.readOnly = true;
}

function showStatus(text) {
  el.status.textContent = text;
}

function showError(error) {
  el.error.textContent = error ? error.message : "";
  el.error.hidden = !error;
}

// --- forwarding user actions -----------------------------------------------

const loaded = (s) => `Loaded ${s.source.name} as revision ${s.source.revision}.`;

el.chooseFile.addEventListener("click", () => el.fileInput.click());

el.fileInput.addEventListener("change", () => {
  const file = el.fileInput.files[0];
  el.fileInput.value = "";         // allow choosing the same file again
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  run(`Uploading ${file.name}…`, () => send("/api/source/upload", { body: form }), loaded);
});

el.manual.addEventListener("click", () =>
  run("Opening manual input…", () => send("/api/source/manual"), () => {
    el.editor.focus();
    return "Type an expression, then choose Apply changes.";
  }));

for (const button of document.querySelectorAll('[data-load="canned"]')) {
  button.addEventListener("click", () =>
    run(`Loading ${button.textContent}…`,
        () => send(`/api/source/canned/${button.dataset.example}`), loaded));
}

el.editor.addEventListener("input", () => {
  localDraft = true;
  clearTimeout(editTimer);
  const firstEdit = state === null || state.draft === null;
  editTimer = setTimeout(syncDraft, firstEdit ? 0 : EDIT_DELAY_MS);
});

el.apply.addEventListener("click", () =>
  run("Applying changes…", () => postJson("/api/source/apply", { text: el.editor.value }),
      (s) => `Applied as revision ${s.source.revision}.`));

el.discard.addEventListener("click", () =>
  run("Discarding changes…", () => send("/api/source/discard"),
      () => "Discarded unapplied edits."));

for (const button of actionButtons) {
  const label = button.textContent.trim();
  button.addEventListener("click", () =>
    run(`${label} is running…`, () => send(`/api/actions/${button.dataset.action}`), (s) => {
      const last = s.results.at(-1);
      return last ? `${last.operation} finished: ${last.outcome}.` : "Done.";
    }));
}

refresh();
