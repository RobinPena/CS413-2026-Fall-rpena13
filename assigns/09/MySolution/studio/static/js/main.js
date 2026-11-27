// LAMBDA-studio page: connects the DOM to the storage adapter (storage.js),
// the LAMBDA3 client (lambda3.js), and the run logic (runner.js).
//
// No REST URL, HTTP header, ETag, or JSON-RPC detail appears in this file.
// The adapter returns each record with an opaque `etag`, which is handed
// back unchanged when that record is saved or deleted. A stale save is never
// retried automatically, and local edits are never discarded without the
// user's say-so.

import { createLambda3Client, describeOutcome } from "./lambda3.js";
import { changeSinceRun, describeExpected, runCases, snapshotCases, summarize } from "./runner.js";
import { createStorage } from "./storage.js";

const $ = (id) => document.getElementById(id);
const browserFetch = (...args) => fetch(...args);

let storage;
let lambda3;

// ------------------------------------------------------------------ messages

function showMessage(text, kind = "info") {
  const box = $("message");
  box.textContent = text;
  box.className = `message ${kind}`;
  box.hidden = false;
}

function showError(action, error) {
  showMessage(`${action}: ${error.message}`, "error");
}

function clearMessage() {
  $("message").hidden = true;
}

function setChip(id, text, kind) {
  $(id).textContent = text;
  $(id).className = `chip ${kind}`;
}

async function checkServices() {
  try {
    await storage.health();
    setChip("db-status", "Database: connected", "ok");
  } catch {
    setChip("db-status", "Database: unreachable", "bad");
  }
  const available = await lambda3.isAvailable();
  setChip("lambda-status", available ? "LAMBDA3: connected" : "LAMBDA3: unreachable", available ? "ok" : "bad");
}

// ----------------------------------------------------------------- lists

function formatTime(iso) {
  return new Date(iso).toLocaleString();
}

function recordButton(record, detail, onOpen) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "record";
  button.dataset.id = record.id;
  const name = document.createElement("span");
  name.className = "record-name";
  name.textContent = record.name;
  const meta = document.createElement("span");
  meta.className = "record-meta";
  meta.textContent = detail;
  button.append(name, meta);
  button.addEventListener("click", onOpen);
  const item = document.createElement("li");
  item.append(button);
  return item;
}

function markCurrent(listId, id) {
  for (const button of $(listId).querySelectorAll("button.record")) {
    button.classList.toggle("current", button.dataset.id === id);
  }
}

// --------------------------------------------------------------- programs

const EMPTY_PROGRAM = Object.freeze({ name: "", description: "", source: "" });

// The program in the editor: its ID and etag (null until first saved), and
// the values last saved, which tell whether the editor holds unsaved edits.
const program = { id: null, etag: null, revision: null, saved: EMPTY_PROGRAM };

function programForm() {
  return { name: $("program-name").value, description: $("program-description").value, source: $("program-source").value };
}

function setProgramForm(fields) {
  $("program-name").value = fields.name;
  $("program-description").value = fields.description;
  $("program-source").value = fields.source;
}

function programIsDirty() {
  const form = programForm();
  return Object.keys(EMPTY_PROGRAM).some((key) => form[key] !== program.saved[key]);
}

function renderProgramState() {
  const dirty = programIsDirty();
  $("program-unsaved").hidden = !dirty;
  $("program-title").textContent = program.id ? program.saved.name : "New program";
  $("program-meta").textContent = program.id ? `revision ${program.revision}` : "not saved yet";
  $("program-reload").disabled = !program.id;
  $("program-delete").disabled = !program.id;
  document.title = anythingUnsaved() ? "● LAMBDA-studio (unsaved changes)" : "LAMBDA-studio";
  markCurrent("program-list", program.id);
}

function showProgram(record, etag) {
  program.id = record.id;
  program.etag = etag;
  program.revision = record.revision;
  program.saved = { name: record.name, description: record.description, source: record.source };
  setProgramForm(program.saved);
  $("program-conflict").hidden = true;
  renderProgramState();
}

function startNewProgram(fields = EMPTY_PROGRAM) {
  program.id = null;
  program.etag = null;
  program.revision = null;
  program.saved = EMPTY_PROGRAM;
  setProgramForm(fields);
  $("program-conflict").hidden = true;
  renderProgramState();
}

function okToLeaveProgram() {
  return !programIsDirty() || window.confirm("Discard your unsaved changes to this program?");
}

