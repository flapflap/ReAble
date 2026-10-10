/* ReAble — interface. Aucune dépendance. Tout texte dynamique passe par textContent (jamais innerHTML). */
(() => {
  "use strict";
  const TOKEN = document.querySelector('meta[name="reable-token"]').content;
  const root = document.getElementById("app");
  root.className = "pr";

  /* ---------- utilitaires ---------- */
  const ICON = {
    ok: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    warn: '<path d="M12 4a8 8 0 1 0 0 16z"/><circle cx="12" cy="12" r="8"/>',
    err: '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17.2v.1"/>',
    neu: '<circle cx="12" cy="12" r="8"/>',
    run: '<path d="M12 3a9 9 0 1 0 9 9"/>',
    folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    list: '<path d="M4 6h16M4 12h16M4 18h10"/>',
    play: '<path d="M7 5l12 7-12 7z"/>',
    box: '<path d="M12 3l8 4v10l-8 4-8-4V7z"/><path d="M4 7l8 4 8-4M12 11v10"/>',
    shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M8.5 12l2.5 2.5L15.5 10"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8v.1"/>',
    updown: '<path d="M7 10l5-5 5 5M7 14l5 5 5-5"/>',
  };
  function icon(name, cls = "", size = 14) {
    const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("viewBox", "0 0 24 24");
    s.setAttribute("fill", "none");
    s.setAttribute("stroke", "currentColor");
    s.setAttribute("stroke-width", name === "ok" ? "2.6" : "2");
    s.setAttribute("stroke-linecap", "round");
    s.setAttribute("stroke-linejoin", "round");
    s.setAttribute("aria-hidden", "true");
    s.setAttribute("width", size);
    s.setAttribute("height", size);
    if (cls) s.setAttribute("class", cls);
    s.innerHTML = ICON[name]; // constantes internes uniquement
    return s;
  }
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else if (k === "disabled" || k === "checked") el[k] = !!v;
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const k of kids.flat()) {
      if (k === null || k === undefined || k === false) continue;
      el.append(k instanceof Node ? k : document.createTextNode(String(k)));
    }
    return el;
  }
  async function api(path, body) {
    const opt = { headers: { "X-ReAble-Token": TOKEN, "Content-Type": "application/json" } };
    if (body !== undefined) { opt.method = "POST"; opt.body = JSON.stringify(body); }
    const r = await fetch(path, opt);
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || `Erreur ${r.status}`);
    return data;
  }
  const fmtTime = (s) => {
    if (s === null || s === undefined || !isFinite(s)) return "—";
    s = Math.round(s);
    const m = Math.floor(s / 60), r = s % 60;
    return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
  };
  const fmtEta = (s) => {
    if (s === null || s === undefined || !isFinite(s)) return "calcul en cours";
    if (s < 60) return `${Math.max(1, Math.round(s))} s`;
    const m = Math.floor(s / 60), r = Math.round(s % 60);
    return `${m} min ${String(r).padStart(2, "0")}`;
  };
  const plural = (n, one, many) => `${n} ${n > 1 ? many : one}`;
  const shortPath = (p) => (p || "").replace(/^\/Users\/[^/]+/, "~");
  const baseName = (p) => (p || "").split("/").pop().replace(/\.als$/, "");

  /* ---------- état de l'interface ---------- */
  const S = {
    view: "choose", // choose | analyzing | understand | running | summary | stopped | empty | error | plugins
    server: null, // /api/state
    path: "",
    selected: new Set(),
    expanded: new Set(),
    job: null, // { id, kind, since, events, last, state }
    log: [], // lignes du journal
    rows: [], // projets traités (liste de suivi)
    logFilter: "all",
    stopping: false,
    error: null,
    toast: null,
    plugins: null,
    lastKind: null,
    summary: null,
  };
  let poll = null;

  function toast(msg) {
    S.toast = msg;
    render();
    setTimeout(() => { if (S.toast === msg) { S.toast = null; render(); } }, 4000);
  }

  /* ---------- tâches ---------- */
  function startPolling(jobId, kind) {
    S.job = { id: jobId, kind, since: 0, last: null, state: "running" };
    S.log = []; S.rows = []; S.stopping = false;
    clearInterval(poll);
    poll = setInterval(tick, 350);
    tick();
  }
  async function tick() {
    if (!S.job) return;
    let snap;
    try { snap = await api(`/api/jobs/${S.job.id}?since=${S.job.since}`); } catch (e) { return; }
    S.job.since = snap.total_events;
    S.job.state = snap.state;
    if (snap.last) S.job.last = snap.last;
    for (const e of snap.events) absorb(e);
    if (snap.state !== "running" && snap.state !== "stopping") {
      clearInterval(poll);
      await finishJob(snap);
    }
    render();
  }
  function absorb(e) {
    const t = new Date().toLocaleTimeString("fr-FR");
    if (e.status === "error") { S.log.push({ t, kind: "err", text: e.message }); return; }
    if (e.result) {
      const done = e.result === "converti" || e.result === "lu";
      const warn = e.result === "réglages par défaut";
      const txt = `${e.item} · ${e.result}${e.message ? " · " + e.message : ""}`;
      S.log.push({ t, kind: e.result === "erreur" ? "err" : warn ? "warn" : "ok", text: txt });
      if (S.job.kind === "convert" || S.job.kind === "plan") {
        const row = S.rows.find((r) => r.name === e.item);
        if (row) { row.result = e.result; row.path = e.path || row.path; } else S.rows.push({ name: e.item, result: e.result, path: e.path });
      }
    } else if (e.item && e.phase) {
      const last = S.log[S.log.length - 1];
      const txt = `${e.item} · ${e.phase}`;
      if (!last || last.text !== txt) S.log.push({ t, kind: "", text: txt });
      if ((S.job.kind === "convert" || S.job.kind === "plan") && !S.rows.find((r) => r.name === e.item)) S.rows.push({ name: e.item, result: "", path: "" });
    }
    if (S.log.length > 600) S.log.splice(0, 100);
  }
  async function finishJob(snap) {
    const kind = S.job.kind;
    S.lastKind = kind;
    try { S.server = await api("/api/state"); } catch (e) { /* garde l'ancien état */ }
    if (snap.state === "error") { S.error = snap.error || "Erreur inconnue"; S.view = "error"; return; }
    if (kind === "analyze") {
      if (snap.state === "stopped") { S.view = "choose"; toast("Analyse arrêtée."); return; }
      const sm = S.server.summary;
      S.selected = new Set(S.server.groups.filter((g) => g.selectable).map((g) => g.id));
      S.view = !sm || (sm.to_convert === 0) ? "empty" : "understand";
    } else if (kind === "convert" || kind === "plan") {
      S.summary = { state: snap.state, result: snap.result, kind, last: S.job.last };
      S.view = snap.state === "stopped" ? "stopped" : "summary";
      if (kind === "plan" && snap.state === "done") { S.view = "understand"; toast("Essai à blanc terminé : rien n'a été écrit."); }
    }
  }
  async function startAnalyze() {
    S.error = null;
    try {
      const r = await api("/api/analyze", { path: S.path });
      S.view = "analyzing";
      startPolling(r.job, "analyze");
    } catch (e) { S.error = e.message; S.view = "error"; render(); }
  }
  async function startConvert(dry) {
    try {
      const r = await api("/api/convert", { groups: [...S.selected], dry_run: !!dry });
      S.view = "running";
      startPolling(r.job, dry ? "plan" : "convert");
    } catch (e) { toast(e.message); }
  }
  async function stopJob() {
    if (!S.job || S.stopping) return;
    S.stopping = true; render();
    try { await api(`/api/jobs/${S.job.id}/stop`, {}); } catch (e) { /* tick reprendra l'état réel */ }
  }
  async function pickFolder() {
    const native = window.pywebview && window.pywebview.api && window.pywebview.api.choose_folder;
    const path = native ? await window.pywebview.api.choose_folder() : (await api("/api/choose-folder", {})).path;
    if (path) { S.path = path; render(); }
  }
  /* Glisser-déposer d'un dossier : le chemin n'est disponible que dans la fenêtre native (pywebviewFullPath). */
  function dropHandlers(el) {
    el.addEventListener("dragover", (e) => { e.preventDefault(); el.classList.add("over"); });
    el.addEventListener("dragleave", () => el.classList.remove("over"));
    el.addEventListener("drop", (e) => {
      e.preventDefault(); el.classList.remove("over");
      const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      const p = f && f.pywebviewFullPath;
      if (p) { S.path = p; startAnalyze(); } else toast("Déposez le dossier dans la fenêtre ReAble, ou utilisez « Choisir… ».");
    });
    return el;
  }
  async function saveOption(patch) {
    try { S.server = await api("/api/options", patch); } catch (e) { toast(e.message); }
    render();
  }
  async function undoAll() {
    const files = (S.summary && S.summary.result && S.summary.result.written) || S.rows.filter((r) => r.path).map((r) => r.path);
    if (!files.length) { toast("Aucune copie à annuler."); return; }
    if (!confirm(`Mettre ${plural(files.length, "copie", "copies")} à la corbeille ?\nVos projets d'origine ne sont pas touchés.`)) return;
    const r = await api("/api/undo", { files });
    toast(`${plural(r.moved.length, "copie mise", "copies mises")} à la corbeille.`);
    S.view = "choose"; S.server = await api("/api/state");
    render();
  }
  async function copyOldList() {
    const r = await api("/api/old-sets");
    try { await navigator.clipboard.writeText(r.sets.join("\n")); toast(`Liste copiée : ${plural(r.sets.length, "projet", "projets")}.`); }
    catch (e) { toast("Copie impossible : autorisation refusée."); }
  }

  /* ---------- briques ---------- */
  function stateBadge(kind, text) {
    const map = { ok: ["ok", "s-ok"], warn: ["warn", "s-warn"], err: ["err", "s-error"], neu: ["neu", "s-neutral"], run: ["run", "s-accent"] };
    const [ic, cls] = map[kind];
    return h("span", { class: "state " + cls }, icon(ic, kind === "run" ? "spin" : ""), text);
  }
  function btn(label, onclick, cls = "btn", extra = {}) { return h("button", { type: "button", class: cls, onclick, ...extra }, label); }
  function nav(label, ic, active, enabled, onclick, right) {
    return h("div", { class: "nav" + (active ? " on" : "") + (enabled && !active ? " click" : !enabled ? " off" : ""), role: "button", tabindex: enabled ? "0" : "-1",
      "aria-current": active ? "page" : null, onclick: enabled ? onclick : null,
      onkeydown: enabled ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onclick(); } } : null }, icon(ic, "", 16), label, h("span", { class: "st" }, right || ""));
  }
  const busy = () => S.view === "analyzing" || S.view === "running";

  function sidebar() {
    const sv = S.server, analyzed = sv && sv.analyzed;
    const step = { choose: 0, analyzing: 0, error: 0, understand: 1, empty: 1, running: 2, summary: 2, stopped: 2 }[S.view];
    return h("nav", { class: "sidebar", "aria-label": "Étapes" },
      h("h3", {}, "Étapes"),
      nav("1 · Choisir", "folder", step === 0 && S.view !== "plugins", !busy(), () => { S.view = "choose"; render(); }, sv && sv.folder ? baseName(sv.folder) : ""),
      nav("2 · Comprendre", "list", step === 1 && S.view !== "plugins", !busy() && analyzed, () => { S.view = sv.summary && sv.summary.to_convert ? "understand" : "empty"; render(); }),
      nav("3 · Convertir", "play", step === 2 && S.view !== "plugins", false, () => {}),
      h("h3", { style: "margin-top:12px" }, "Bibliothèque"),
      nav("Plugins", "box", S.view === "plugins", !busy(), openPlugins, S.plugins ? String(S.plugins.length) : ""),
      h("div", { class: "safe" }, icon("shield", "", 16), h("span", {}, "Vos projets d’origine ne sont jamais modifiés. Les copies portent [ReAble].")));
  }
  async function openPlugins() {
    try { S.plugins = await api("/api/plugins"); } catch (e) { S.plugins = []; }
    S.prevView = S.view === "plugins" ? S.prevView : S.view;
    S.view = "plugins"; render();
  }
  function titlebar(sub, ...tools) {
    return h("div", { class: "titlebar" }, h("div", { class: "ttl" }, h("b", {}, "ReAble"), h("span", {}, sub)), h("div", { class: "tools" }, ...tools));
  }
  function status(left, right) { return h("div", { class: "status" }, h("span", { class: "grow" }, left), right ? h("span", {}, right) : null); }
  /* Le bouton Arrêter est un élément unique, créé une fois et mis à jour sur place : l'interface se redessine plusieurs fois
     par seconde pendant une tâche, et un bouton recréé à chaque fois ferait perdre les clics tombés entre deux redessins. */
  const stopEl = h("button", { type: "button", class: "btn btn-stop", onclick: () => stopJob() });
  function stopButton() {
    stopEl.disabled = S.stopping;
    stopEl.replaceChildren(...(S.stopping ? ["Arrêt en cours…"] : [h("i"), "Arrêter"]));
    return stopEl;
  }
  function frame(sub, tools, content, statusEl, inspector) {
    return [titlebar(sub, ...tools), h("div", { class: "wrap" }, sidebar(), h("section", { class: "content", "aria-label": sub }, content), inspector || null), statusEl,
      S.toast ? h("div", { class: "toast", role: "status" }, S.toast) : null];
  }

  /* ---------- vues ---------- */
  function noDefs() {
    return S.server && S.server.definitions === 0
      ? h("div", { class: "hint" }, icon("err", "", 16), h("div", {}, h("b", {}, "Aucune définition de plugin n’est chargée. "), "Sans elles, ReAble ne sait convertir aucun plugin. Synchronisez-les avec la commande « reable plugins sync », puis relancez l’application."))
      : null;
  }
  function viewChoose() {
    const input = h("input", { type: "text", value: S.path, placeholder: "~/Music", "aria-label": "Dossier de projets", oninput: (e) => { S.path = e.target.value; update(); } });
    const go = btn("Analyser", startAnalyze, "btn btn-primary", { disabled: !S.path.trim() });
    function update() { go.disabled = !S.path.trim(); }
    return frame("Aucun dossier choisi", [go],
      [noDefs(), dropHandlers(h("div", { class: "drop" }, icon("folder", "", 44), h("h2", {}, "Quel dossier de projets analyser ?"),
        h("p", {}, "Glissez un dossier ici, ou choisissez-le. ReAble y cherche les projets Ableton Live (.als) et repère les plugins qui manquent sur ce Mac."),
        h("div", { class: "pathrow" }, h("div", { class: "input" }, input), btn("Choisir…", pickFolder))))],
      status("Aucun projet analysé.", "Rien n’est modifié pendant l’analyse."));
  }
  function progressBlock(label, total) {
    const l = S.job && S.job.last, n = l ? l.index : 0, tot = l ? l.total : total || 0;
    if (l && l.task === "plan" && S.job.kind === "analyze") label = "projets vérifiés";
    const pct = tot ? Math.round((n / tot) * 100) : 0;
    const phases = ["lecture", "conversion", "contrôle", "écriture"];
    const cur = l && l.phase ? phases.indexOf(l.phase) : -1;
    const searching = !tot;
    return h("div", { class: "prog" },
      h("div", { class: "row" }, h("b", {}, searching ? "Recherche des projets…" : `${n} / ${tot} ${label}`), h("span", {}, "Écoulé ", h("b", {}, fmtTime(l ? l.elapsed : 0)), " · reste environ ", h("b", {}, fmtEta(l ? l.eta : null)))),
      h("div", { class: "bar", role: "progressbar", "aria-valuemin": "0", "aria-valuemax": String(tot), "aria-valuenow": String(n), "aria-label": "Progression" }, h("i", { style: `width:${pct}%` })),
      h("div", { class: "phase", "aria-live": "polite" }, h("span", {}, l && l.item ? `${l.item} :` : "Préparation…"),
        phases.map((p, i) => h("em", { class: i < cur ? "d" : i === cur ? "n" : "" }, p[0].toUpperCase() + p.slice(1)))));
  }
  function viewAnalyzing() {
    const l = S.job && S.job.last;
    return frame(shortPath(S.path), [stopButton()],
      [progressBlock("projets lus", 0), h("div", { class: "center" }, h("h2", {}, l && l.task === "plan" ? "Vérification de ce qui peut être converti…" : "Analyse en cours…"),
        h("p", {}, l && l.task === "plan" ? "ReAble simule chaque conversion, sans rien écrire. Vous pouvez arrêter à tout moment." : "ReAble lit chaque projet sans le modifier. Vous pouvez arrêter à tout moment."))],
      status(h("span", {}, h("b", {}, l ? l.index : 0), l && l.task === "plan" ? " vérifiés" : " lus"), "L’analyse est en lecture seule."));
  }
  function groupRow(g) {
    const sel = S.selected.has(g.id);
    const open = S.expanded.has(g.id);
    const stateEl = { validated: stateBadge("ok", "Validé"), default: stateBadge("warn", "Réglages par défaut"), old: stateBadge("err", "Action requise"),
      unsupported: stateBadge("neu", "Non pris en charge"), done: stateBadge("ok", "Déjà fait") }[g.kind];
    const detail = { validated: g.kind === "validated" && /Kontakt|Massive|FM8|Absynth|Battery/.test(g.title) ? "La piste est dupliquée : l’originale reste, en sourdine." : "Vos réglages seront repris.",
      default: "Le plugin cible ne lit pas les réglages de l’ancienne version : réglages par défaut, l’ancien preset est noté sur la piste.",
      old: "À ouvrir et enregistrer dans Live 12, puis réanalyser.", unsupported: g.plugins.slice(0, 6).join(", ") + (g.plugins.length > 6 ? "…" : "") + " — ReAble ne sait pas encore les convertir.",
      done: "Les copies existent déjà ; elles ne seront pas refaites." }[g.kind];
    const act = g.kind === "old" ? btnLink("Copier la liste", copyOldList) : btnLink(open ? "Masquer" : g.kind === "unsupported" ? "Voir lesquels" : "Voir les projets", () => { open ? S.expanded.delete(g.id) : S.expanded.add(g.id); render(); });
    const cb = g.selectable ? h("input", { type: "checkbox", checked: sel, "aria-label": `Convertir ${g.title}`, onchange: (e) => { e.target.checked ? S.selected.add(g.id) : S.selected.delete(g.id); render(); } }) : null;
    const rows = [h("tr", {}, h("td", { class: "chk" }, cb), h("td", {}, stateEl),
      h("td", {}, h("strong", {}, g.title), h("span", { class: "sub" }, detail)), h("td", { class: "n" }, g.count), h("td", {}, act))];
    if (open) rows.push(h("tr", { class: "sub" }, h("td"), h("td", { colspan: 4 }, h("div", { class: "names" }, (g.kind === "unsupported" ? g.plugins : g.sets.map(baseName)).map((n) => h("span", {}, n))))));
    return rows;
  }
  function btnLink(label, fn) { return h("a", { href: "#", class: "link", onclick: (e) => { e.preventDefault(); fn(); } }, label); }
  function inspector(locked) {
    const o = S.server.options;
    const sample = (o.rename_template || "").replace("{track}", "Lead").replace("{from}", "VST2").replace("{to}", "VST3").replace("{plugin}", "Ozone 10").replace("{preset}", "Abstract City").replace("{date}", "2026-10-09");
    const sel = (value, choices, onchange) => h("div", { class: "pop" }, h("select", { "aria-label": "", disabled: locked, onchange: (e) => onchange(e.target.value) },
      choices.map(([v, l]) => h("option", { value: v, selected: v === value }, l))), icon("updown", "", 12));
    const field = (label, ...kids) => h("div", { class: "field" }, h("label", {}, label), ...kids);
    return h("aside", { class: "inspector" + (locked ? " lock" : ""), "aria-label": "Réglages" }, h("h3", {}, locked ? "Réglages · verrouillés" : "Réglages"),
      field("Piste d’origine", sel(o.replace_mode, [["duplicate_track", "Dupliquer la piste"], ["replace", "Remplacer sur place"]], (v) => saveOption({ replace_mode: v }))),
      field("Nom des pistes converties", h("div", { class: "input" }, h("input", { type: "text", value: o.rename_template, disabled: locked, "aria-label": "Modèle de nom",
        onchange: (e) => saveOption({ rename_template: e.target.value }) })),
        h("div", { class: "pv" }, h("span", {}, "Aperçu"), h("span", { class: "mono" }, `Lead → ${sample}`))),
      h("label", { class: "check" }, h("input", { type: "checkbox", checked: o.track_info, disabled: locked, onchange: (e) => saveOption({ track_info: e.target.checked }) }), "Écrire un texte d’information sur la piste"),
      field("Où écrire les copies", sel(o.out_dir ? "other" : "beside", [["beside", "À côté des originaux"], ["other", o.out_dir ? shortPath(o.out_dir) : "Dans un autre dossier…"]], async (v) => {
        if (v === "beside") return saveOption({ out_dir: null });
        const r = await api("/api/choose-folder", {}); if (r.path) saveOption({ out_dir: r.path }); else render();
      })),
      field("Si la copie existe déjà", sel(o.if_exists, [["skip", "Ne pas la refaire"], ["overwrite", "La remplacer"], ["number", "Numéroter"]], (v) => saveOption({ if_exists: v }))));
  }
  function viewUnderstand() {
    const sv = S.server, sm = sv.summary, groups = sv.groups;
    const selCount = new Set(groups.filter((g) => g.selectable && S.selected.has(g.id)).flatMap((g) => g.sets)).size;
    const sumItem = (ic, n, text) => h("span", {}, icon(ic, "", 14), h("b", {}, n), " " + text);
    return frame(`${baseName(sv.folder)} · ${plural(sv.sets, "projet analysé", "projets analysés")}`,
      [btn("Réanalyser", () => { S.path = sv.folder; startAnalyze(); }), btn("Essai à blanc", () => startConvert(true), "btn", { disabled: !selCount }),
        btn(`Convertir ${plural(selCount, "projet", "projets")}`, () => startConvert(false), "btn btn-primary", { disabled: !selCount })],
      [h("div", { class: "sumbar" }, sumItem("ok", sm.to_convert, "projets seront convertis"), sumItem("err", sm.too_old, "trop anciens (à ouvrir dans Live 12)"), sumItem("neu", sm.unsupported_plugins, "plugins sans équivalent")),
        h("table", {}, h("thead", {}, h("tr", {}, h("th"), h("th", { style: "width:170px" }, "État"), h("th", {}, "Conversion"), h("th", { style: "text-align:right" }, "Projets"), h("th", { style: "width:140px" }))),
          h("tbody", {}, groups.flatMap(groupRow)))],
      status(h("span", {}, h("b", {}, selCount), " projets sélectionnés"), "Rien n’est écrit tant que vous ne cliquez pas sur Convertir."), inspector(false));
  }
  function viewEmpty() {
    const sv = S.server, sm = sv.summary || {};
    const done = sm.already_done || 0, old = sm.too_old || 0, unsup = sm.unsupported_plugins || 0;
    const title = done ? "Tout est déjà converti" : "Rien à convertir pour le moment";
    const reasons = [];
    if (done) reasons.push(`${plural(done, "projet a", "projets ont")} déjà ${done > 1 ? "leur" : "sa"} copie [ReAble] : rien n’est refait.`);
    if (old) reasons.push(`${plural(old, "projet est", "projets sont")} trop ancien${old > 1 ? "s" : ""} : ouvrez-${old > 1 ? "les" : "le"} dans Live 12, enregistrez-${old > 1 ? "les" : "le"}, puis réanalysez.`);
    if (unsup) reasons.push(`${plural(unsup, "plugin n’a", "plugins n’ont")} pas d’équivalent connu : ReAble ne sait pas encore ${unsup > 1 ? "les" : "le"} convertir.`);
    if (!reasons.length) reasons.push("Aucun projet de ce dossier ne contient de plugin manquant que ReAble sait remplacer.");
    return frame(`${baseName(sv.folder)} · ${plural(sv.sets, "projet analysé", "projets analysés")}`, [btn("Réanalyser", () => { S.path = sv.folder; startAnalyze(); })],
      [noDefs(), h("div", { class: "center" }, icon("ok", "big", 48), h("h2", {}, title), reasons.map((r) => h("p", {}, r)),
        h("div", { class: "row" }, btn("Voir les plugins", openPlugins)))],
      status(h("span", {}, plural(sv.sets, "projet analysé", "projets analysés"), " · ", h("b", {}, 0), " à convertir.")));
  }
  function resultRow(r, i) {
    const k = r.result;
    const st = !k ? stateBadge("run", "En cours") : k === "converti" ? stateBadge("ok", "Converti") : k === "réglages par défaut" ? stateBadge("warn", "Réglages par défaut") : k === "erreur" ? stateBadge("err", "Erreur") : stateBadge("neu", "Ignoré");
    return h("tr", { class: !k ? "sel" : "" }, h("td", { style: "width:170px" }, st), h("td", {}, h("strong", {}, r.name)));
  }
  function viewRunning() {
    const l = S.job && S.job.last;
    const dry = S.job && S.job.kind === "plan";
    const counts = { c: 0, d: 0, i: 0, e: 0 };
    for (const r of S.rows) { if (r.result === "converti") counts.c++; else if (r.result === "réglages par défaut") counts.d++; else if (r.result === "erreur") counts.e++; else if (r.result === "ignoré") counts.i++; }
    const log = S.log.filter((x) => S.logFilter === "all" || (S.logFilter === "warn" && (x.kind === "warn" || x.kind === "err")) || (S.logFilter === "err" && x.kind === "err")).slice(-120);
    const seg = (id, label) => h("span", { class: S.logFilter === id ? "on" : "", role: "button", tabindex: "0", onclick: () => { S.logFilter = id; render(); } }, label);
    return frame(`${dry ? "Essai à blanc" : "Conversion en cours"} · ${baseName(S.server.folder)}`, [stopButton()],
      [progressBlock("projets", S.job ? S.job.total : 0),
        h("div", { class: "list" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", { style: "width:170px" }, "État"), h("th", {}, "Projet"))), h("tbody", {}, S.rows.slice(-60).map(resultRow)))),
        h("div", { class: "logpane" }, h("header", {}, "Journal", h("span", { class: "seg", role: "group", "aria-label": "Filtre du journal" }, seg("all", "Tout"), seg("warn", "Avertissements"), seg("err", "Erreurs"))),
          h("div", { class: "log", role: "log", "aria-label": "Journal" }, log.map((x) => h("div", {}, h("time", {}, x.t), h("span", { class: x.kind === "ok" ? "ok" : "" }, x.text)))))],
      status(h("span", {}, h("b", {}, counts.c), " convertis · ", h("b", {}, counts.d), " en réglages par défaut · ", h("b", {}, counts.i), " ignorés · ", h("b", {}, counts.e), " erreurs"),
        S.stopping ? "Arrêt en cours : le projet en cours est abandonné proprement." : "Vous pouvez arrêter à tout moment : le projet en cours est abandonné proprement."), inspector(true));
  }
  function viewSummary() {
    const res = (S.summary && S.summary.result) || {}, written = res.written || [];
    const c = res.counts || {};
    const rows = written.slice(0, 200).map((p) => h("tr", {}, h("td", {}, baseName(p)), h("td", {}, shortPath(p.replace(/\/[^/]*$/, ""))), h("td", {}, btnLink("Afficher dans le Finder", () => api("/api/reveal", { path: p })))));
    return frame("Conversion terminée", [btn("Ouvrir le dossier", () => written[0] && api("/api/reveal", { path: written[0] }), "btn", { disabled: !written.length }),
        btn("Copier la liste", async () => { await navigator.clipboard.writeText(written.join("\n")); toast("Liste copiée."); }, "btn", { disabled: !written.length }),
        btn("Annuler cette conversion", undoAll, "btn", { disabled: !written.length })],
      [h("div", { class: "summary" }, h("h2", {}, `Conversion terminée : ${plural(written.length, "projet converti", "projets convertis")}, ${plural(c.errors || 0, "erreur", "erreurs")}`),
          h("p", {}, "Les copies sont à côté des originaux, avec [ReAble] dans leur nom. Vos originaux n’ont pas été modifiés.")),
        h("div", { class: "hint" }, icon("info", "", 16), h("div", {}, h("b", {}, "Que vérifier dans Live ? "), "Ouvrez une copie : les pistes dupliquées chargent leur instrument, l’originale est en sourdine ; le nouveau plugin d’effet est placé avant l’ancien, désactivé.")),
        h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Copie créée"), h("th", {}, "Dossier"), h("th", { style: "width:170px" }))), h("tbody", {}, rows))],
      status(h("span", {}, h("b", {}, c.converted || 0), " convertis · ", h("b", {}, c.default || 0), " en réglages par défaut · ", h("b", {}, c.skipped || 0), " ignorés · ", h("b", {}, c.errors || 0), " erreurs"),
        S.job && S.job.last ? `Durée : ${fmtTime(S.job.last.elapsed)}` : ""));
  }
  function viewStopped() {
    const l = S.summary.last || {}, done = l.index || 0, total = l.total || 0, left = Math.max(0, total - done);
    const files = S.rows.filter((r) => r.path).map((r) => r.path);
    return frame("Conversion arrêtée", [btn("Annuler ce qui a été fait", undoAll, "btn", { disabled: !files.length }), btn("Reprendre", () => startConvert(false), "btn btn-primary")],
      [h("div", { class: "summary" }, h("h2", {}, `Arrêté : ${plural(done, "projet fait", "projets faits")}, ${plural(left, "non traité", "non traités")}`),
          h("p", {}, `Le projet qui était en cours a été abandonné proprement : aucun fichier incomplet n’a été laissé. Les ${plural(files.length, "copie déjà faite est conservée", "copies déjà faites sont conservées")}.`)),
        h("div", { class: "center", style: "margin-top:36px" }, icon("shield", "big", 48), h("h2", {}, "Rien n’est abîmé"),
          h("p", {}, "« Reprendre » continue avec les projets restants, sans refaire les premiers. « Annuler ce qui a été fait » met les copies à la corbeille et laisse vos projets d’origine tels quels."))],
      status(h("span", {}, h("b", {}, files.length), " copies écrites · ", h("b", {}, left), " non traités"), "Arrêté."));
  }
  function viewError() {
    return frame("Une erreur est survenue", [btn("Réessayer", () => { S.view = "choose"; render(); }, "btn btn-primary")],
      h("div", { class: "center" }, icon("err", "big", 48), h("h2", {}, "L’opération n’a pas pu aboutir"),
        h("p", {}, S.error || "Erreur inconnue", " ", h("b", { style: "color:var(--pr-text)" }, "Aucun projet d’origine n’a été modifié.")),
        h("div", { class: "row" }, btn("Choisir un autre dossier", () => { S.view = "choose"; render(); }))),
      status("Aucun projet d’origine modifié."));
  }
  function viewPlugins() {
    const tone = { validated: ["ok", "Validé"], experimental: ["warn", "Expérimental · bloqué"], unsupported: ["neu", "Non pris en charge"] };
    const rows = (S.plugins || []).map((d) => h("tr", {}, h("td", {}, h("strong", {}, d.id), h("span", { class: "sub" }, d.vendor || "")),
      h("td", {}, stateBadge(tone[d.status][0], tone[d.status][1])), h("td", {}, d.adapter ? `Adaptateur : ${d.adapter}` : "Aucun adaptateur"), h("td", {}, d.source)));
    return frame("Bibliothèque de plugins", [btn("Retour", () => { S.view = S.prevView && S.prevView !== "plugins" ? S.prevView : "choose"; render(); })],
      [h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Plugin"), h("th", { style: "width:200px" }, "Statut"), h("th", {}, "Ce que ReAble sait faire"), h("th", { style: "width:100px" }, "Source"))), h("tbody", {}, rows)),
        h("div", { class: "hint" }, icon("info", "", 16), h("div", {}, h("b", {}, "Un plugin non testé reste bloqué. "), "Après un test dans Live, indiquez le résultat avec la commande « plugins validate » : le plugin devient utilisable pour vous. Rien n’est envoyé sans votre accord."))],
      status(h("span", {}, plural((S.plugins || []).length, "plugin connu", "plugins connus"), " · ", h("b", {}, (S.plugins || []).filter((d) => d.status === "validated").length), " validés")));
  }

  /* ---------- rendu ---------- */
  const VIEWS = { choose: viewChoose, analyzing: viewAnalyzing, understand: viewUnderstand, empty: viewEmpty, running: viewRunning, summary: viewSummary, stopped: viewStopped, error: viewError, plugins: viewPlugins };
  function render() {
    const active = document.activeElement;
    const keep = active && active.tagName === "INPUT" && active.type === "text" ? { v: active.value, s: active.selectionStart } : null;
    const nodes = VIEWS[S.view]().flat().filter(Boolean);
    root.replaceChildren(...nodes);
    if (keep) { const i = root.querySelector('input[type="text"]'); if (i) { i.value = keep.v; i.focus(); try { i.setSelectionRange(keep.s, keep.s); } catch (e) { /* ignore */ } } }
  }
  window.addEventListener("beforeunload", (e) => { if (busy()) { e.preventDefault(); e.returnValue = ""; } });
  /* Point d'entrée pour la fenêtre native : « Arrêter et fermer ? » */
  window.reableRequestClose = () => {
    if (!busy()) return true;
    if (confirm("Une tâche est en cours. Arrêter et fermer ?\nLe projet en cours est abandonné proprement ; les copies déjà faites sont conservées.")) { stopJob(); return true; }
    return false;
  };

  (async function init() {
    try {
      S.server = await api("/api/state");
      S.path = S.server.folder || "~/Music";
      if (S.server.job && (S.server.job.state === "running" || S.server.job.state === "stopping")) {
        S.view = S.server.job.kind === "analyze" ? "analyzing" : "running";
        startPolling(S.server.job.id, S.server.job.kind);
      } else if (S.server.analyzed) {
        S.selected = new Set(S.server.groups.filter((g) => g.selectable).map((g) => g.id));
        S.view = S.server.summary && S.server.summary.to_convert ? "understand" : "empty";
      }
    } catch (e) { S.error = e.message; S.view = "error"; }
    render();
  })();
})();
