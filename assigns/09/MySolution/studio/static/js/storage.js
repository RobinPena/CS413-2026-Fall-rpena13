// Storage adapter: the only browser code that knows the database service's
// REST API (API.md): its URLs, request bodies, pagination, error envelope,
// ETags, and If-Match.
//
//   const storage = createStorage(fetch, "http://127.0.0.1:8009/api/v1");
//   const { program, etag } = await storage.createProgram({ name, source, description });
//   const saved = await storage.updateProgram(program.id, etag, { name, source, description });
//
// Methods resolve to plain records (with the record's opaque `etag` where the
// caller will need it for a later change) or reject with StorageError. The UI
// hands the etag back unchanged; only this module turns it into If-Match.

const PAGE_SIZE = 100; // the largest page the service allows (API.md section 6)

export class StorageError extends Error {
  // kind: "network" (no answer), "http" (an answer that is not the API's), or
  // "api" (a documented error envelope, with its code, field, and so on).
  constructor(kind, message, { status = null, code = null, field = null, reason = null, currentRevision = null } = {}) {
    super(message);
    this.name = "StorageError";
    this.kind = kind;
    this.status = status;
    this.code = code;
    this.field = field;
    this.reason = reason;
    this.currentRevision = currentRevision;
  }

  /** Someone else saved the record first; nothing was changed. */
  get isConflict() { return this.code === "revision_conflict"; }

  /** The record (or its collection, or the case) no longer exists. */
  get isNotFound() { return this.code === "record_not_found"; }
}

// Request bodies hold exactly the fields the API accepts (API.md section 4).
function programBody({ name, source, description = "" }) {
  return { name, source, description };
}

function collectionBody({ name, description = "" }) {
  return { name, description };
}

function caseBody({ name, source, expected, description = "" }) {
  const outcome = expected.kind === "value"
    ? { kind: "value", value: expected.value }
    : { kind: "error", category: expected.category };
  return { name, source, expected: outcome, description };
}

function decodeError(status, data) {
  const error = data?.error;
  if (error && typeof error.code === "string" && typeof error.message === "string") {
    return new StorageError("api", error.message, {
      status, code: error.code, field: error.field ?? null, reason: error.reason ?? null,
      currentRevision: error.current_revision ?? null,
    });
  }
  return new StorageError("http", `The database service answered with HTTP ${status}.`, { status });
}

export function createStorage(fetchFn, baseUrl) {
  const segment = (id) => encodeURIComponent(id);

  /** One request. Resolves to { data, etag }; data is null for 204. */
  async function send(method, path, { body, etag } = {}) {
    const headers = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (etag !== undefined) headers["If-Match"] = etag;
    let response;
    try {
      response = await fetchFn(baseUrl + path, {
        method, headers, cache: "no-store", body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new StorageError("network",
        `Cannot reach the database service at ${baseUrl}. Check that it is running, then try again.`);
    }
    if (response.status === 204) return { data: null, etag: null };
    let data = null;
    try {
      data = await response.json();
    } catch {
      // not JSON: reported below
    }
    if (!response.ok) throw decodeError(response.status, data);
    if (data === null || typeof data !== "object") {
      throw new StorageError("http", `The database service sent an unreadable answer (HTTP ${response.status}).`,
        { status: response.status });
    }
    return { data, etag: response.headers.get("ETag") };
  }

  /** A response holding one record: { [key]: record, etag }. */
  async function sendForRecord(key, method, path, options) {
    const { data, etag } = await send(method, path, options);
    if (!data[key] || !etag) {
      throw new StorageError("http",
        "The database service's answer lacked the record or its ETag. If the page is on another origin, "
        + "check that the service allows it (--studio-origin).");
    }
    return { [key]: data[key], etag };
  }

  /** Every record of a list route, following the cursor chain of one snapshot. */
  async function listAll(path) {
    const records = [];
    let query = `?limit=${PAGE_SIZE}`;
    for (;;) {
      const { data } = await send("GET", path + query);
      if (!Array.isArray(data.items)) throw new StorageError("http", "The database service sent an unreadable list.");
      records.push(...data.items);
      if (data.next_cursor === null || data.next_cursor === undefined) return records;
      query = `?limit=${PAGE_SIZE}&cursor=${encodeURIComponent(data.next_cursor)}`;
    }
  }

  const programPath = (id) => `/programs/${segment(id)}`;
  const collectionPath = (id) => `/collections/${segment(id)}`;
  const casePath = (collectionId, caseId) => `${collectionPath(collectionId)}/cases/${segment(caseId)}`;

  return {
    async health() {
      return (await send("GET", "/health")).data;
    },

    listPrograms: () => listAll("/programs"),
    getProgram: (id) => sendForRecord("program", "GET", programPath(id)),
    createProgram: (fields) => sendForRecord("program", "POST", "/programs", { body: programBody(fields) }),
    updateProgram: (id, etag, fields) =>
      sendForRecord("program", "PUT", programPath(id), { body: programBody(fields), etag }),
    async deleteProgram(id, etag) {
      await send("DELETE", programPath(id), { etag });
    },

    listCollections: () => listAll("/collections"),
    getCollection: (id) => sendForRecord("collection", "GET", collectionPath(id)),
    createCollection: (fields) =>
      sendForRecord("collection", "POST", "/collections", { body: collectionBody(fields) }),
    updateCollection: (id, etag, fields) =>
      sendForRecord("collection", "PUT", collectionPath(id), { body: collectionBody(fields), etag }),
    async deleteCollection(id, etag) {
      await send("DELETE", collectionPath(id), { etag });
    },

    // Case changes use the collection's etag and answer with the whole collection.
    addCase: (collectionId, etag, fields) =>
      sendForRecord("collection", "POST", `${collectionPath(collectionId)}/cases`, { body: caseBody(fields), etag }),
    updateCase: (collectionId, caseId, etag, fields) =>
      sendForRecord("collection", "PUT", casePath(collectionId, caseId), { body: caseBody(fields), etag }),
    deleteCase: (collectionId, caseId, etag) =>
      sendForRecord("collection", "DELETE", casePath(collectionId, caseId), { etag }),
  };
}