async function refreshProgramList() {
  try {
    const records = await storage.listPrograms();
    $("program-list").replaceChildren(...records.map((record) =>
      recordButton(record, `revision ${record.revision} · ${formatTime(record.updated_at)}`, () => openProgram(record.id))));
    $("program-list-empty").hidden = records.length > 0;
    markCurrent("program-list", program.id);
  } catch (error) {
    showError("Could not load the saved programs", error);
  }
}

function newProgram() {
  if (!okToLeaveProgram()) return;
  startNewProgram();
  $("program-kept").hidden = true;
  $("program-output").hidden = true;
  clearMessage();
}

async function openProgram(id) {
  if (!okToLeaveProgram()) return;
  try {
    const { program: record, etag } = await storage.getProgram(id);
    showProgram(record, etag);
    $("program-kept").hidden = true;
    $("program-output").hidden = true;
    clearMessage();
  } catch (error) {
    showError("Could not open the program", error);
    if (error.isNotFound) refreshProgramList();
  }
}

async function saveProgram() {
  const fields = programForm();
  try {
    const { program: record, etag } = program.id
      ? await storage.updateProgram(program.id, program.etag, fields)
      : await storage.createProgram(fields);
    showProgram(record, etag);
    showMessage(`Saved "${record.name}" as revision ${record.revision}.`, "success");
    refreshProgramList();
  } catch (error) {
    if (error.isConflict) showProgramConflict("Not saved", error);
    else if (error.isNotFound && program.id) programDeletedElsewhere();
    else showError("Not saved", error);
  }
}

function showProgramConflict(action, error) {
  const now = error.currentRevision ? `, and the server now has revision ${error.currentRevision}` : "";
  $("program-conflict-text").textContent =
    `${action}: this program was changed elsewhere after you opened revision ${program.revision}${now}. `
    + "The server copy was not overwritten, and your edits are still in the editor. "
    + "Reload the server copy to continue from it; your version will be kept below so that you can copy from it.";
  $("program-conflict").hidden = false;
  clearMessage();
}

function keepVersion(fields) {
  $("program-kept-text").textContent = `Name: ${fields.name}\nDescription: ${fields.description}\n\n${fields.source}`;
  $("program-kept").hidden = false;
  $("program-kept").open = true;
}

async function reloadProgram({ afterConflict = false } = {}) {
  if (!afterConflict && !okToLeaveProgram()) return;
  const mine = programForm();
  const hadEdits = programIsDirty();
  try {
    const { program: record, etag } = await storage.getProgram(program.id);
    showProgram(record, etag);
    if (hadEdits) keepVersion(mine);
    showMessage(`Loaded revision ${record.revision} from the server.`, "info");
  } catch (error) {
    if (error.isNotFound) programDeletedElsewhere();
    else showError("Could not reload the program", error);
  }
}

function programDeletedElsewhere() {
  startNewProgram(programForm());
  showMessage("This program no longer exists on the server: it was deleted elsewhere. Your text is still in the "
    + "editor as a new, unsaved program, and Save would create it again.", "error");
  refreshProgramList();
}

async function deleteProgram() {
  const name = program.saved.name;
  if (!window.confirm(`Delete the program "${name}" from the database?`)) return;
  try {
    await storage.deleteProgram(program.id, program.etag);
    startNewProgram();
    showMessage(`Deleted "${name}".`, "success");
  } catch (error) {
    if (error.isConflict) {
      showProgramConflict("Not deleted", error);
      return;
    }
    if (!error.isNotFound) {
      showError("Not deleted", error);
      return;
    }
    startNewProgram();
    showMessage(`"${name}" had already been deleted elsewhere.`, "info");
  }
  refreshProgramList();
}

async function runProgram() {
  const output = $("program-output");
  output.hidden = false;
  output.className = "output";
  output.textContent = "Running in LAMBDA3…";
  $("program-run").disabled = true;
  const outcome = await lambda3.interpret($("program-source").value);
  $("program-run").disabled = false;
  output.textContent = describeOutcome(outcome);
  output.className = `output ${outcome.kind === "value" ? "ok" : "bad"}`;
}

// ------------------------------------------------------------ collections

// The collection on screen and its etag, as last received from the service.
const collection = { record: null, etag: null };

const EMPTY_CASE = Object.freeze({ name: "", source: "", expectedKind: "value", expectedValue: "", description: "" });

