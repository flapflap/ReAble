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
    gear: '<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/>',
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
    view: "choose", // choose | analyzing | understand | running | summary | stopped | empty | error | plugins | plugintest | settings
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
    templateDirs: [],
    lastKind: null,
    summary: null,
    ptest: null,   // test d'un plugin : { def, created, busy, error }
    beta: { enabled: false },
    about: false,
    report: null,
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
        const id = e.key || e.item;
        const row = S.rows.find((r) => r.id === id);
        if (row) { row.result = e.result; row.path = e.path || row.path; } else S.rows.push({ id, name: e.item, result: e.result, path: e.path });
      }
    } else if (e.item && e.phase) {
      const last = S.log[S.log.length - 1];
      const txt = `${e.item} · ${e.phase}`;
      if (!last || last.text !== txt) S.log.push({ t, kind: "", text: txt });
      if ((S.job.kind === "convert" || S.job.kind === "plan") && !S.rows.find((r) => r.id === (e.key || e.item))) S.rows.push({ id: e.key || e.item, name: e.item, result: "", path: "" });
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
      const r = await api("/api/analyze", { path: S.path, template_dirs: S.templateDirs });
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
  /* Glisser-déposer : la fenêtre native (pywebview) lit le chemin côté Python puis appelle reableDropped.
     Ici, le navigateur ne fournit jamais de chemin : on affiche l'explication au lieu de rester muet. */
  function dropHandlers(el) {
    el.addEventListener("dragover", (e) => { e.preventDefault(); el.classList.add("over"); });
    el.addEventListener("dragleave", () => el.classList.remove("over"));
    el.addEventListener("drop", async (e) => {
      e.preventDefault(); el.classList.remove("over");
      const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (!f) { toast("Déposez un dossier de projets."); return; }
      try { window.reableDropped(await api("/api/dropped-path", { name: f.name })); } catch (err) { toast("Le glisser-déposer a échoué : utilisez « Choisir… »."); }
    });
    return el;
  }
  window.reableDropped = (r) => {
    if (busy()) { toast("Une tâche est en cours : attendez la fin ou arrêtez-la avant de choisir un autre dossier."); return; }
    if (!r || r.error) { toast((r && r.error) || "Dépôt non reconnu : déposez un dossier de projets Live."); return; }
    S.path = r.path; startAnalyze();
  };
  async function saveOption(patch) {
    try { S.server = await api("/api/options", patch); } catch (e) { toast(e.message); }
    render();
  }
  async function undoAll() {
    const n = (S.summary && S.summary.result && S.summary.result.written ? S.summary.result.written.length : 0) || S.rows.filter((r) => r.path).length;
    if (!n) { toast("Aucune copie à annuler."); return; }
    if (!confirm(`Mettre ${plural(n, "copie", "copies")} à la corbeille ?\nVos projets d'origine ne sont pas touchés.`)) return;
    const r = await api("/api/undo", {});            // le serveur connaît toutes les copies écrites, même après un arrêt
    toast(`${plural(r.moved.length, "copie mise", "copies mises")} à la corbeille.`);
    S.view = "choose"; S.server = await api("/api/state");
    render();
  }
  async function addTemplateDir() {
    const native = window.pywebview && window.pywebview.api && window.pywebview.api.choose_folder;
    const path = native ? await window.pywebview.api.choose_folder() : (await api("/api/choose-folder", {})).path;
    if (!path) return;
    S.templateDirs = [...new Set([...S.templateDirs, path])];
    S.path = S.server.folder; startAnalyze();
  }
  const REPO = "https://github.com/flapflap/ReAble";
  async function openExternal(url) {
    const native = window.pywebview && window.pywebview.api && window.pywebview.api.open_url;
    try { if (native) await window.pywebview.api.open_url(url); else await api("/api/open-url", { url }); } catch (e) { toast(e.message); }
  }
  function feedbackUrl(kind) {
    const sv = S.server || {};
    const ctx = `\n\n---\nReAble ${sv.version || "?"} · macOS ${sv.system || "?"}`;
    const bug = kind === "bug";
    const body = bug ? `**Ce que je faisais**\n\n**Ce que j’attendais**\n\n**Ce qui s’est passé**\n${ctx}` : `**L’idée**\n\n**Pourquoi c’est utile**\n${ctx}`;
    return `${REPO}/issues/new?template=${bug ? "bug_report.md" : "feature_request.md"}&title=${encodeURIComponent(bug ? "[Bug] " : "[Idée] ")}&body=${encodeURIComponent(body)}`;
  }
  function pluginRequestUrl(r) {
    const sv = S.server || {};
    const body = `**Plugin** : ${r.plugin}\n**Éditeur** : ${r.vendor || "?"}\n**Format dans mon projet** : ${r.format}\n**Situation indiquée par ReAble** : ${r.verdict}\n**Projets concernés** : ${r.count}\n\n**Ce que je voudrais**\n\n---\nReAble ${sv.version || "?"} · macOS ${sv.system || "?"}`;
    return `${REPO}/issues/new?template=plugin_request.md&title=${encodeURIComponent("[Plugin] " + r.plugin)}&body=${encodeURIComponent(body)}`;
  }
  function aboutDialog() {
    const sv = S.server || {};
    const close = () => { S.about = false; render(); };
    return h("div", { class: "scrim", role: "presentation", onclick: (e) => { if (e.target === e.currentTarget) close(); } },
      h("div", { class: "dlg about", role: "dialog", "aria-modal": "true", "aria-labelledby": "about-title" },
        h("img", { class: "logo", src: "logo.png", alt: "", width: 56, height: 56 }),
        h("h2", { id: "about-title" }, "ReAble"),
        h("p", {}, `Version ${sv.version || "?"} · macOS ${sv.system || "?"}`),
        h("p", {}, "Retrouve et répare les plugins manquants de tes projets Ableton Live. Tes projets d’origine ne sont jamais modifiés."),
        h("div", { class: "col" },
          btn("Voir le projet sur GitHub", () => openExternal(REPO), "btn"),
          btn("Signaler un problème", () => openExternal(feedbackUrl("bug")), "btn"),
          btn("Proposer une idée", () => openExternal(feedbackUrl("feature")), "btn")),
        h("div", { class: "row" }, btn("Fermer", close, "btn btn-primary"))));
  }
  window.reableShowAbout = () => { S.about = true; render(); };
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
    return h("div", { class: "nav" + (active ? " on" : "") + (enabled && !active ? " click" : !enabled && !active ? " off" : ""), role: "button", tabindex: enabled ? "0" : "-1",
      "aria-current": active ? "page" : null, onclick: enabled ? onclick : null,
      onkeydown: enabled ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onclick(); } } : null }, icon(ic, "", 16), label, h("span", { class: "st" }, right || ""));
  }
  const busy = () => S.view === "analyzing" || S.view === "running";

  function sidebar() {
    const sv = S.server, analyzed = sv && sv.analyzed;
    const step = { choose: 0, analyzing: 0, error: 0, understand: 1, empty: 1, running: 2, summary: 2, stopped: 2, report: 1 }[S.view];
    const lib = S.view === "plugins" || S.view === "plugintest" || S.view === "settings";
    return h("nav", { class: "sidebar", "aria-label": "Étapes" },
      h("h3", {}, "Étapes"),
      nav("1 · Choisir", "folder", step === 0 && !lib, !busy(), () => { S.view = "choose"; render(); }),
      nav("2 · Valider", "list", step === 1 && !lib, !busy() && analyzed, () => { S.view = sv.summary && sv.summary.to_convert ? "understand" : "empty"; render(); }),
      nav("3 · Convertir", "play", step === 2 && !lib, false, () => {}),
      h("h3", { style: "margin-top:12px" }, "Bibliothèque"),
      nav("Plugins", "box", S.view === "plugins" || S.view === "plugintest", !busy(), openPlugins, S.plugins ? String(S.plugins.length) : ""),
      nav("Réglages", "gear", S.view === "settings", !busy(), openSettings),
      h("div", { class: "safe" }, icon("shield", "", 16), h("span", {}, "Vos projets d’origine ne sont jamais modifiés. Les copies portent [ReAble].")),
      sv && sv.version ? h("button", { type: "button", class: "ver", onclick: () => { S.about = true; render(); } }, `ReAble · version ${sv.version}`) : null);
  }
  const LIB_VIEWS = ["plugins", "plugintest", "settings"];
  function rememberView() { if (!LIB_VIEWS.includes(S.view)) S.prevView = S.view; }
  async function openPlugins() {
    try { S.plugins = await api("/api/plugins"); } catch (e) { S.plugins = []; }
    rememberView();
    S.view = "plugins"; render();
  }
  async function openSettings() {
    try { S.beta = await api("/api/beta"); } catch (e) { /* garde l'état connu */ }
    try { S.server = await api("/api/state"); } catch (e) { /* idem */ }
    rememberView();
    S.view = "settings"; render();
  }
  const leaveLibrary = () => { S.view = S.prevView && !LIB_VIEWS.includes(S.prevView) ? S.prevView : "choose"; render(); };
  function titlebar(sub, ...tools) {
    return h("div", { class: "titlebar" }, h("img", { class: "logo", src: "logo.png", alt: "", width: 28, height: 28 }),
      h("div", { class: "ttl" }, h("b", {}, "ReAble"), sub ? h("span", {}, sub) : null), h("div", { class: "tools" }, ...tools));
  }
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
    return frame("", [],
      [noDefs(), dropHandlers(h("div", { class: "drop" }, icon("folder", "", 44), h("h2", {}, "Quel dossier de projets analyser ?"),
        h("p", {}, "Glissez un dossier ici, ou choisissez-le. ReAble y cherche les projets Ableton Live (.als) et repère les plugins qui manquent sur ce Mac."),
        h("div", { class: "pathrow" }, h("div", { class: "input" }, input), btn("Choisir…", pickFolder), go)))],
      null);
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
      null);
  }
  function groupRow(g) {
    const sel = S.selected.has(g.id);
    const open = S.expanded.has(g.id);
    const stateEl = { validated: stateBadge("ok", "Validé"), default: stateBadge("warn", "Réglages par défaut"), old: stateBadge("err", "Action requise"), template: stateBadge("err", "Gabarit requis"),
      unsupported: stateBadge("neu", "Non pris en charge"), done: stateBadge("ok", "Déjà fait") }[g.kind];
    const detail = { validated: "Vos réglages seront repris.",
      default: "Repart des réglages par défaut ; l’ancien preset est noté sur la piste.",
      old: "À ouvrir et enregistrer dans Live 12, puis réanalyser.",
      template: `Pour convertir ces projets, ReAble a besoin d’un projet Live 12 qui contient ${g.targets.join(", ")} en VST3 (un « gabarit »). Chargez-le une fois dans un projet, enregistrez-le, puis ajoutez ce dossier.`, unsupported: g.plugins.slice(0, 4).join(", ") + (g.plugins.length > 4 ? "…" : "") + " — ReAble ne sait pas encore les convertir.",
      done: "Les copies existent déjà ; elles ne seront pas refaites." }[g.kind];
    const act = g.kind === "template" ? btnLink("Ajouter un dossier de gabarits…", addTemplateDir) : g.kind === "old" ? btnLink("Copier la liste", copyOldList) : btnLink(open ? "Masquer" : g.kind === "unsupported" ? "Voir lesquels" : "Voir les projets", () => { open ? S.expanded.delete(g.id) : S.expanded.add(g.id); render(); });
    const cb = g.selectable ? h("input", { type: "checkbox", checked: sel, "aria-label": `Convertir ${g.title}`, onchange: (e) => { e.target.checked ? S.selected.add(g.id) : S.selected.delete(g.id); render(); } }) : null;
    const rows = [h("tr", {}, h("td", { class: "chk" }, cb), h("td", {}, stateEl),
      h("td", {}, h("strong", {}, g.title), h("span", { class: "sub" }, detail)), h("td", { class: "n" }, g.count), h("td", {}, act))];
    if (open) rows.push(h("tr", { class: "sub" }, h("td"), h("td", { colspan: 4 }, h("div", { class: "names" }, (g.kind === "unsupported" ? g.plugins : g.sets.map(baseName)).map((n) => h("span", {}, n))))));
    return rows;
  }
  function btnLink(label, fn) { return btn(label, fn, "btn btn-sm"); }
  function optionFields(locked) {
    const o = S.server.options;
    const sample = (o.rename_template || "").replace("{track}", "Lead").replace("{from}", "VST2").replace("{to}", "VST3").replace("{plugin}", "Ozone 10").replace("{preset}", "Abstract City").replace("{date}", "2026-10-09");
    const sel = (value, choices, onchange, label) => h("div", { class: "pop" }, h("select", { "aria-label": label || "", disabled: locked, onchange: (e) => onchange(e.target.value) },
      choices.map(([v, l]) => h("option", { value: v, selected: v === value }, l))), icon("updown", "", 12));
    const field = (label, ...kids) => h("div", { class: "field" }, h("label", {}, label), ...kids);
    return [
      field("Piste d’origine", sel(o.replace_mode, [["duplicate_track", "Dupliquer la piste"], ["replace", "Remplacer sur place"]], (v) => saveOption({ replace_mode: v }), "Piste d’origine")),
      field("Où écrire les copies", sel(o.out_dir ? "other" : "beside", [["beside", "À côté des originaux"], ["other", o.out_dir ? shortPath(o.out_dir) : "Dans un autre dossier…"]], async (v) => {
        if (v === "beside") return saveOption({ out_dir: null });
        const r = await api("/api/choose-folder", {}); if (r.path) saveOption({ out_dir: r.path }); else render();
      }, "Où écrire les copies")),
      field("Nom des pistes converties", h("div", { class: "input" }, h("input", { type: "text", value: o.rename_template, disabled: locked, "aria-label": "Modèle de nom",
        onchange: (e) => saveOption({ rename_template: e.target.value }) })),
        h("div", { class: "pv" }, h("span", {}, "Aperçu"), h("span", { class: "mono" }, `Lead → ${sample}`))),
      field("Si la copie existe déjà", sel(o.if_exists, [["skip", "Ne pas la refaire"], ["overwrite", "La remplacer"], ["number", "Numéroter"]], (v) => saveOption({ if_exists: v }), "Si la copie existe déjà")),
      h("label", { class: "check" }, h("input", { type: "checkbox", checked: o.track_info, disabled: locked, onchange: (e) => saveOption({ track_info: e.target.checked }) }), "Écrire un texte d’information sur la piste"),
    ];
  }
  /* Panneau de réglages verrouillés, affiché pendant une conversion. */
  function inspector(locked) {
    return h("aside", { class: "inspector" + (locked ? " lock" : ""), "aria-label": "Réglages" }, h("h3", {}, locked ? "Réglages · verrouillés" : "Réglages"), ...optionFields(locked));
  }
  function viewUnderstand() {
    const sv = S.server, groups = sv.groups;
    const selCount = new Set(groups.filter((g) => g.selectable && S.selected.has(g.id)).flatMap((g) => g.sets)).size;
    const foot = h("div", { class: "status foot" },
      btn("Réanalyser", () => { S.path = sv.folder; startAnalyze(); }), btn("Plugins manquants", openReport), h("span", { class: "grow" }),
      btn("Essai à blanc", () => startConvert(true), "btn", { disabled: !selCount }),
      btn(`Convertir ${plural(selCount, "projet", "projets")}`, () => startConvert(false), "btn btn-primary", { disabled: !selCount }));
    return frame(`${baseName(sv.folder)} · ${plural(sv.sets, "projet analysé", "projets analysés")}`, [],
      h("div", { class: "valid" },
        h("div", {}, h("h2", {}, "Ce que ReAble va faire"), h("p", { class: "lead" }, "Cochez les conversions à lancer. Rien n’est écrit tant que vous ne cliquez pas sur Convertir.")),
        h("table", {}, h("thead", {}, h("tr", {}, h("th"), h("th", { style: "width:170px" }, "État"), h("th", {}, "Conversion"), h("th", { style: "text-align:right" }, "Projets"), h("th", { style: "width:170px" }))),
          h("tbody", {}, groups.flatMap(groupRow))),
        h("div", {}, h("h2", { style: "margin-bottom:8px" }, "Options de conversion"), h("div", { class: "opts" }, ...optionFields(false)))),
      foot);
  }
  const KIND_BADGE = { blocked: ["err", "Non convertible"], unknown: ["err", "Inconnu"], template: ["warn", "Gabarit requis"], old: ["warn", "Projet à ré-enregistrer"], convert: ["ok", "Sera converti"], done: ["ok", "Déjà fait"] };
  function reportText(rep) {
    return [`Plugins manquants — ${shortPath(rep.folder)}`, ""].concat(rep.rows.map((r) => `${r.plugin} (${r.format}) · ${plural(r.count, "projet", "projets")} · ${r.verdict}${r.hint ? " · " + r.hint : ""}\n   ${r.projects.join(", ")}`)).join("\n");
  }
  function reportBlock(rep, expanded) {
    if (!rep || !rep.rows.length) return h("p", { class: "lead" }, "Aucun plugin manquant dans ce dossier.");
    const rows = rep.rows.flatMap((r) => {
      const [tone, label] = KIND_BADGE[r.kind] || KIND_BADGE.unknown;
      const key = "rep|" + r.plugin + "|" + r.format, open = S.expanded.has(key);
      const main = h("tr", {}, h("td", {}, h("strong", {}, r.plugin), h("span", { class: "sub" }, `${r.format}${r.vendor ? " · " + r.vendor : ""}`)),
        h("td", {}, stateBadge(tone, label)), h("td", {}, r.verdict, r.hint ? h("span", { class: "sub" }, r.hint) : null),
        h("td", { class: "n" }, r.count), h("td", { class: "acts" }, btn(open ? "Masquer" : "Voir les projets", () => { open ? S.expanded.delete(key) : S.expanded.add(key); render(); }, "btn btn-sm"),
          r.kind === "unknown" || r.kind === "blocked" ? btn("Demander la prise en charge", () => openExternal(pluginRequestUrl(r)), "btn btn-sm btn-primary") : null));
      return open ? [main, h("tr", { class: "sub" }, h("td", { colspan: 5 }, h("div", { class: "names" }, r.projects.map((n) => h("span", {}, n)))))] : [main];
    });
    return h("table", {}, h("thead", {}, h("tr", {}, h("th", { style: "width:220px" }, "Plugin"), h("th", { style: "width:170px" }, "Situation"), h("th", { style: "min-width:220px" }, "Ce qu’il faut faire"), h("th", { style: "text-align:right;width:70px" }, "Projets"), h("th", { style: "width:290px" }))), h("tbody", {}, rows));
  }
  async function openReport() {
    try { S.report = await api("/api/missing-report"); } catch (e) { toast(e.message); return; }
    S.prevReport = S.view === "report" ? S.prevReport : S.view;
    S.view = "report"; render();
  }
  async function copyReport() {
    try { await navigator.clipboard.writeText(reportText(S.report)); toast("Rapport copié."); } catch (e) { toast("Copie impossible : autorisation refusée."); }
  }
  function viewReport() {
    const rep = S.report || { rows: [] };
    return frame("Plugins manquants", [btn("Copier le rapport", copyReport, "btn", { disabled: !rep.rows.length }), btn("Retour", () => { S.view = S.prevReport || "understand"; render(); })],
      h("div", { class: "valid" }, h("div", {}, h("h2", {}, "Plugins manquants dans ce dossier"), h("p", { class: "lead" }, `${plural(rep.rows.length, "plugin manquant", "plugins manquants")}, classés des plus bloquants aux plus simples.`)), reportBlock(rep)), null);
  }
  function viewEmpty() {
    const sv = S.server, sm = sv.summary || {};
    const done = sm.already_done || 0, old = sm.too_old || 0, unsup = sm.unsupported_plugins || 0;
    const title = done ? "Tout est déjà converti" : "Rien à convertir pour le moment";
    const reasons = [];
    if (done) reasons.push(`${plural(done, "projet a", "projets ont")} déjà ${done > 1 ? "leur" : "sa"} copie [ReAble] : rien n’est refait.`);
    if (old) reasons.push(`${plural(old, "projet est", "projets sont")} trop ancien${old > 1 ? "s" : ""} : ouvrez-${old > 1 ? "les" : "le"} dans Live 12, enregistrez-${old > 1 ? "les" : "le"}, puis réanalysez.`);
    const tpl = sm.template_missing || 0;
    if (tpl) reasons.push(`${plural(tpl, "projet attend", "projets attendent")} un gabarit : ajoutez un projet Live 12 qui contient ${(sm.templates_needed || []).join(", ")} en VST3.`);
    if (unsup) reasons.push(`${plural(unsup, "plugin n’a", "plugins n’ont")} pas d’équivalent connu : ReAble ne sait pas encore ${unsup > 1 ? "les" : "le"} convertir.`);
    if (!reasons.length) reasons.push("Aucun projet de ce dossier ne contient de plugin manquant que ReAble sait remplacer.");
    return frame(`${baseName(sv.folder)} · ${plural(sv.sets, "projet analysé", "projets analysés")}`, [btn("Réanalyser", () => { S.path = sv.folder; startAnalyze(); })],
      [noDefs(), h("div", { class: "center" }, icon("ok", "big", 48), h("h2", {}, title), reasons.map((r) => h("p", {}, r)),
        h("div", { class: "row" }, btn("Voir le rapport des plugins manquants", openReport))),],
      null);
  }
  function countsLine(c, d, i, e, extra) {
    return h("div", { class: "counts" }, h("b", {}, c), " convertis · ", h("b", {}, d), " en réglages par défaut · ", h("b", {}, i), " ignorés · ", h("b", {}, e), e > 1 ? " erreurs" : " erreur", extra ? ` · ${extra}` : "");
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
      [progressBlock("projets", S.job ? S.job.total : 0), countsLine(counts.c, counts.d, counts.i, counts.e),
        h("div", { class: "list" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", { style: "width:170px" }, "État"), h("th", {}, "Projet"))), h("tbody", {}, S.rows.slice(-60).map(resultRow)))),
        h("div", { class: "logpane" }, h("header", {}, "Journal", h("span", { class: "seg", role: "group", "aria-label": "Filtre du journal" }, seg("all", "Tout"), seg("warn", "Avertissements"), seg("err", "Erreurs"))),
          h("div", { class: "log", role: "log", "aria-label": "Journal" }, log.map((x) => h("div", {}, h("time", {}, x.t), h("span", { class: x.kind === "ok" ? "ok" : "" }, x.text)))))],
      null, inspector(true));
  }
  function viewSummary() {
    const res = (S.summary && S.summary.result) || {}, written = res.written || [];
    const c = res.counts || {};
    const rows = written.slice(0, 200).map((p) => h("tr", {}, h("td", {}, baseName(p)), h("td", {}, shortPath(p.replace(/\/[^/]*$/, ""))), h("td", {}, btnLink("Afficher dans le Finder", () => api("/api/reveal", { path: p })))));
    return frame("Conversion terminée", [btn("Ouvrir le dossier", () => written[0] && api("/api/reveal", { path: written[0] }), "btn", { disabled: !written.length }),
        btn("Copier la liste", async () => { await navigator.clipboard.writeText(written.join("\n")); toast("Liste copiée."); }, "btn", { disabled: !written.length }),
        btn("Annuler cette conversion", undoAll, "btn", { disabled: !written.length })],
      [h("div", { class: "summary" }, h("h2", {}, `Conversion terminée : ${plural(written.length, "projet converti", "projets convertis")}, ${plural(c.errors || 0, "erreur", "erreurs")}`),
          h("p", {}, "Les copies sont à côté des originaux, avec [ReAble] dans leur nom. Vos originaux n’ont pas été modifiés."),
          countsLine(c.converted || 0, c.default || 0, c.skipped || 0, c.errors || 0, S.job && S.job.last ? `durée ${fmtTime(S.job.last.elapsed)}` : "")),
        h("div", { class: "hint" }, icon("info", "", 16), h("div", {}, h("b", {}, "Que vérifier dans Live ? "), "Ouvrez une copie : les pistes dupliquées chargent leur instrument, l’originale est en sourdine ; le nouveau plugin d’effet est placé avant l’ancien, désactivé.")),
        h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Copie créée"), h("th", {}, "Dossier"), h("th", { style: "width:170px" }))), h("tbody", {}, rows))],
      null);
  }
  function viewStopped() {
    const l = S.summary.last || {}, done = l.index || 0, total = l.total || 0, left = Math.max(0, total - done);
    const files = S.rows.filter((r) => r.path).map((r) => r.path);
    return frame("Conversion arrêtée", [btn("Annuler ce qui a été fait", undoAll, "btn", { disabled: !files.length }), btn("Reprendre", () => startConvert(false), "btn btn-primary")],
      [h("div", { class: "summary" }, h("h2", {}, `Arrêté : ${plural(done, "projet fait", "projets faits")}, ${plural(left, "non traité", "non traités")}`),
          h("p", {}, `Le projet qui était en cours a été abandonné proprement : aucun fichier incomplet n’a été laissé. Les ${plural(files.length, "copie déjà faite est conservée", "copies déjà faites sont conservées")}.`)),
        h("div", { class: "center", style: "margin-top:36px" }, icon("shield", "big", 48), h("h2", {}, "Rien n’est abîmé"),
          h("p", {}, "« Reprendre » continue avec les projets restants, sans refaire les premiers. « Annuler ce qui a été fait » met les copies à la corbeille et laisse vos projets d’origine tels quels."))],
      null);
  }
  function viewError() {
    return frame("Une erreur est survenue", [btn("Réessayer", () => { S.view = "choose"; render(); }, "btn btn-primary")],
      h("div", { class: "center" }, icon("err", "big", 48), h("h2", {}, "L’opération n’a pas pu aboutir"),
        h("p", {}, S.error || "Erreur inconnue", " ", h("b", { style: "color:var(--pr-text)" }, "Aucun projet d’origine n’a été modifié.")),
        h("div", { class: "row" }, btn("Choisir un autre dossier", () => { S.view = "choose"; render(); }))),
      null);
  }
  const STATUS_LABEL = { validated: ["ok", "Validé"], experimental: ["warn", "À tester · bloqué"], unsupported: ["neu", "Non pris en charge"] };
  const ORIGIN_LABEL = { "intégré": "Fournie avec ReAble", "partagé": "Bibliothèque partagée", "utilisateur": "Ajoutée ou validée par vous" };
  const CAPABILITY = { "container-copy": "Reprend le preset et les réglages", izotope: "Reprend le preset et les réglages (format iZotope)" };
  function viewPlugins() {
    const rows = (S.plugins || []).map((d) => {
      const [tone, label] = STATUS_LABEL[d.status];
      const act = d.status === "experimental" ? btn("Tester ce plugin", () => { S.ptest = { def: d, created: null, busy: false, error: null, note: "" }; S.view = "plugintest"; render(); }, "btn btn-sm") : null;
      return h("tr", {}, h("td", {}, h("strong", {}, d.name), h("span", { class: "sub" }, d.vendor || "")), h("td", {}, stateBadge(tone, label)),
        h("td", {}, d.adapter ? (CAPABILITY[d.adapter] || "Prise en charge partielle") : "Pas encore convertible"), h("td", {}, ORIGIN_LABEL[d.source] || d.source), h("td", {}, act));
    });
    const validated = (S.plugins || []).filter((d) => d.status === "validated").length;
    return frame("Bibliothèque de plugins", [btn("Retour", leaveLibrary)],
      h("div", { class: "valid" },
        h("div", {}, h("h2", {}, "Plugins connus de ReAble"), h("p", { class: "lead" }, `${plural(validated, "plugin validé", "plugins validés")} sur ${(S.plugins || []).length}. Un plugin « à tester » reste bloqué tant que vous n’avez pas vérifié le résultat dans Live.`)),
        h("table", {}, h("thead", {}, h("tr", {}, h("th", { style: "width:190px" }, "Plugin"), h("th", { style: "width:170px" }, "Statut"), h("th", {}, "Ce que ReAble sait faire"), h("th", { style: "width:190px" }, "Origine"), h("th", { style: "width:130px" }))), h("tbody", {}, rows))),
      null);
  }
  async function createTestCopy() {
    const t = S.ptest; t.busy = true; t.error = null; render();
    try { t.created = await api("/api/plugins/test", { id: t.def.id }); } catch (e) { t.error = e.message; }
    t.busy = false; render();
  }
  async function sendVerdict(result) {
    const t = S.ptest;
    try {
      await api("/api/plugins/validate", { id: t.def.id, result, note: t.note });
      toast(result === "ok" ? `${t.def.name} est maintenant validé pour vous.` : `Noté : ${t.def.name} reste bloqué.`);
      S.plugins = await api("/api/plugins"); S.server = await api("/api/state");
      S.view = "plugins"; render();
    } catch (e) { toast(e.message); }
  }
  function viewPluginTest() {
    const t = S.ptest, d = t.def;
    const step = (n, title, ...body) => h("div", { class: "step" }, h("span", { class: "num" }, String(n)), h("div", {}, h("b", {}, title), ...body));
    const analyzed = S.server && S.server.analyzed;
    const first = t.created
      ? step(1, "La copie de test est prête", h("p", {}, `Projet « ${t.created.project} » : ${t.created.plugin} → ${t.created.target}. Rangée à part, vos projets ne sont pas touchés.`),
          h("div", { class: "row" }, btn("Afficher dans le Finder", () => api("/api/reveal", { path: t.created.path }), "btn btn-sm")))
      : step(1, "Créer une copie de test", analyzed
          ? h("p", {}, `ReAble prend un de vos projets analysés qui utilise ${d.name} et en écrit une copie de test, rangée dans le dossier de ReAble.`)
          : h("p", {}, `ReAble a besoin d’un de vos projets qui utilise ${d.name}. Analysez d’abord le dossier qui le contient.`),
          t.error ? h("p", { class: "err" }, t.error) : null,
          h("div", { class: "row" }, analyzed ? btn(t.busy ? "Création…" : "Créer la copie de test", createTestCopy, "btn btn-primary btn-sm", { disabled: t.busy })
            : btn("Choisir un dossier", () => { S.view = "choose"; render(); }, "btn btn-primary btn-sm")));
    const locked = !t.created;
    return frame(`Tester ${d.name}`, [btn("Retour", () => { S.view = "plugins"; render(); })],
      h("div", { class: "valid" },
        h("div", {}, h("h2", {}, `Vérifier ${d.name} dans Live`), h("p", { class: "lead" }, "Trois étapes. Le résultat reste sur ce Mac : rien n’est envoyé sans votre accord.")),
        first,
        step(2, "Ouvrir la copie dans Live 12", h("p", {}, "Vérifiez que le plugin se charge, avec le même preset et des réglages identiques à ceux du projet d’origine. Jouez quelques notes ou écoutez la piste.")),
        step(3, "Dire ce que vous avez constaté",
          h("div", { class: "input", style: "max-width:420px" }, h("input", { type: "text", placeholder: "Remarque (facultatif)", value: t.note, disabled: locked, "aria-label": "Remarque",
            oninput: (e) => { t.note = e.target.value; } })),
          h("div", { class: "row" }, btn("Oui, c’est identique", () => sendVerdict("ok"), "btn btn-primary btn-sm", { disabled: locked }), btn("Non, il y a un problème", () => sendVerdict("ko"), "btn btn-sm", { disabled: locked })))),
      null);
  }
  async function toggleBeta(on) {
    try { S.beta = await api("/api/beta", { enabled: on }); } catch (e) { toast(e.message); }
    render();
  }
  async function exportBeta() {
    try { const r = await api("/api/beta/export", {}); toast("Résultats exportés sur le Bureau."); api("/api/reveal", { path: r.path }); } catch (e) { toast(e.message); }
  }
  function viewSettings() {
    const sv = S.server || {};
    const block = (title, ...kids) => h("section", { class: "block" }, h("h2", {}, title), ...kids);
    return frame("Réglages", [btn("Retour", leaveLibrary)],
      h("div", { class: "valid" },
        block("Programme bêta",
          h("p", { class: "lead" }, "Aidez à enrichir la bibliothèque : ReAble peut préparer un fichier anonyme avec le résultat de vos tests de plugins (aucun nom de projet, de piste ni de chemin). Vous l’envoyez vous-même, si vous le souhaitez."),
          h("label", { class: "check" }, h("input", { type: "checkbox", checked: S.beta.enabled, onchange: (e) => toggleBeta(e.target.checked) }), "Participer au programme bêta"),
          h("div", { class: "row" }, btn("Exporter mes résultats", exportBeta, "btn btn-sm", { disabled: !S.beta.enabled || !S.beta.has_results })),
          S.beta.enabled && !S.beta.has_results ? h("p", { class: "lead" }, "Aucun résultat à exporter : testez d’abord un plugin depuis l’onglet Plugins.") : null),
        block("Gabarits",
          h("p", { class: "lead" }, "Pour convertir vers un plugin, ReAble a besoin d’un projet Live 12 qui le contient en VST3. Il en garde un exemplaire à chaque analyse ; vous pouvez en ajouter depuis l’écran Valider."),
          S.templateDirs.length ? h("div", { class: "names" }, S.templateDirs.map((d) => h("span", {}, shortPath(d)))) : null),
        block("Bibliothèque de plugins",
          h("p", { class: "lead" }, `${plural(sv.definitions || 0, "plugin connu", "plugins connus")}.`),
          h("div", { class: "row" }, btn("Voir les plugins", openPlugins, "btn btn-sm"))),
        block("À propos et retours", h("p", { class: "lead" }, `ReAble, version ${sv.version || "?"}. Un problème, une idée ? Dites-le sur GitHub : le message est pré-rempli avec la version et le système.`),
          h("div", { class: "row" }, btn("Signaler un problème", () => openExternal(feedbackUrl("bug")), "btn btn-sm"), btn("Proposer une idée", () => openExternal(feedbackUrl("feature")), "btn btn-sm"),
            btn("Voir le projet sur GitHub", () => openExternal(REPO), "btn btn-sm")))),
      null);
  }

  /* ---------- rendu ---------- */
  const VIEWS = { choose: viewChoose, analyzing: viewAnalyzing, understand: viewUnderstand, empty: viewEmpty, running: viewRunning, summary: viewSummary, stopped: viewStopped, error: viewError, plugins: viewPlugins, plugintest: viewPluginTest, settings: viewSettings, report: viewReport };
  function render() {
    const active = document.activeElement;
    const keep = active && active.tagName === "INPUT" && active.type === "text" ? { v: active.value, s: active.selectionStart } : null;
    const nodes = VIEWS[S.view]().flat().filter(Boolean);
    if (S.about) nodes.push(aboutDialog());
    root.replaceChildren(...nodes);
    if (keep) { const i = root.querySelector('input[type="text"]'); if (i) { i.value = keep.v; i.focus(); try { i.setSelectionRange(keep.s, keep.s); } catch (e) { /* ignore */ } } }
  }
  window.addEventListener("keydown", (e) => { if (e.key === "Escape" && S.about) { S.about = false; render(); } });
  window.addEventListener("beforeunload", (e) => { if (busy()) { e.preventDefault(); e.returnValue = ""; } });
  /* Point d'entrée pour la fenêtre native : « Arrêter et fermer ? » */
  window.reableShowSettings = () => { if (!busy()) openSettings(); };
  window.reableRequestClose = () => {
    if (!busy()) return true;
    if (confirm("Une tâche est en cours. Arrêter et fermer ?\nLe projet en cours est abandonné proprement ; les copies déjà faites sont conservées.")) { stopJob(); return true; }
    return false;
  };

  /* Messages de la fenêtre native (menu « À propos », dépôt d'un dossier) : relevés toutes les demi-secondes. */
  setInterval(async () => {
    let r;
    try { r = await api("/api/ui-events"); } catch (e) { return; }
    for (const ev of r.events || []) {
      if (ev.type === "about") { S.about = true; render(); }
      else if (ev.type === "drop") window.reableDropped(ev.data);
    }
  }, 500);

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
