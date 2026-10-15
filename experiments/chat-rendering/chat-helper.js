/*
 * chat-helper.js — synthetic long-chat rendering experiment (NOT a production feature,
 * NOT integrated into any APK, NOT tested against real Arena).
 *
 * Problem being modelled (from the project brief): a long AI chat opens slowly and new
 * answers sometimes appear only after a hard refresh. Goal: apply updates incrementally
 * without page reload while preserving the user's draft, focus, selection and scroll.
 *
 * Two parts:
 *  - ChatStore: transport-agnostic ordering/dedupe/gap logic keyed by a monotonically
 *    increasing sequence number (the same idea as SSE `id:` + `Last-Event-ID` resume,
 *    see MDN "Using server-sent events"). Pure JS, unit-tested in Node.
 *  - ChatView: DOM renderer that mutates only the affected message node, uses
 *    `content-visibility:auto` + `contain-intrinsic-size` for long histories
 *    (web.dev/articles/content-visibility) and restores scroll by anchor element.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ChatHelper = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  class ChatStore {
    constructor() {
      this.messages = new Map(); // id -> {id, role, text, done, seq}
      this.order = [];           // ids in display order
      this.lastSeq = 0;          // highest contiguous seq applied (resume cursor)
      this.pending = new Map();  // seq -> event (received out of order, waiting for gap fill)
      this.stats = { applied: 0, duplicates: 0, gaps: 0, buffered: 0 };
    }

    /**
     * Apply one event {seq, id, role, text?, delta?, done?}.
     * Returns an array of changes [{kind:'append'|'update', id}] actually applied, plus
     * {gapFrom} if the caller must request a resync from that cursor.
     */
    apply(ev) {
      if (!ev || !Number.isInteger(ev.seq) || ev.seq < 1 || typeof ev.id !== "string")
        throw new TypeError("invalid event");
      if (ev.seq <= this.lastSeq || this.pending.has(ev.seq)) {
        this.stats.duplicates++;
        return { changes: [], duplicate: true };
      }
      if (ev.seq > this.lastSeq + 1) {
        this.pending.set(ev.seq, ev);
        this.stats.buffered++;
        this.stats.gaps++;
        return { changes: [], gapFrom: this.lastSeq };
      }
      const changes = [this._applyOne(ev)];
      // drain contiguous buffered events
      while (this.pending.has(this.lastSeq + 1)) {
        const next = this.pending.get(this.lastSeq + 1);
        this.pending.delete(this.lastSeq + 1);
        changes.push(this._applyOne(next));
      }
      return { changes };
    }

    _applyOne(ev) {
      this.lastSeq = ev.seq;
      this.stats.applied++;
      const cur = this.messages.get(ev.id);
      if (!cur) {
        const m = { id: ev.id, role: ev.role || "assistant", text: ev.text != null ? ev.text : (ev.delta || ""), done: !!ev.done, seq: ev.seq };
        this.messages.set(ev.id, m);
        this.order.push(ev.id);
        return { kind: "append", id: ev.id };
      }
      if (ev.text != null) cur.text = ev.text;
      else if (ev.delta) cur.text += ev.delta;
      if (ev.done) cur.done = true;
      cur.seq = ev.seq;
      return { kind: "update", id: ev.id };
    }

    get size() { return this.order.length; }
  }

  /** Capture what the user would lose on a reload. */
  function captureUserState(scroller, composer, doc) {
    const atBottom = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 2;
    let anchor = null, anchorOffset = 0;
    if (!atBottom) {
      const top = scroller.getBoundingClientRect().top;
      for (const el of scroller.children) {
        const r = el.getBoundingClientRect();
        if (r.bottom > top) { anchor = el; anchorOffset = r.top - top; break; }
      }
    }
    return {
      atBottom, anchor, anchorOffset,
      focused: doc.activeElement === composer,
      value: composer.value,
      selStart: composer.selectionStart, selEnd: composer.selectionEnd, selDir: composer.selectionDirection,
    };
  }

  function restoreUserState(st, scroller, composer, doc) {
    if (st.atBottom) scroller.scrollTop = scroller.scrollHeight;
    else if (st.anchor && st.anchor.isConnected) {
      const top = scroller.getBoundingClientRect().top;
      const drift = (st.anchor.getBoundingClientRect().top - top) - st.anchorOffset;
      if (Math.abs(drift) >= 0.5) scroller.scrollTop += drift;
    }
    if (composer.value !== st.value) composer.value = st.value; // never expected; defensive
    if (st.focused && doc.activeElement !== composer) composer.focus({ preventScroll: true });
    if (st.focused && (composer.selectionStart !== st.selStart || composer.selectionEnd !== st.selEnd))
      composer.setSelectionRange(st.selStart, st.selEnd, st.selDir || "none");
  }

  class ChatView {
    constructor({ scroller, composer, doc, intrinsicSize = 120 }) {
      this.scroller = scroller; this.composer = composer; this.doc = doc || document;
      this.intrinsicSize = intrinsicSize;
      this.store = new ChatStore();
      this.nodes = new Map();
      this.onGap = null;     // (fromSeq) => void : caller requests replay from cursor
      this.hidden = false;   // when page hidden, queue events and render once on return
      this.queue = [];
      this.renders = 0;
    }

    ingest(events) {
      if (this.hidden) { this.queue.push(...events); return; }
      const changes = [];
      let gapFrom = null;
      for (const ev of events) {
        const r = this.store.apply(ev);
        changes.push(...r.changes);
        if (r.gapFrom != null && gapFrom == null) gapFrom = r.gapFrom;
      }
      if (changes.length) this._render(changes);
      if (gapFrom != null && this.onGap) this.onGap(gapFrom);
    }

    setHidden(h) {
      this.hidden = h;
      if (!h && this.queue.length) { const q = this.queue; this.queue = []; this.ingest(q); }
    }

    _render(changes) {
      const st = captureUserState(this.scroller, this.composer, this.doc);
      const frag = this.doc.createDocumentFragment();
      const seen = new Set();
      for (const c of changes) {
        if (seen.has(c.id) && c.kind === "update") continue;
        seen.add(c.id);
        const m = this.store.messages.get(c.id);
        let el = this.nodes.get(c.id);
        if (!el) {
          el = this.doc.createElement("article");
          el.className = "msg " + m.role;
          el.dataset.id = m.id;
          el.style.contentVisibility = "auto";
          el.style.containIntrinsicSize = "auto " + this.intrinsicSize + "px";
          this.nodes.set(c.id, el);
          frag.appendChild(el);
        }
        el.textContent = m.text;
        el.toggleAttribute("data-streaming", !m.done);
      }
      if (frag.childNodes.length) this.scroller.appendChild(frag);
      restoreUserState(st, this.scroller, this.composer, this.doc);
      this.renders++;
    }
  }

  return { ChatStore, ChatView, captureUserState, restoreUserState };
});