// The case form: the case being edited (null: adding a new case) and the
// values it started from, which tell whether it holds unsaved edits.
const caseForm = { editingId: null, saved: EMPTY_CASE };

// The latest run: { number, collectionId, snapshots, results, current, running }.
let lastRun = null;
let runCount = 0;

function collectionMetaIsDirty() {
  return collection.record !== null && ($("collection-name").value !== collection.record.name
    || $("collection-description").value !== collection.record.description);
}

function caseFormValues() {
  return {
    name: $("case-name").value, source: $("case-source").value, expectedKind: $("case-expected-kind").value,
    expectedValue: $("case-expected-value").value, description: $("case-description").value,
  };
}

function setCaseForm(values) {
  $("case-name").value = values.name;
  $("case-source").value = values.source;
  $("case-expected-kind").value = values.expectedKind;
  $("case-expected-value").value = values.expectedValue;
  $("case-description").value = values.description;
}

function caseIsDirty() {
  const values = caseFormValues();
  return Object.keys(EMPTY_CASE).some((key) => values[key] !== caseForm.saved[key]);
}

function caseFields() {
  const values = caseFormValues();
  const expected = values.expectedKind === "value"
    ? { kind: "value", value: values.expectedValue }
    : { kind: "error", category: values.expectedKind };
  return { name: values.name, source: values.source, expected, description: values.description };
}

function caseToFormValues(item) {
  return {
    name: item.name, source: item.source, description: item.description,
    expectedKind: item.expected.kind === "value" ? "value" : item.expected.category,
    expectedValue: item.expected.kind === "value" ? item.expected.value : "",
  };
}

function anythingUnsaved() {
  return programIsDirty() || collectionMetaIsDirty() || (collection.record !== null && caseIsDirty());
}

function renderCollectionState() {
  $("collection-unsaved").hidden = !collectionMetaIsDirty();
  $("case-unsaved").hidden = !caseIsDirty();
  $("case-value-row").hidden = $("case-expected-kind").value !== "value";
  const editing = collection.record?.cases.find((item) => item.id === caseForm.editingId);
  $("case-form-title").textContent = editing ? `Edit case: ${editing.name}` : "Add a case";
  $("case-save").textContent = editing ? "Save case" : "Add case";
  $("case-cancel").textContent = editing ? "Stop editing" : "Clear";
  $("collection-run").disabled = Boolean(lastRun?.running) || !collection.record?.cases.length;
  document.title = anythingUnsaved() ? "● LAMBDA-studio (unsaved changes)" : "LAMBDA-studio";
}

function okToLeaveCollection() {
  const dirty = collectionMetaIsDirty() || (collection.record !== null && caseIsDirty());
  return !dirty || window.confirm("Discard your unsaved changes in this collection's forms?");
}

async function refreshCollectionList() {
  try {
    const records = await storage.listCollections();
    $("collection-list").replaceChildren(...records.map((record) =>
      recordButton(record, `${record.cases.length} case(s) · revision ${record.revision}`, () => openCollection(record.id))));
    $("collection-list-empty").hidden = records.length > 0;
    markCurrent("collection-list", collection.record?.id);
  } catch (error) {
    showError("Could not load the test collections", error);
  }
}

function resetCaseForm() {
  caseForm.editingId = null;
  caseForm.saved = EMPTY_CASE;
  setCaseForm(EMPTY_CASE);
}

/**
 * Show a collection received from the service. Text the user has typed into
 * the forms is kept (unless `fresh`), so reloading never discards local edits.
 */
function showCollection(record, etag, { fresh = false } = {}) {
  const switching = collection.record?.id !== record.id;
  const keepMeta = !fresh && !switching && collectionMetaIsDirty();
  collection.record = record;
  collection.etag = etag;
  $("collection-none").hidden = true;
  $("collection-detail").hidden = false;
  $("collection-conflict").hidden = true;
  $("collection-title").textContent = record.name;
  $("collection-meta").textContent = `revision ${record.revision} · ${record.cases.length} case(s)`;
  if (!keepMeta) {
    $("collection-name").value = record.name;
    $("collection-description").value = record.description;
  }
  if (fresh || switching) {
    resetCaseForm();
  } else if (caseForm.editingId && !record.cases.some((item) => item.id === caseForm.editingId)) {
    caseForm.editingId = null;      // the case is gone; the form's text stays, as a new case
    caseForm.saved = EMPTY_CASE;
  }
  renderCases(record);
  renderRun();
  markCurrent("collection-list", record.id);
  renderCollectionState();
}

