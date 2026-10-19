// Fame vs Game page. Data comes from data/fame.js, written by scripts/export.py.
(function () {
  "use strict";

  const DATA = window.FAME_DATA;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmt = (n) => (n == null ? "—" : n >= 1e6 ? (n / 1e6).toFixed(n >= 1e7 ? 0 : 1) + "M" : n >= 1e3 ? (n / 1e3).toFixed(n >= 1e4 ? 0 : 1) + "K" : String(Math.round(n)));
  const VERDICT_CLASS = { Underrated: "under", Overrated: "over", "Fairly rated": "fair" };
  const THRESHOLD = 25;
  const SIGNALS = [
    { key: "pageviews", label: "Wikipedia views (30 days)", raw: "pageviews_30d", weight: 0.30 },
    { key: "news", label: "News articles (30 days)", raw: "news_articles_30d", weight: 0.25 },
    { key: "instagram", label: "Instagram followers", raw: "instagram_followers", weight: 0.20 },
    { key: "tiktok", label: "TikTok followers", raw: "tiktok_followers", weight: 0.15 },
    { key: "media", label: "Film and TV credits", raw: "media_credits", weight: 0.10 },
  ];
  const DEFAULT_WEIGHTS = Object.fromEntries(SIGNALS.map((s) => [s.key, s.weight]));

  if (!DATA || !DATA.players || !DATA.players.length) {
    $("chart").innerHTML = '<p class="empty-state">The first data refresh hasn\'t run yet. The chart appears after the pipeline\'s first daily run.</p>';
    return;
  }

  const players = DATA.players.map((p) => ({ ...p }));
  let weights = { ...DEFAULT_WEIGHTS };
  try { const saved = JSON.parse(localStorage.getItem("fvg-weights") || "null"); if (saved) weights = { ...weights, ...saved }; } catch (e) { /* ignore */ }
  let selected = null;

  // ---------- scoring (mirrors dbt/models/marts/fct_fame_vs_game.sql) ----------
  function percentRank(values) {
    // DuckDB percent_rank: (rank - 1) / (n - 1), ties share the lowest rank
    const sorted = [...values].sort((a, b) => a - b);
    const first = new Map();
    sorted.forEach((v, i) => { if (!first.has(v)) first.set(v, i); });
    const n = values.length;
    return values.map((v) => (n > 1 ? (100 * first.get(v)) / (n - 1) : 0));
  }

  function rescore() {
    const raw = players.map((p) => {
      let num = 0, den = 0;
      SIGNALS.forEach((s) => {
        const pct = p[s.key + "_pct"];
        if (pct != null && weights[s.key] > 0) { num += weights[s.key] * pct; den += weights[s.key]; }
      });
      return den > 0 ? num / den : 0;
    });
    const ranks = percentRank(raw);
    players.forEach((p, i) => {
      p.fame = Math.round(ranks[i] * 10) / 10;
      p.game = p.production_score;
      p.diff = Math.round((p.game - p.fame) * 10) / 10;
      p.verdictNow = p.diff >= THRESHOLD ? "Underrated" : p.diff <= -THRESHOLD ? "Overrated" : "Fairly rated";
      p.quadNow = p.game >= 50 && p.fame >= 50 ? "Stars" : p.fame >= 50 ? "Hype" : p.game >= 50 ? "Hidden gems" : "Under the radar";
    });
  }

  // ---------- header facts ----------
  function facts() {
    const items = [
      ["Players", players.length],
      ["Data through", DATA.pageviewsThrough ? new Date(DATA.pageviewsThrough + "T12:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "—"],
      ["Social counts", `${DATA.instagramFilled} IG · ${DATA.tiktokFilled} TT`],
    ];
    if ((DATA.newsDays || 0) < 30) items.push(["News window", `${DATA.newsDays || 0} of 30 days`]);
    $("facts").innerHTML = items.map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join("");
  }

  // ---------- filters ----------
  function visible(p) {
    const team = $("team").value;
    const verdicts = [...$("verdicts").querySelectorAll("input:checked")].map((i) => i.value);
    return (!team || p.team === team) && verdicts.includes(p.verdictNow);
  }
  function matchesSearch(p) {
    const q = $("search").value.trim().toLowerCase();
    if (!q) return false;
    const plain = p.player_name.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    return plain.includes(q.normalize("NFD").replace(/[̀-ͯ]/g, ""));
  }

  // ---------- chart ----------
  function drawChart() {
    const box = $("chart");
    const W = Math.max(320, box.clientWidth), H = Math.round(Math.min(W * 0.78, 640));
    const m = { l: 44, r: 14, t: 14, b: 40 };
    const x = (v) => m.l + (v / 100) * (W - m.l - m.r);
    const y = (v) => H - m.b - (v / 100) * (H - m.t - m.b);
    const small = W < 560;
    const r = small ? 4 : 5.5;
    const searching = $("search").value.trim() !== "";

    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Fame score versus game score for ${players.length} players">`;
    // fairness band around the diagonal
    s += `<polygon class="band" points="${x(0)},${y(THRESHOLD)} ${x(100 - THRESHOLD)},${y(100)} ${x(100)},${y(100)} ${x(100)},${y(100 - THRESHOLD)} ${x(THRESHOLD)},${y(0)} ${x(0)},${y(0)}"/>`;
    for (let v = 0; v <= 100; v += 25) {
      s += `<line class="gridline" x1="${x(v)}" x2="${x(v)}" y1="${y(0)}" y2="${y(100)}"/><line class="gridline" x1="${x(0)}" x2="${x(100)}" y1="${y(v)}" y2="${y(v)}"/>`;
      s += `<g class="axis"><text x="${x(v)}" y="${H - m.b + 16}" text-anchor="middle">${v}</text><text x="${m.l - 8}" y="${y(v) + 4}" text-anchor="end">${v}</text></g>`;
    }
    s += `<line class="mid" x1="${x(50)}" x2="${x(50)}" y1="${y(0)}" y2="${y(100)}"/><line class="mid" x1="${x(0)}" x2="${x(100)}" y1="${y(50)}" y2="${y(50)}"/>`;
    s += `<line class="diag" x1="${x(0)}" y1="${y(0)}" x2="${x(100)}" y2="${y(100)}"/>`;
    s += `<g class="axis"><text x="${(x(0) + x(100)) / 2}" y="${H - 6}" text-anchor="middle">GAME (on-court production percentile) →</text>`;
    s += `<text transform="translate(12 ${(y(0) + y(100)) / 2}) rotate(-90)" text-anchor="middle">FAME (attention percentile) →</text></g>`;
    const ql = [["Hype", x(2), y(96), "start"], ["Stars", x(98), y(96), "end"], ["Under the radar", x(2), y(2) - 4, "start"], ["Hidden gems", x(98), y(2) - 4, "end"]];
    ql.forEach(([t, qx, qy, a]) => { s += `<text class="qlabel" x="${qx}" y="${qy}" text-anchor="${a}">${t}</text>`; });

    const order = [...players].sort((a, b) => (visible(a) - visible(b)) || (Math.abs(a.diff) - Math.abs(b.diff)));
    order.forEach((p) => {
      const cls = ["dot", VERDICT_CLASS[p.verdictNow]];
      if (!visible(p) || (searching && !matchesSearch(p))) cls.push("dim");
      if (searching && matchesSearch(p)) cls.push("hit");
      if (selected === p.bref_id) cls.push("sel");
      const rr = selected === p.bref_id || (searching && matchesSearch(p)) ? r + 2.5 : r;
      s += `<circle class="${cls.join(" ")}" data-id="${esc(p.bref_id)}" cx="${x(p.game).toFixed(1)}" cy="${y(p.fame).toFixed(1)}" r="${rr}"/>`;
    });

    // Label the biggest outliers plus anything searched or selected
    const labelled = new Set();
    [...players].filter(visible).sort((a, b) => Math.abs(b.diff) - Math.abs(a.diff)).slice(0, small ? 4 : 8).forEach((p) => labelled.add(p.bref_id));
    players.filter((p) => searching && matchesSearch(p)).slice(0, 6).forEach((p) => labelled.add(p.bref_id));
    if (selected) labelled.add(selected);
    players.filter((p) => labelled.has(p.bref_id)).forEach((p) => {
      const left = p.game > 75;
      s += `<text class="name" x="${x(p.game) + (left ? -9 : 9)}" y="${y(p.fame) + 4}" text-anchor="${left ? "end" : "start"}">${esc(p.player_name)}</text>`;
    });
    s += "</svg>";
    box.innerHTML = s;

    const shown = players.filter(visible).length;
    $("chartNote").textContent = `${shown} of ${players.length} players shown. Dashed diagonal: fame matches game. Shaded band: within ${THRESHOLD} points, fairly rated.`;
  }

  // ---------- tooltip + selection ----------
  const tip = $("tip");
  $("chart").addEventListener("pointermove", (e) => {
    const dot = e.target.closest(".dot");
    if (!dot) { tip.hidden = true; return; }
    const p = players.find((q) => q.bref_id === dot.dataset.id);
    tip.innerHTML = `<b>${esc(p.player_name)}</b> · ${esc(p.team || "")}<br>Game ${p.game.toFixed(0)} · Fame ${p.fame.toFixed(0)} · ${esc(p.verdictNow)}`;
    tip.hidden = false;
    const tx = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
    const ty = e.clientY + 16 + tip.offsetHeight > window.innerHeight ? e.clientY - tip.offsetHeight - 10 : e.clientY + 16;
    tip.style.left = tx + "px";
    tip.style.top = ty + "px";
  });
  $("chart").addEventListener("pointerleave", () => { tip.hidden = true; });
  $("chart").addEventListener("click", (e) => {
    const dot = e.target.closest(".dot");
    if (dot) select(dot.dataset.id);
  });

  function select(id) {
    selected = id;
    drawChart();
    drawDetail();
    if (window.matchMedia("(max-width: 900px)").matches) $("detail").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function bar(label, value, pct, cls = "") {
    if (pct == null) return `<li><span>${label}</span><span class="val missing">not available</span></li>`;
    return `<li><span>${label}</span><span class="val">${value}</span><span class="bar ${cls}"><i style="width:${pct}%"></i></span></li>`;
  }

  function drawDetail() {
    const p = players.find((q) => q.bref_id === selected);
    if (!p) {
      const top = [...players].sort((a, b) => b.diff - a.diff)[0];
      $("detail").innerHTML = `<p class="empty">Click any dot, or a name in the lists below, to see why that player lands where they do.</p>
        <p class="empty">Right now the most underrated player is <b>${esc(top.player_name)}</b>: better on the court than ${top.game.toFixed(0)}% of the league, but more famous than only ${top.fame.toFixed(0)}%.</p>`;
      return;
    }
    const links = [];
    if (p.wikipedia_title) links.push(`<a href="https://en.wikipedia.org/wiki/${encodeURIComponent(p.wikipedia_title)}" target="_blank" rel="noopener">Wikipedia</a>`);
    if (p.instagram_handle) links.push(`<a href="https://www.instagram.com/${encodeURIComponent(p.instagram_handle)}/" target="_blank" rel="noopener">Instagram</a>`);
    if (p.tiktok_handle) links.push(`<a href="https://www.tiktok.com/@${encodeURIComponent(p.tiktok_handle)}" target="_blank" rel="noopener">TikTok</a>`);
    links.push(`<a href="https://www.basketball-reference.com/players/${p.bref_id[0]}/${encodeURIComponent(p.bref_id)}.html" target="_blank" rel="noopener">Stats</a>`);
    const sign = p.diff > 0 ? "+" : "";
    $("detail").innerHTML = `
      <div class="who"><h2>${esc(p.player_name)}</h2>
        <div class="meta">${esc(p.team || "")}${p.position ? " · " + esc(p.position) : ""}${p.age ? " · age " + Math.round(p.age) : ""}</div>
        <span class="verdict ${VERDICT_CLASS[p.verdictNow]}">${esc(p.verdictNow)} · ${esc(p.quadNow)}</span></div>
      <div class="scores"><div><b>${p.game.toFixed(0)}</b><span>Game</span></div><div><b>${p.fame.toFixed(0)}</b><span>Fame</span></div><div><b>${sign}${p.diff.toFixed(0)}</b><span>Gap</span></div></div>
      <div><h3>Fame signals</h3><ul class="signals">
        ${SIGNALS.map((s) => bar(s.label, fmt(p[s.raw]), p[s.key + "_pct"])).join("")}
      </ul></div>
      <div><h3>On the court</h3><ul class="signals">
        ${bar("Box Plus/Minus", p.bpm == null ? "—" : (p.bpm > 0 ? "+" : "") + p.bpm.toFixed(1), Math.max(0, Math.min(100, (p.bpm + 6) * 100 / 16)), "game")}
        ${bar("VORP", p.vorp == null ? "—" : p.vorp.toFixed(1), Math.max(0, Math.min(100, p.vorp * 100 / 8)), "game")}
        <li><span>2026–27 share of score</span><span class="val">${Math.round((p.cur_season_weight || 0) * 100)}%</span></li>
      </ul></div>
      <div class="links">${links.join("")}</div>`;
  }

  // ---------- ranked lists ----------
  function drawLists() {
    const pool = players.filter((p) => !$("team").value || p.team === $("team").value);
    const li = (p) => `<li><button type="button" data-id="${esc(p.bref_id)}">${esc(p.player_name)}<span class="team">${esc(p.team || "")}</span></button><span class="gap">${p.diff > 0 ? "+" : ""}${p.diff.toFixed(0)}</span></li>`;
    $("underList").innerHTML = [...pool].sort((a, b) => b.diff - a.diff).slice(0, 10).map(li).join("");
    $("overList").innerHTML = [...pool].sort((a, b) => a.diff - b.diff).slice(0, 10).map(li).join("");
  }
  document.querySelector(".lists").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-id]");
    if (b) select(b.dataset.id);
  });

  // ---------- weights ----------
  function buildWeights() {
    $("weights").innerHTML = SIGNALS.map((s) => `<div class="field"><label for="w-${s.key}">${s.label}: <span id="wv-${s.key}">${Math.round(weights[s.key] * 100)}</span></label>
      <input type="range" id="w-${s.key}" data-key="${s.key}" min="0" max="50" step="1" value="${Math.round(weights[s.key] * 100)}"></div>`).join("");
    $("weights").querySelectorAll("input").forEach((inp) => inp.addEventListener("input", (e) => {
      weights[e.target.dataset.key] = +e.target.value / 100;
      $("wv-" + e.target.dataset.key).textContent = e.target.value;
      try { localStorage.setItem("fvg-weights", JSON.stringify(weights)); } catch (err) { /* ignore */ }
      refresh();
    }));
  }
  $("resetWeights").addEventListener("click", () => {
    weights = { ...DEFAULT_WEIGHTS };
    try { localStorage.removeItem("fvg-weights"); } catch (err) { /* ignore */ }
    buildWeights();
    refresh();
  });

  // ---------- wiring ----------
  function refresh() { rescore(); drawChart(); drawLists(); drawDetail(); }
  const teams = [...new Set(players.map((p) => p.team).filter(Boolean))].sort();
  $("team").insertAdjacentHTML("beforeend", teams.map((t) => `<option>${esc(t)}</option>`).join(""));
  ["team", "search"].forEach((id) => $(id).addEventListener("input", () => { drawChart(); drawLists(); }));
  $("verdicts").addEventListener("change", drawChart);
  $("search").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { const hit = players.find(matchesSearch); if (hit) select(hit.bref_id); }
  });
  let resizeTimer;
  window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(drawChart, 120); });

  facts();
  buildWeights();
  refresh();
})();
