// JSON-RPC 2.0 over HTTP POST /rpc for the N-Queens client.
//
// createRpcClient(fetchFn, url).call(method, params) resolves to the result,
// or rejects with RpcError (the server answered with a JSON-RPC error) or
// TransportError (no usable answer: network failure, HTTP status, bad body).

export class RpcError extends Error {
  constructor(code, message, data) {
    super(message);
    this.name = "RpcError";
    this.code = code;
    this.data = data;
  }
}

export class TransportError extends Error {
  constructor(message) {
    super(message);
    this.name = "TransportError";
  }
}

export function createRpcClient(fetchFn, url = "/rpc") {
  let nextId = 1;
  return {
    async call(method, params) {
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
        throw new TransportError(`network error: ${error.message}`);
      }
      if (response.status !== 200) throw new TransportError(`HTTP status ${response.status}`);
      let body;
      try {
        body = await response.json();
      } catch {
        throw new TransportError("the answer was not JSON");
      }
      if (body === null || typeof body !== "object" || body.id !== id) {
        throw new TransportError("the answer did not match the request");
      }
      if (body.error) throw new RpcError(body.error.code, body.error.message, body.error.data);
      return body.result;
    },
  };
}
