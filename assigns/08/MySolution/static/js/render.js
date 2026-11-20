// DOM rendering for the N-Queens client: draws the board, the attack line,
// the status sentence, counters, controls and log from the player's state.
// It never talks to the server.

import { controlState } from "./player.js";

const QUEEN = "♛︎"; // black chess queen, text presentation (not emoji)
const SVG = "http://www.w3.org/2000/svg";

const MODE_TEXT = {
  idle: "Ready",
  paused: "Paused",
  playing: "Playing",
  seeking: "Finding the next solution",
  done: "Complete",
  error: "Stopped by an error",
};

export function createRenderer(doc) {
  const $ = (id) => doc.getElementById(id);
  const el = {
    frame: $("board-frame"), board: $("board"), line: $("attack-line"),
    columns: $("column-labels"), rows: $("row-labels"),
    status: $("status"), milestone: $("milestone"), error: $("error"), log: $("log"), mode: $("mode"),
    start: $("start"), step: $("step"), play: $("play"), nextSolution: $("next-solution"), reset: $("reset"),
    count: {
      solutions: $("count-solutions"), events: $("count-events"), try: $("count-try"),
      reject: $("count-reject"), backtrack: $("count-backtrack"),
    },
  };
  let squares = [];
  let builtSize = 0;
  let loggedSeq = 0;

  function build(size) {
    el.frame.style.setProperty("--n", size);
    el.board.replaceChildren();
    squares = [];
    for (let row = 0; row < size; row += 1) {
      squares.push([]);
      for (let column = 0; column < size; column += 1) {
        const square = doc.createElement("div");
        square.className = (row + column) % 2 === 0 ? "square light" : "square dark";
        el.board.append(square);
        squares[row].push(square);
      }
    }
    const labels = (count) => Array.from({ length: count }, (_, i) => {
      const label = doc.createElement("span");
      label.textContent = String(i);
      return label;
    });
    el.columns.replaceChildren(...labels(size));
    el.rows.replaceChildren(...labels(size));
    el.line.setAttribute("viewBox", `0 0 ${size} ${size}`);
    builtSize = size;
  }

  function drawBoard(view) {
    const { focus, attack } = view;
    for (let row = 0; row < view.size; row += 1) {
      for (let column = 0; column < view.size; column += 1) {
        const square = squares[row][column];
        const queen = view.board[row] === column;
        square.dataset.mark = queen ? "queen" : "";
        square.textContent = queen ? QUEEN : "";
        delete square.dataset.attacker;
        delete square.dataset.path;
      }
    }
    if (focus !== null) {
      const square = squares[focus.row][focus.column];
      square.dataset.mark = focus.kind; // try, place, reject or backtrack
      square.textContent = focus.kind === "reject" ? "✕" : focus.kind === "backtrack" ? "↩" : QUEEN;
    }
    el.line.replaceChildren();
    if (attack !== null) {
      squares[attack.row][attack.column].dataset.attacker = "true";
      for (const [row, column] of attack.path) squares[row][column].dataset.path = "true";
      const line = doc.createElementNS(SVG, "line");
      line.setAttribute("x1", attack.column + 0.5);
      line.setAttribute("y1", attack.row + 0.5);
      line.setAttribute("x2", focus.column + 0.5);
      line.setAttribute("y2", focus.row + 0.5);
      el.line.append(line);
    }
    const kind = view.lastEvent?.event;
    el.frame.dataset.state = view.complete ? "done" : kind === "solution" ? "solution" : "";
    [...el.rows.children].forEach((label, row) => label.classList.toggle("active", focus?.row === row));
    const queens = view.board.map((column, row) => `row ${row} column ${column}`);
    el.board.setAttribute("aria-label", queens.length ? `Queens at ${queens.join(", ")}` : "Empty board");
  }

  function drawLog(view) {
    if (view.seq < loggedSeq) { // a reset started a new search
      el.log.replaceChildren();
      loggedSeq = 0;
    }
    for (const entry of view.log) {
      if (entry.seq <= loggedSeq) continue;
      const item = doc.createElement("li");
      item.dataset.kind = entry.kind;
      const number = doc.createElement("span");
      number.className = "seq";
      number.textContent = String(entry.seq);
      item.append(number, entry.text);
      el.log.prepend(item); // newest first
      loggedSeq = entry.seq;
    }
    while (el.log.children.length > view.log.length) el.log.lastElementChild.remove();
  }

  function render(state) {
    const { view } = state;
    if (view.size !== builtSize) build(view.size);
    drawBoard(view);
    drawLog(view);

    const last = view.log.at(-1);
    el.status.textContent = state.mode === "seeking" ? `Searching for solution ${view.solutions + 1}…`
      : last ? last.text : "Press Start to watch the search, or Step to go one event at a time.";
    el.status.dataset.kind = view.lastEvent?.event ?? "";
    el.mode.textContent = MODE_TEXT[state.mode];

    const milestone = view.complete ? `Search complete: ${view.solutions} ${view.solutions === 1 ? "solution" : "solutions"}`
      : view.lastEvent?.event === "solution" ? `Solution ${view.solutions}` : "";
    el.milestone.textContent = milestone;
    el.milestone.hidden = milestone === "";
    el.milestone.dataset.kind = view.complete ? "done" : "solution";

    el.error.textContent = state.error ?? "";
    el.error.hidden = state.error === null;

    el.count.solutions.textContent = view.solutions;
    el.count.events.textContent = view.seq;
    el.count.try.textContent = view.counts.try;
    el.count.reject.textContent = view.counts.reject;
    el.count.backtrack.textContent = view.counts.backtrack;

    const controls = controlState(state);
    el.start.textContent = controls.start.label;
    el.play.textContent = controls.play.label;
    el.play.setAttribute("aria-pressed", String(controls.play.pressed));
    for (const name of ["start", "step", "play", "nextSolution", "reset"]) el[name].disabled = !controls[name].enabled;
  }

  return { render };
}