function renderCases(record) {
  const rows = record.cases.map((item, index) => {
    const row = document.createElement("li");
    row.dataset.caseId = item.id;
    const head = document.createElement("div");
    head.className = "case-head";
    const title = document.createElement("strong");
    title.textContent = `${index + 1}. ${item.name}`;
    const expected = document.createElement("span");
    expected.className = "meta";
    expected.textContent = `expects ${describeExpected(item.expected)}`;
    const edit = document.createElement("button");
    edit.type = "button";
    edit.textContent = "Edit";
    edit.className = "case-edit";
    edit.addEventListener("click", () => editCase(item.id));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "Delete";
    remove.className = "case-delete danger";
    remove.addEventListener("click", () => deleteCase(item.id));
    head.append(title, expected, edit, remove);
    const source = document.createElement("pre");
    source.className = "source";
    source.textContent = item.source;
    row.append(head, source);
    if (item.description) {
      const description = document.createElement("p");
      description.className = "hint";
      description.textContent = item.description;
      row.append(description);
    }
    return row;
  });
  $("case-list").replaceChildren(...rows);
  $("case-list-empty").hidden = rows.length > 0;
}

function collectionGone(action) {
  collection.record = null;
  collection.etag = null;
  $("collection-detail").hidden = true;
  $("collection-none").hidden = false;
  showMessage(`${action}: this collection no longer exists on the server; it was deleted elsewhere.`, "error");
  refreshCollectionList();
  renderCollectionState();
}

function showCollectionConflict(action, error) {
  const now = error.currentRevision ? ` (it is now at revision ${error.currentRevision})` : "";
  $("collection-conflict-text").textContent =
    `${action}: this collection was changed elsewhere after you loaded revision ${collection.record.revision}${now}. `
    + "Nothing was changed on the server, and what you typed below is kept. "
    + "Reload the collection to see its current cases, then try again.";
  $("collection-conflict").hidden = false;
  clearMessage();
}

/** After a failed collection or case change: explain it, without retrying anything. */
async function handleCollectionError(action, error) {
  if (error.isConflict) {
    showCollectionConflict(action, error);
  } else if (error.isNotFound) {
    // Either the collection or the case is gone; reading the collection tells which.
    try {
      const { collection: record, etag } = await storage.getCollection(collection.record.id);
      showCollection(record, etag);
      showMessage(`${action}: that case no longer exists; it was deleted elsewhere. The collection has been `
        + "reloaded, and the form keeps your text as a new case.", "error");
    } catch (readError) {
      if (readError.isNotFound) collectionGone(action);
      else showError(action, readError);
    }
  } else {
    showError(action, error);
  }
}

async function createCollection(event) {
  event.preventDefault();
  if (!okToLeaveCollection()) return;
  const fields = { name: $("new-collection-name").value, description: $("new-collection-description").value };
  try {
    const { collection: record, etag } = await storage.createCollection(fields);
    $("new-collection-name").value = "";
    $("new-collection-description").value = "";
    showCollection(record, etag, { fresh: true });
    showMessage(`Created the test collection "${record.name}".`, "success");
    refreshCollectionList();
  } catch (error) {
    showError("Collection not created", error);
  }
}

async function openCollection(id) {
  if (!okToLeaveCollection()) return;
  try {
    const { collection: record, etag } = await storage.getCollection(id);
    showCollection(record, etag, { fresh: true });
    clearMessage();
  } catch (error) {
    showError("Could not open the collection", error);
    if (error.isNotFound) refreshCollectionList();
  }
}

async function reloadCollection() {
  try {
    const { collection: record, etag } = await storage.getCollection(collection.record.id);
    showCollection(record, etag);
    showMessage(`Loaded revision ${record.revision} of "${record.name}" from the server.`, "info");
  } catch (error) {
    if (error.isNotFound) collectionGone("Not reloaded");
    else showError("Could not reload the collection", error);
  }
}

async function saveCollectionDetails() {
  const fields = { name: $("collection-name").value, description: $("collection-description").value };
  try {
    const { collection: record, etag } = await storage.updateCollection(collection.record.id, collection.etag, fields);
    $("collection-name").value = record.name;          // the service trims the name
    $("collection-description").value = record.description;
    showCollection(record, etag);
    showMessage(`Saved the name and description (revision ${record.revision}).`, "success");
    refreshCollectionList();
  } catch (error) {
    handleCollectionError("Name and description not saved", error);
  }
}

