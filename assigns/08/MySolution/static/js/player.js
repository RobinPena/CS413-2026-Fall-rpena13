// Playback state and the event reducer for the N-Queens client (DESIGN.md section 8).
//
// No DOM access: the RPC client, the timer functions and the change callback
// are injected, so the Node tests can drive every control with fakes.

export const LOG_LIMIT = 200;
export const BATCH_LIMIT = 32; // Next solution reads up to this many events per request
const STREAM_NOT_FOUND = -32020;

export function emptyView(size) {
  return {
    size,
    board: [], // committed queens from the latest snapshot, in row order
    focus: null, // {row, column, kind}: the square the latest event is about
    attack: null, // for a rejection: the attacking queen and the squares between
    lastEvent: null,
    solutions: 0,
    lastSolution: null,
    complete: false,
    counts: { try: 0, place: 0, reject: 0, backtrack: 0, solution: 0 },
    seq: 0, // number of events shown
    log: [], // the latest LOG_LIMIT entries, oldest first: {seq, kind, text}
  };
}

// The nearest earlier queen attacking (row, column), checked in the same
// order as queens_check_safe in solver.lam. Display logic only.
export function explainReject(board, column, row) {
  for (let earlier = row - 1; earlier >= 0; earlier -= 1) {
    const other = board[earlier];
    const reason = other === column ? "column"
      : Math.abs(other - column) === row - earlier ? "diagonal" : null;
    if (reason !== null) {
      const step = Math.sign(column - other);
      const path = [];
      for (let r = earlier + 1; r < row; r += 1) path.push([r, other + step * (r - earlier)]);
      return { row: earlier, column: other, reason, path };
    }
  }
  return null;
}

// The status sentence for an event; view is the state after applying it.
export function describe(event, view) {
  const at = `row ${event.row}, column ${event.column}`;
  switch (event.event) {
    case "try": return `Try ${at}`;
    case "place": return `Place queen at ${at}`;
    case "reject": {
      const attack = view.attack;
      if (attack === null) return `Reject ${at}`;
      const how = attack.reason === "column" ? "same column as" : "on a diagonal with";
      return `Reject ${at}: ${how} the queen in row ${attack.row}`;
    }
    case "backtrack": return `Backtrack: remove the queen from ${at}`;
    case "solution": return `Solution ${view.solutions}: [${event.board.join(", ")}]`;
    case "done": return `Search complete: ${view.solutions} ${view.solutions === 1 ? "solution" : "solutions"}`;
    default: return `Unknown event ${event.event}`;
  }
}

// Pure reducer: the committed board always comes from the event's snapshot,
// and the candidate square is kept apart in focus, so drawing a candidate
// can never corrupt the committed board.
export function applyEvent(view, event) {
  const next = {
    ...view, counts: { ...view.counts }, seq: view.seq + 1, lastEvent: event, focus: null, attack: null,
  };
  switch (event.event) {
    case "try":
    case "place":
    case "backtrack":
      next.board = event.board;
      next.focus = { row: event.row, column: event.column, kind: event.event };
      break;
    case "reject":
      next.board = event.board;
      next.focus = { row: event.row, column: event.column, kind: "reject" };
      next.attack = explainReject(event.board, event.column, event.row);
      break;
    case "solution":
      next.board = event.board;
      next.solutions = view.solutions + 1;
      next.lastSolution = event.board;
      break;
    case "done":
      next.complete = true;
      break;
    default:
      throw new Error(`unknown event ${event.event}`);
  }
  if (event.event in next.counts) next.counts[event.event] += 1;
  next.log = [...view.log, { seq: next.seq, kind: event.event, text: describe(event, next) }].slice(-LOG_LIMIT);
  return next;
}

// Slider position 0-100 to milliseconds per event: 1000 ms down to 10 ms.
export function delayForSpeed(position) {
  return Math.round(1000 * 0.01 ** (position / 100));
}

export function errorMessage(error) {
  if (error?.code === STREAM_NOT_FOUND) {
    return "The search expired on the server. Press Restart to begin a new search.";
  }
  if (typeof error?.code === "number") {
    return `The server refused the request (error ${error.code}: ${error.message}). Press Restart to try again.`;
  }
  return `Could not reach the server (${error?.message ?? error}). Check that it is running, then press Restart.`;
}

// Which controls are usable, and their labels, for a player state.
export function controlState(state) {
  const consuming = !state.inFlight && ["idle", "paused", "playing"].includes(state.mode);
  const active = state.mode === "playing" || state.mode === "seeking";
  return {
    start: { enabled: true, label: state.mode === "idle" ? "Start" : "Restart" },
    step: { enabled: consuming },
    play: {
      enabled: active || consuming || (state.mode === "paused" && state.inFlight),
      label: active ? "Pause" : "Play",
      pressed: active,
    },
    nextSolution: { enabled: consuming },
    reset: { enabled: true },
  };
}

