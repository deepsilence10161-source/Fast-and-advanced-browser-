#!/usr/bin/env python3
"""HTTP/2 download server for the device speed test (patch 0017, Swiftra Turbo Download).

Why: on an HTTP/1.1 server Chromium's parallel slices already use separate connections. On HTTP/2 (most real
servers and CDNs) they are streams on ONE connection, so a limit per connection (a server limit, or the per-flow
limit of TCP/QUIC congestion control on a lossy, high-RTT mobile link) caps the whole download. This server models
that: TLS + ALPN h2 only, and each connection is paced to `rate` bytes/s shared by all its streams (serial pacing,
no idle credit, so a kept-alive connection cannot burst later).

Every stream is recorded: connection id, ALPN, range start, bytes, start/end time. So the test reports how many
connections the browser really used, not just how long it took.
Library: python-hyper `h2` (MIT).
"""
import asyncio
import itertools
import re
import ssl
import threading
import time

import h2.config
import h2.connection
import h2.events
import h2.exceptions

CHUNK = 16 * 1024


class _Conn(asyncio.Protocol):
    def __init__(self, server):
        self.srv, self.transport, self.closed = server, None, False
        self.cid = next(server.ids)
        self.conn = h2.connection.H2Connection(h2.config.H2Configuration(client_side=False, header_encoding="utf-8"))
        self.window = None
        self.next_free = 0.0
        self.reset = set()

    # asyncio callbacks
    def connection_made(self, transport):
        self.transport = transport
        sslobj = transport.get_extra_info("ssl_object")
        alpn = sslobj.selected_alpn_protocol() if sslobj else None
        self.window = asyncio.Event()
        with self.srv.lock:
            self.srv.conns[self.cid] = {"t0": time.time(), "alpn": alpn}
        self.conn.initiate_connection()
        self._flush()

    def connection_lost(self, exc):
        self.closed = True
        if self.window:
            self.window.set()
        with self.srv.lock:
            self.srv.conns.get(self.cid, {})["t1"] = time.time()

    def data_received(self, data):
        try:
            events = self.conn.receive_data(data)
        except h2.exceptions.ProtocolError:
            self._flush()
            self.transport.close()
            return
        for ev in events:
            if isinstance(ev, h2.events.RequestReceived):
                asyncio.ensure_future(self._serve(ev.stream_id, dict(ev.headers)))
            elif isinstance(ev, h2.events.WindowUpdated):
                self.window.set()
            elif isinstance(ev, h2.events.StreamReset):
                self.reset.add(ev.stream_id)
                self.window.set()
            elif isinstance(ev, h2.events.ConnectionTerminated):
                self.closed = True
                self.window.set()
        self._flush()

    def _flush(self):
        out = self.conn.data_to_send()
        if out and self.transport and not self.closed:
            self.transport.write(out)

    async def _pace(self, n):
        """Serial pacing per connection: this chunk may leave at max(now, next_free); no credit for idle time."""
        loop = asyncio.get_running_loop()
        now = loop.time()
        start = max(now, self.next_free)
        self.next_free = start + n / self.srv.rate
        if start > now:
            await asyncio.sleep(start - now)

    async def _serve(self, sid, hdr):
        path = hdr.get(":path", "/")
        rec = {"conn": self.cid, "stream": sid, "path": path, "range": hdr.get("range"), "t0": time.time(),
               "t1": None, "bytes": 0, "status": None, "range_start": 0, "rid": None}
        with self.srv.lock:
            self.srv.requests.append(rec)
        try:
            m = re.match(r"^/f/([A-Za-z0-9_-]+)\.zip", path)
            if hdr.get(":method") != "GET" or not m:
                rec["status"] = 404
                self.conn.send_headers(sid, [(":status", "404"), ("content-length", "0")], end_stream=True)
                self._flush()
                return
            rec["rid"] = m.group(1)
            size = len(self.srv.data)
            start, end = 0, size - 1
            r = re.match(r"bytes=(\d+)-(\d*)", hdr.get("range") or "")
            if r:
                start = int(r.group(1))
                end = min(int(r.group(2)), size - 1) if r.group(2) else size - 1
            rec["range_start"], rec["status"] = start, 206 if r else 200
            headers = [(":status", str(rec["status"])), ("content-type", "application/zip"),
                       ("content-length", str(end - start + 1)), ("accept-ranges", "bytes"),
                       ("etag", '"swiftra-h2-24m"'), ("last-modified", "Sat, 17 Oct 2026 00:00:00 GMT"),
                       ("content-disposition", f'attachment; filename="{self.srv.prefix}-{rec["rid"]}.zip"')]
            if r:
                headers.append(("content-range", f"bytes {start}-{end}/{size}"))
            self.conn.send_headers(sid, headers)
            self._flush()
            pos = start
            while pos <= end:
                if self.closed or sid in self.reset:
                    return
                try:
                    win = min(self.conn.local_flow_control_window(sid), self.conn.max_outbound_frame_size)
                except (h2.exceptions.StreamClosedError, KeyError):
                    return
                n = min(CHUNK, end - pos + 1, win)
                if n <= 0:
                    self.window.clear()
                    await self.window.wait()
                    continue
                await self._pace(n)
                if self.closed or sid in self.reset:
                    return
                try:
                    self.conn.send_data(sid, self.srv.data[pos:pos + n])
                except (h2.exceptions.StreamClosedError, h2.exceptions.FlowControlError):
                    return
                self._flush()
                pos += n
                rec["bytes"] += n
            self.conn.end_stream(sid)
            self._flush()
        except h2.exceptions.ProtocolError:
            pass
        finally:
            rec["t1"] = time.time()