async function deleteCollection() {
  const { name, id } = collection.record;
  if (!window.confirm(`Delete the test collection "${name}" and all of its cases?`)) return;
  try {
    await storage.deleteCollection(id, collection.etag);
    collection.record = null;
    collection.etag = null;
    resetCaseForm();
    $("collection-detail").hidden = true;
    $("collection-none").hidden = false;
    showMessage(`Deleted the test collection "${name}".`, "success");
    refreshCollectionList();
    renderCollectionState();
  } catch (error) {
    handleCollectionError("Not deleted", error);
  }
}

function editCase(caseId) {
  if (caseIsDirty() && !window.confirm("Discard the unsaved text in the case form?")) return;
  const item = collection.record.cases.find((candidate) => candidate.id === caseId);
  caseForm.editingId = caseId;
  caseForm.saved = caseToFormValues(item);
  setCaseForm(caseForm.saved);
  renderCollectionState();
  $("case-form").scrollIntoView({ behavior: "smooth", block: "nearest" });
  $("case-name").focus();
}

function stopEditingCase() {
  if (caseIsDirty() && !window.confirm("Discard the unsaved text in the case form?")) return;
  resetCaseForm();
  renderCollectionState();
}

async function saveCase(event) {
  event.preventDefault();
  const editing = caseForm.editingId;
  const action = editing ? "Case not saved" : "Case not added";
  try {
    const { id } = collection.record;
    const { collection: record, etag } = editing
      ? await storage.updateCase(id, editing, collection.etag, caseFields())
      : await storage.addCase(id, collection.etag, caseFields());
    const name = $("case-name").value.trim();
    resetCaseForm();
    showCollection(record, etag);
    showMessage(`${editing ? "Saved" : "Added"} the case "${name}" (collection revision ${record.revision}).`, "success");
    refreshCollectionList();
  } catch (error) {
    handleCollectionError(action, error);
  }
}

async function deleteCase(caseId) {
  const item = collection.record.cases.find((candidate) => candidate.id === caseId);
  if (!window.confirm(`Delete the case "${item.name}"?`)) return;
  try {
    const { collection: record, etag } = await storage.deleteCase(collection.record.id, caseId, collection.etag);
    if (caseForm.editingId === caseId) resetCaseForm();
    showCollection(record, etag);
    showMessage(`Deleted the case "${item.name}" (collection revision ${record.revision}).`, "success");
    refreshCollectionList();
  } catch (error) {
    handleCollectionError("Case not deleted", error);
  }
}

// ------------------------------------------------------------------- runs

async function runCollection() {
  let record;
  let etag;
  try {
    // Run what is saved on the server now, not what the page last showed.
    ({ collection: record, etag } = await storage.getCollection(collection.record.id));
  } catch (error) {
    if (error.isNotFound) collectionGone("Not run");
    else showError("Could not run the collection", error);
    return;
  }
  showCollection(record, etag);
  const snapshots = snapshotCases(record);
  if (snapshots.length === 0) {
    showMessage("This collection has no cases to run.", "info");
    return;
  }
  runCount += 1;
  lastRun = { number: runCount, collectionId: record.id, snapshots, results: [], current: 0, running: true };
  clearMessage();
  renderRun();
  renderCollectionState();
  await runCases(snapshots, lambda3.interpret, {
    onStart: (snapshot, index) => { lastRun.current = index; renderRun(); },
    onResult: (result) => { lastRun.results.push(result); renderRun(); },
  });
  lastRun.running = false;
  renderRun();
  renderCollectionState();
  const { total, passed, failed } = summarize(lastRun.results);
  showMessage(`Run finished: ${passed} of ${total} cases passed${failed ? `, ${failed} failed` : ""}.`,
    failed ? "error" : "success");
}

function cell(text, className) {
  const td = document.createElement("td");
  td.textContent = text;
  if (className) td.className = className;
  return td;
}