export function createPlayer({
  rpc, schedule = setTimeout, cancel = clearTimeout, onChange = () => {}, size = 8, delay = 160,
}) {
  const state = {
    run: 0, // generation: Start and Reset increment it, so older responses are ignored
    size,
    delay,
    pauseAtSolution: true,
    streamId: null,
    mode: "idle", // idle | paused | playing | seeking | done | error
    inFlight: false, // at most one queens.open or queens.next at a time
    buffer: [], // events fetched but not shown yet
    view: emptyView(size),
    error: null,
  };
  let timer = null;

  const notify = () => onChange(state);
  const stopTimer = () => {
    if (timer !== null) cancel(timer);
    timer = null;
  };
  const closeQuietly = (streamId) => {
    rpc.call("queens.close", { stream_id: streamId }).catch(() => {});
  };

  function fail(error) {
    stopTimer();
    state.mode = "error";
    state.error = errorMessage(error);
  }

  function finish() {
    stopTimer();
    state.mode = "done";
    state.buffer = [];
    if (state.streamId !== null) closeQuietly(state.streamId); // release the server's exhausted record
    state.streamId = null;
  }

  // Each request below resolves false if it failed or if Reset made it stale;
  // a stale response never touches the state.
  async function request(run, method, params) {
    state.inFlight = true;
    notify();
    try {
      const result = await rpc.call(method, params);
      return run === state.run ? { result } : { stale: result };
    } catch (error) {
      if (run === state.run) fail(error);
      return null;
    } finally {
      if (run === state.run) state.inFlight = false;
    }
  }

  async function ensureStream(run) {
    if (state.streamId !== null) return true;
    const answer = await request(run, "queens.open", { size: state.size });
    if (answer?.stale) closeQuietly(answer.stale.stream_id); // opened for a search that was reset
    if (!answer?.result) return false;
    state.streamId = answer.result.stream_id;
    return true;
  }

  // Make sure at least one event is buffered, fetching up to limit if needed.
  async function fill(run, limit) {
    if (state.buffer.length > 0) return true;
    if (!(await ensureStream(run))) return false;
    const answer = await request(run, "queens.next", { stream_id: state.streamId, limit });
    if (!answer?.result) return false;
    if (answer.result.events.length === 0) { // already exhausted: nothing left to show
      finish();
      return false;
    }
    state.buffer.push(...answer.result.events);
    return true;
  }

  function showOne() {
    const event = state.buffer.shift();
    state.view = applyEvent(state.view, event);
    if (event.event === "done") finish();
    return event;
  }

  const canConsume = () => !state.inFlight && ["idle", "paused", "playing"].includes(state.mode);

  // If Play was pressed while another request was pending, keep playing now.
  function resumeIfPlaying() {
    if (state.mode === "playing" && timer === null) timer = schedule(tick, state.delay);
  }

  async function tick() {
    timer = null;
    const run = state.run;
    if (state.mode !== "playing" || state.inFlight) return;
    const ready = await fill(run, 1);
    if (run !== state.run) return;
    if (ready && state.mode === "playing") { // if paused meanwhile, the event stays buffered
      const event = showOne();
      if (state.mode === "playing") {
        if (event.event === "solution" && state.pauseAtSolution) state.mode = "paused";
        else timer = schedule(tick, event.event === "solution" ? state.delay * 4 : state.delay);
      }
    }
    notify();
  }

  async function step() {
    if (!canConsume()) return;
    stopTimer();
    state.mode = "paused";
    const run = state.run;
    const ready = await fill(run, 1);
    if (run !== state.run) return;
    if (ready) showOne();
    resumeIfPlaying();
    notify();
  }

  function play() {
    if (!["idle", "paused"].includes(state.mode)) return;
    state.mode = "playing";
    notify();
    tick();
  }

  function pause() {
    if (state.mode !== "playing" && state.mode !== "seeking") return;
    stopTimer();
    state.mode = "paused";
    notify();
  }

  async function nextSolution() {
    if (!canConsume()) return;
    stopTimer();
    state.mode = "seeking";
    notify();
    const run = state.run;
    while (await fill(run, BATCH_LIMIT)) {
      if (run !== state.run || state.mode !== "seeking") break;
      while (state.buffer.length > 0 && state.mode === "seeking") {
        if (showOne().event === "solution") state.mode = "paused"; // the rest stays buffered
      }
      if (state.mode !== "seeking") break;
      notify(); // progress between batches
    }
    if (run !== state.run) return;
    resumeIfPlaying();
    notify();
  }

  function reset() {
    state.run += 1;
    stopTimer();
    if (state.streamId !== null) closeQuietly(state.streamId);
    Object.assign(state, {
      streamId: null, mode: "idle", inFlight: false, buffer: [], error: null, view: emptyView(state.size),
    });
    notify();
  }

  return {
    state,
    start() { reset(); play(); },
    step,
    play,
    pause,
    togglePlay() { (state.mode === "playing" || state.mode === "seeking") ? pause() : play(); },
    nextSolution,
    reset,
    setSize(newSize) {
      if (newSize === state.size) return;
      state.size = newSize;
      reset();
    },
    setDelay(ms) { state.delay = ms; },
    setPauseAtSolution(on) { state.pauseAtSolution = on; },
  };
}
