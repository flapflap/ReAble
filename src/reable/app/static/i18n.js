/* ReAble — traduction de l'interface. Le français est la langue d'origine : les textes du code sont en français et
   le dictionnaire locales/en.json donne l'anglais. Tout texte absent du dictionnaire reste en français (jamais d'erreur). */
(() => {
  "use strict";
  const I = { lang: "fr", exact: new Map(), patterns: [] };
  window.I18N = I;

  I.load = async () => {
    try {
      const d = await (await fetch("locales/en.json")).json();
      for (const [k, v] of Object.entries(d.exact || {})) I.exact.set(k.trim(), v.trim());
      I.patterns = (d.patterns || []).map(([re, out]) => [new RegExp(re), out]);
    } catch (e) { /* sans dictionnaire : français */ }
  };

  /* Traduit un texte (en conservant les espaces qui l'entourent). */
  I.T = (s) => {
    if (I.lang !== "en" || typeof s !== "string" || !s) return s;
    const m = /^(\s*)([\s\S]*?)(\s*)$/.exec(s);
    const core = m[2];
    if (!core) return s;
    const hit = I.exact.get(core);
    if (hit !== undefined) return m[1] + hit + m[3];
    for (const [re, out] of I.patterns) {
      const g = re.exec(core);
      if (g) return m[1] + out.replace(/\$(\d)/g, (_, n) => I.T(g[+n] || "")) + m[3];
    }
    return s;
  };

  /* Phrase construite avec des variables : on écrit les deux langues côte à côte. */
  I.L = (fr, en) => (I.lang === "en" ? en : fr);

  const ATTRS = ["placeholder", "aria-label", "title", "alt"];
  /* Passe sur le DOM après chaque affichage : textes et attributs. Ce qui est marqué translate="no"
     (noms de projets, de plugins, chemins) n'est jamais touché. */
  I.localize = (root) => {
    if (I.lang !== "en") return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const n of nodes) {
      if (n.parentElement && n.parentElement.closest('[translate="no"]')) continue;
      const t = I.T(n.nodeValue);
      if (t !== n.nodeValue) n.nodeValue = t;
    }
    for (const el of root.querySelectorAll(ATTRS.map((a) => `[${a}]`).join(","))) {
      if (el.closest('[translate="no"]')) continue;
      for (const a of ATTRS) if (el.hasAttribute(a)) { const v = el.getAttribute(a), t = I.T(v); if (t !== v) el.setAttribute(a, t); }
    }
  };
})();