function renderRun() {
  const section = $("run-section");
  if (!lastRun || lastRun.collectionId !== collection.record?.id) {
    section.hidden = true;
    return;
  }
  section.hidden = false;
  // Which run is shown and whether it is over (also read by the browser tests).
  section.dataset.run = String(lastRun.number);
  section.dataset.state = lastRun.running ? "running" : "finished";
  const rows = lastRun.snapshots.map((snapshot, index) => {
    const result = lastRun.results[index];
    const row = document.createElement("tr");
    row.dataset.caseId = snapshot.caseId;
    row.dataset.result = result ? (result.passed ? "pass" : "fail") : "pending";

    const name = cell("");
    const label = document.createElement("div");
    label.textContent = snapshot.name;
    const change = changeSinceRun(snapshot, collection.record);
    if (change) {
      const note = document.createElement("span");
      note.className = "badge changed";
      note.textContent = change;
      label.append(" ", note);
    }
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = "source that ran";
    const source = document.createElement("pre");
    source.className = "source";
    source.textContent = snapshot.source;
    details.append(summary, source);
    name.append(label, details);

    let actual = "waiting";
    if (result) actual = describeOutcome(result.outcome);
    else if (lastRun.running && index === lastRun.current) actual = "running…";
    const verdict = result ? (result.passed ? "PASS" : "FAIL") : "—";
    row.append(cell(String(index + 1)), name, cell(describeExpected(snapshot.expected)), cell(actual, "actual"),
      cell(verdict, result ? (result.passed ? "pass" : "fail") : ""));
    return row;
  });
  $("run-results").replaceChildren(...rows);

  const { total, passed, failed } = summarize(lastRun.results);
  $("run-summary").textContent = lastRun.running
    ? `Running case ${lastRun.current + 1} of ${lastRun.snapshots.length}…`
    : `${passed} of ${total} passed, ${failed} failed. Each row shows the case as it was when the run started.`;
}

// ------------------------------------------------------------------ setup

function showTab(name) {
  const programs = name === "programs";
  $("programs-view").hidden = !programs;
  $("collections-view").hidden = programs;
  $("tab-programs").setAttribute("aria-selected", String(programs));
  $("tab-collections").setAttribute("aria-selected", String(!programs));
}

function wireEvents() {
  $("tab-programs").addEventListener("click", () => showTab("programs"));
  $("tab-collections").addEventListener("click", () => showTab("collections"));

  for (const id of ["program-name", "program-description", "program-source"]) {
    $(id).addEventListener("input", renderProgramState);
  }
  $("programs-refresh").addEventListener("click", refreshProgramList);
  $("program-new").addEventListener("click", newProgram);
  $("program-save").addEventListener("click", saveProgram);
  $("program-reload").addEventListener("click", () => reloadProgram());
  $("program-run").addEventListener("click", runProgram);
  $("program-delete").addEventListener("click", deleteProgram);
  $("program-conflict-reload").addEventListener("click", () => reloadProgram({ afterConflict: true }));
  $("program-conflict-dismiss").addEventListener("click", () => { $("program-conflict").hidden = true; });

  for (const id of ["collection-name", "collection-description", "case-name", "case-source",
    "case-expected-kind", "case-expected-value", "case-description"]) {
    $(id).addEventListener("input", renderCollectionState);
  }
  $("collections-refresh").addEventListener("click", refreshCollectionList);
  $("collection-create").addEventListener("submit", createCollection);
  $("collection-reload").addEventListener("click", reloadCollection);
  $("collection-conflict-reload").addEventListener("click", reloadCollection);
  $("collection-save").addEventListener("click", saveCollectionDetails);
  $("collection-delete").addEventListener("click", deleteCollection);
  $("collection-run").addEventListener("click", runCollection);
  $("case-form").addEventListener("submit", saveCase);
  $("case-cancel").addEventListener("click", stopEditingCase);
  $("case-use-program").addEventListener("click", () => {
    $("case-source").value = $("program-source").value;
    renderCollectionState();
  });

  window.addEventListener("beforeunload", (event) => {
    if (anythingUnsaved()) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
}

async function start() {
  wireEvents();
  showTab("programs");
  let config;
  try {
    config = await (await fetch("config.json", { cache: "no-store" })).json();
  } catch {
    showMessage("Could not load the studio's configuration from the studio host. Reload the page to try again.", "error");
    return;
  }
  storage = createStorage(browserFetch, config.database_url);
  lambda3 = createLambda3Client(browserFetch);
  startNewProgram();
  renderCollectionState();
  await Promise.all([checkServices(), refreshProgramList(), refreshCollectionList()]);
}

start();
