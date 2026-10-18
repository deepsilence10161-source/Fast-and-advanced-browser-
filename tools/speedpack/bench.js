// Swiftra CPU benchmark (own code, no third-party suite). Deterministic, offline, ~1-3 s per run.
// Each workload: 1 warm-up + N timed runs; result = median ms per workload and the sum of medians.
(function () {
  'use strict';
  function rng(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }
  let sink = 0, parseRun = 0;
  const W = {
    objects() {   // allocation + polymorphic calls + recursion
      class Leaf { constructor(v) { this.v = v; } sum() { return this.v; } }
      class Node2 { constructor(l, r) { this.l = l; this.r = r; } sum() { return this.l.sum() + this.r.sum(); } }
      const make = (d, v) => d === 0 ? new Leaf(v) : new Node2(make(d - 1, v * 2), make(d - 1, v * 2 + 1));
      let t = 0; for (let i = 0; i < 4; i++) t += make(15, i).sum();
      sink += t;
    },
    json() {
      const r = rng(1), a = [];
      for (let i = 0; i < 15000; i++) a.push({ id: i, name: 'item' + i, price: Math.floor(r() * 1e5) / 100,
        tags: ['a' + (i % 7), 'b' + (i % 11)], ok: (i & 1) === 0, nested: { x: r(), y: [i, i + 1, i + 2] } });
      let n = 0; for (let k = 0; k < 3; k++) { const s = JSON.stringify(a); n += JSON.parse(s).length + s.length; }
      sink += n;
    },
    regex() {
      const r = rng(2), words = ['alpha', 'beta', 'gamma', 'delta', 'user@example.com', '2026-10-18', 'http://x.test/a?b=1'];
      let txt = ''; for (let i = 0; i < 30000; i++) txt += words[Math.floor(r() * words.length)] + (i % 13 ? ' ' : '\n');
      let n = 0;
      for (let k = 0; k < 3; k++) {
        n += (txt.match(/\b[a-z]+@[a-z]+\.[a-z]{2,}\b/g) || []).length;
        n += (txt.match(/\d{4}-\d\d-\d\d/g) || []).length;
        n += txt.replace(/(gam|del)ma?/g, (m, g) => g.toUpperCase()).length;
        n += txt.split(/\s+/).filter(w => /^https?:\/\//.test(w)).length;
      }
      sink += n;
    },
    strings() {
      let s = '', n = 0;
      for (let i = 0; i < 60000; i++) s += String.fromCharCode(97 + (i % 26)) + (i % 100 === 0 ? ',' : '');
      for (let k = 0; k < 20; k++) { n += s.split(',').map(x => x.toUpperCase()).join('|').indexOf('XYZ', k * 100); }
      n += [...s.slice(0, 20000)].reverse().join('').length;
      sink += n;
    },
    numeric() {   // matrix multiply + iterative FFT on typed arrays
      const N = 110, a = new Float64Array(N * N), b = new Float64Array(N * N), c = new Float64Array(N * N), r = rng(3);
      for (let i = 0; i < N * N; i++) { a[i] = r(); b[i] = r(); }
      for (let i = 0; i < N; i++) for (let k = 0; k < N; k++) { const x = a[i * N + k]; for (let j = 0; j < N; j++) c[i * N + j] += x * b[k * N + j]; }
      const M = 1 << 15, re = new Float64Array(M), im = new Float64Array(M);
      for (let i = 0; i < M; i++) re[i] = Math.sin(i * 0.01) + r() * 0.1;
      for (let i = 1, j = 0; i < M; i++) { let bit = M >> 1; for (; j & bit; bit >>= 1) j ^= bit; j ^= bit;
        if (i < j) { let t = re[i]; re[i] = re[j]; re[j] = t; t = im[i]; im[i] = im[j]; im[j] = t; } }
      for (let len = 2; len <= M; len <<= 1) { const ang = -2 * Math.PI / len, wr = Math.cos(ang), wi = Math.sin(ang);
        for (let i = 0; i < M; i += len) { let cr = 1, ci = 0;
          for (let j = 0; j < len / 2; j++) { const ur = re[i + j], ui = im[i + j], k = i + j + len / 2;
            const vr = re[k] * cr - im[k] * ci, vi = re[k] * ci + im[k] * cr;
            re[i + j] = ur + vr; im[i + j] = ui + vi; re[k] = ur - vr; im[k] = ui - vi;
            const ncr = cr * wr - ci * wi; ci = cr * wi + ci * wr; cr = ncr; } } }
      sink += c[N + 1] + re[7];
    },
    sort() {
      const r = rng(4), a = new Array(150000), o = [];
      for (let i = 0; i < a.length; i++) a[i] = Math.floor(r() * 1e9);
      a.sort((x, y) => x - y);
      for (let i = 0; i < 40000; i++) o.push({ k: 'k' + Math.floor(r() * 1e6), v: i });
      o.sort((x, y) => (x.k < y.k ? -1 : x.k > y.k ? 1 : 0));
      sink += a[777] + o[33].v;
    },
    mapset() {
      const m = new Map(), s = new Set(); let n = 0;
      for (let i = 0; i < 150000; i++) { m.set('k' + i, i); s.add(i * 7); }
      for (let i = 0; i < 150000; i++) { n += m.get('k' + ((i * 31) % 150000)) | 0; if (s.has(i)) n++; }
      for (let i = 0; i < 150000; i += 2) { m.delete('k' + i); s.delete(i * 7); }
      sink += n + m.size + s.size;
    },
    hashing() {   // 32-bit integer mixing (murmur-style finaliser) over a typed array
      const u = new Uint32Array(1 << 20); let h = 0x9747b28c;
      for (let i = 0; i < u.length; i++) u[i] = i * 2654435761;
      for (let k = 0; k < 4; k++) for (let i = 0; i < u.length; i++) {
        let x = u[i] ^ h; x = Math.imul(x ^ (x >>> 16), 0x85ebca6b); x = Math.imul(x ^ (x >>> 13), 0xc2b2ae35);
        h = (x ^ (x >>> 16)) >>> 0; }
      sink += h;
    },
    parse() {   // V8 parser + bytecode compiler (C++): unique source each time, so no compile cache hit
      parseRun++; let src = '/*' + parseRun + '*/';
      for (let i = 0; i < 1200; i++) src += 'var f' + i + '=(function(a,b){var x=a*' + i + '+b;if(x>' + i +
        '){for(var j=0;j<3;j++){x+=j*b-(a|0);}}else{x=[a,b,' + i + '].map(function(v){return v+1}).length}' +
        'return {k' + i + ':x,s:"str' + i + '",o:{p:[1,2,3],q:null}};});\n';
      src += 'return f0(2,3).k0+f1199(2,3).k1199;';   // parenthesised = eagerly compiled by V8
      sink += new Function(src)();
    },
    dom() {   // node creation, style, layout, query, removal
      const host = document.createElement('div'); document.body.appendChild(host); let n = 0;
      for (let k = 0; k < 2; k++) {
        const frag = document.createDocumentFragment();
        for (let i = 0; i < 2500; i++) { const d = document.createElement('div'); d.className = 'c' + (i % 10);
          d.textContent = 'row ' + i; d.style.width = (50 + i % 200) + 'px'; frag.appendChild(d); }
        host.appendChild(frag); n += host.offsetHeight;
        host.querySelectorAll('.c3').forEach(e => { e.style.fontWeight = 'bold'; }); n += host.offsetHeight;
        host.textContent = '';
      }
      host.remove(); sink += n;
    },
  };
  function med(xs) { const s = xs.slice().sort((a, b) => a - b); return s[(s.length - 1) >> 1]; }
  window.swiftraBench = function (runs) {
    const out = { runs: runs, ms: {}, total: 0 };
    for (const [name, fn] of Object.entries(W)) {
      fn(); const t = [];
      for (let i = 0; i < runs; i++) { const t0 = performance.now(); fn(); t.push(performance.now() - t0); }
      out.ms[name] = Math.round(med(t) * 10) / 10; out.total += out.ms[name];
    }
    out.total = Math.round(out.total * 10) / 10; out.sink = sink % 1000;
    return out;
  };
})();