class H2DownloadServer:
    def __init__(self, port, cert, key, data, rate, prefix="swiftra-h2"):
        self.port, self.cert, self.key, self.data, self.rate, self.prefix = port, cert, key, data, rate, prefix
        self.requests, self.conns, self.lock, self.ids = [], {}, threading.Lock(), itertools.count(1)
        self.loop, self.ready = None, threading.Event()

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()
        if not self.ready.wait(15):
            raise RuntimeError("h2 server did not start")
        return self

    def _run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(self.cert, self.key)
        ctx.set_alpn_protocols(["h2"])
        ctx.options |= ssl.OP_NO_COMPRESSION
        srv = self.loop.run_until_complete(
            self.loop.create_server(lambda: _Conn(self), "127.0.0.1", self.port, ssl=ctx))
        self.ready.set()
        try:
            self.loop.run_forever()
        finally:
            srv.close()

    def stats(self, rid):
        """Per download: streams, distinct connections (and their ALPN), coverage, seconds."""
        with self.lock:
            recs = [dict(r) for r in self.requests if r["rid"] == rid]
            conns = {c: dict(v) for c, v in self.conns.items()}
        if not recs:
            return {"requests": 0}
        iv = sorted((r["range_start"], r["range_start"] + r["bytes"]) for r in recs if r["bytes"])
        covered, cs, ce = 0, None, None
        for s, e in iv:
            if ce is None or s > ce:
                covered += (ce - cs) if ce is not None else 0
                cs, ce = s, e
            else:
                ce = max(ce, e)
        covered += (ce - cs) if ce is not None else 0
        used = sorted({r["conn"] for r in recs})
        done = [r["t1"] for r in recs if r["t1"]]
        t0 = min(r["t0"] for r in recs)
        size = len(self.data)
        return {"requests": len(recs), "connections": len(used), "alpn": sorted({str(conns.get(c, {}).get("alpn"))
                                                                                 for c in used}),
                "streams_per_conn": {str(c): sum(1 for r in recs if r["conn"] == c) for c in used},
                "ranges": [r["range"] for r in recs][:12], "covered": min(covered, size),
                "complete": covered >= size, "all_closed": len(done) == len(recs),
                "seconds": round(max(done) - t0, 2) if done and len(done) == len(recs) else None}
