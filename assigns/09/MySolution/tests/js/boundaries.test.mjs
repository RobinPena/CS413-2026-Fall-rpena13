// Responsibility boundaries in the studio code (DESIGN.md STU-1). Run from
// assigns/09/ with:  node --test MySolution/tests/js/
//
// UI code (main.js) must not know REST or JSON-RPC details: those belong to
// storage.js and lambda3.js. The logic modules must not touch the page.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const read = (name) => readFileSync(new URL(`../../studio/static/js/${name}`, import.meta.url), "utf8");
const withoutComments = (source) => source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");

test("main.js holds no REST or JSON-RPC details", () => {
  const code = withoutComments(read("main.js"));
  const details = ["/api", "/programs", "/collections", "/cases", "/rpc", "If-Match", "ETag", "cursor",
    "limit=", "jsonrpc", "lambda.interpret", "-320", "revision_conflict", "record_not_found", "status ===",
    "method:", "headers"];
  for (const detail of details) {
    assert.ok(!code.includes(detail), `main.js mentions ${JSON.stringify(detail)}`);
  }
});

test("only storage.js sends If-Match, and only lambda3.js speaks JSON-RPC", () => {
  for (const name of ["main.js", "lambda3.js", "runner.js"]) {
    assert.ok(!withoutComments(read(name)).includes("If-Match"), name);
  }
  for (const name of ["main.js", "storage.js", "runner.js"]) {
    assert.ok(!withoutComments(read(name)).includes("jsonrpc"), name);
  }
});

test("storage.js, lambda3.js, and runner.js do not touch the page", () => {
  for (const name of ["storage.js", "lambda3.js", "runner.js"]) {
    const code = withoutComments(read(name));
    assert.ok(!/\b(document|window)\b/.test(code), name);
  }
});
