// JSON-RPC 2.0 client for the Assign07 LAMBDA3 service, reached through the
// studio host's POST /lambda/rpc forwarder (the same origin as the page).
//
//   const lambda3 = createLambda3Client(fetch);
//   const outcome = await lambda3.interpret(source);
//
// interpret() never rejects. Every result, including a failure to reach the
// service, comes back as an outcome value, so a collection run can record it
// and carry on:
//
//   { kind: "value", type, value }
//   { kind: "error", category, code, message }
//
// category is "syntax" (-32010) or "type" (-32011) for the two LAMBDA3
// errors a test case may expect; "timeout" (-32012), "runtime" (-32013),
// "rejected" (-32602), "internal" (-32603), or "protocol" (any other JSON-RPC
// error) for the other answers; and "transport" when no JSON-RPC answer
// arrived at all.

const CATEGORY_FOR_CODE = new Map([
  [-32010, "syntax"],
  [-32011, "type"],
  [-32012, "timeout"],
  [-32013, "runtime"],
  [-32602, "rejected"],
  [-32603, "internal"],
]);

class TransportFailure extends Error {}

export function createLambda3Client(fetchFn, url = "/lambda/rpc") {
  let nextId = 1;

  /** One call. Resolves to the response object, or throws TransportFailure. */
  async function call(method, params) {
    const id = nextId;
    nextId += 1;
    let response;
    try {
      response = await fetchFn(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", method, params, id }),
      });
    } catch (error) {
      throw new TransportFailure(`the studio host could not be reached (${error.message})`);
    }
    if (response.status !== 200) {
      const text = (await response.text().catch(() => "")).trim();
      throw new TransportFailure(`HTTP ${response.status}${text ? `: ${text}` : ""}`);
    }
    let answer;
    try {
      answer = await response.json();
    } catch {
      throw new TransportFailure("the answer was not JSON");
    }
    if (answer === null || typeof answer !== "object" || answer.id !== id) {
      throw new TransportFailure("the answer did not match the request");
    }
    return answer;
  }

  return {
    async interpret(source) {
      let answer;
      try {
        answer = await call("lambda.interpret", { source });
      } catch (error) {
        if (!(error instanceof TransportFailure)) throw error;
        return { kind: "error", category: "transport", code: null, message: `LAMBDA3 unavailable: ${error.message}` };
      }
      if (answer.error) return errorOutcome(answer.error);
      const { type, value } = answer.result ?? {};
      if (typeof type !== "string" || typeof value !== "string") {
        return { kind: "error", category: "protocol", code: null, message: "LAMBDA3 sent a malformed result" };
      }
      return { kind: "value", type, value };
    },

    /** True when LAMBDA3 answers service.health. */
    async isAvailable() {
      try {
        return (await call("service.health", {})).result?.status === "ok";
      } catch {
        return false;
      }
    },
  };
}

function errorOutcome({ code, message, data }) {
  const category = CATEGORY_FOR_CODE.get(code) ?? "protocol";
  let text = `${message ?? "JSON-RPC error"} (${code})`;
  if (data?.diagnostic) text += `: ${data.diagnostic}`;
  if (data?.line !== undefined) text += ` at line ${data.line}, column ${data.column}`;
  if (data?.limit_seconds !== undefined) text += `: no answer within ${data.limit_seconds} s`;
  return { kind: "error", category, code, message: text };
}

/** A one-line description of an outcome, for display. */
export function describeOutcome(outcome) {
  return outcome.kind === "value" ? `${outcome.value} : ${outcome.type}` : outcome.message;
}
