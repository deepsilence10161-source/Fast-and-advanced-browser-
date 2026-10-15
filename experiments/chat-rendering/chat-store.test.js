// node --test experiments/chat-rendering/chat-store.test.js
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { ChatStore } = require("./chat-helper.js");

test("appends in order and tracks cursor", () => {
  const s = new ChatStore();
  s.apply({ seq: 1, id: "a", role: "user", text: "hi" });
  const r = s.apply({ seq: 2, id: "b", text: "yo" });
  assert.deepEqual(r.changes, [{ kind: "append", id: "b" }]);
  assert.equal(s.lastSeq, 2);
  assert.deepEqual(s.order, ["a", "b"]);
});

test("streaming deltas update the same message", () => {
  const s = new ChatStore();
  s.apply({ seq: 1, id: "x", delta: "Hel" });
  s.apply({ seq: 2, id: "x", delta: "lo" });
  const r = s.apply({ seq: 3, id: "x", delta: "!", done: true });
  assert.equal(s.messages.get("x").text, "Hello!");
  assert.equal(s.messages.get("x").done, true);
  assert.equal(s.size, 1);
  assert.deepEqual(r.changes, [{ kind: "update", id: "x" }]);
});

test("duplicates (replay) are ignored", () => {
  const s = new ChatStore();
  s.apply({ seq: 1, id: "a", text: "1" });
  s.apply({ seq: 2, id: "b", text: "2" });
  assert.equal(s.apply({ seq: 1, id: "a", text: "1" }).duplicate, true);
  assert.equal(s.apply({ seq: 2, id: "b", text: "2" }).duplicate, true);
  assert.equal(s.size, 2);
  assert.equal(s.stats.duplicates, 2);
});

test("gap is buffered, reported, and drained when filled", () => {
  const s = new ChatStore();
  s.apply({ seq: 1, id: "a", text: "1" });
  const g = s.apply({ seq: 3, id: "c", text: "3" });
  assert.equal(g.gapFrom, 1);
  assert.equal(s.size, 1);
  assert.equal(s.apply({ seq: 3, id: "c", text: "3" }).duplicate, true, "buffered event replay is a duplicate");
  const r = s.apply({ seq: 2, id: "b", text: "2" });
  assert.deepEqual(r.changes.map(c => c.id), ["b", "c"]);
  assert.deepEqual(s.order, ["a", "b", "c"]);
  assert.equal(s.lastSeq, 3);
  assert.equal(s.pending.size, 0);
});

test("full text replacement wins over earlier deltas", () => {
  const s = new ChatStore();
  s.apply({ seq: 1, id: "a", delta: "draft" });
  s.apply({ seq: 2, id: "a", text: "final", done: true });
  assert.equal(s.messages.get("a").text, "final");
});

test("rejects malformed events", () => {
  const s = new ChatStore();
  assert.throws(() => s.apply({ id: "a" }), TypeError);
  assert.throws(() => s.apply({ seq: 0, id: "a" }), TypeError);
  assert.throws(() => s.apply({ seq: 1.5, id: "a" }), TypeError);
  assert.throws(() => s.apply({ seq: 1, id: 7 }), TypeError);
});
