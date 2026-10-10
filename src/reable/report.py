"""Rapports lisibles (Markdown) et complets (JSON)."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .model import Plugin, SetReport

STATUS_ICON = {"installé": "✅", "manquant": "❌", "inconnu": "❔"}


def classify(p: Plugin) -> str:
    if p.install_status == "installé":
        return "ok"
    if p.install_status != "manquant":
        return "inconnu"
    if p.replacements:
        return "autre-format"
    if p.family_installed:
        return "meme-famille"
    return "a-reinstaller"


_SECTIONS = [
    ("a-reinstaller", "À réinstaller (introuvable sur ce Mac)"),
    ("meme-famille", "Même famille installée (version plus récente ou voisine)"),
    ("autre-format", "Installé dans un autre format"),
]


def _pct(v: float) -> str:
    return "non mémorisée" if v != v else f"{v * 100:.1f} %"


def set_markdown(r: SetReport, full_params: bool = True) -> str:
    L = [f"## {Path(r.path).name}", "",
         f"- Fichier : `{r.path}`",
         f"- Créé avec : {r.live_version}",
         f"- Pistes : {len(r.tracks)} — plugins tiers : {len(r.plugins)}", ""]
    if not r.plugins:
        L.append("_Aucun plugin tiers._\n")
        return "\n".join(L)
    L += ["| Piste | Plugin | Format | Statut | Preset | Paramètres Live | Automations |",
          "|---|---|---|---|---|---|---|"]
    for p in r.plugins:
        autos = sum(1 for x in p.parameters if x.automated) + sum(x.clip_envelopes for x in p.parameters)
        where = p.track + (f" › {p.chain_path}" if p.chain_path else "")
        L.append(f"| {where} | {p.user_name or p.name} | {p.format} | "
                 f"{STATUS_ICON.get(p.install_status, '')} {p.install_status} | "
                 f"{p.preset_name or '—'} | {len(p.parameters)} | {autos or '—'} |")
    L.append("")
    for p in r.plugins:
        L += [f"### {p.track} — {p.name} ({p.format})", ""]
        L.append(f"- Fabricant : {p.manufacturer or '—'} · identifiant : `{p.identifier or '—'}`")
        L.append(f"- Preset : **{p.preset_name or 'inconnu'}**"
                 + (f" _(source : {p.preset_source})_" if p.preset_source else ""))
        if not p.enabled:
            L.append("- ⚠️ Device désactivé dans Live")
        L.append(f"- Installation : {p.install_status} ({p.install_detail})")
        if p.replacements:
            L.append(f"- Remplacement possible : **{p.name} en {', '.join(p.replacements)}**")
        L.append(f"- Taille de l'état sauvegardé : {p.state_bytes // 1024} Ko")
        for section, content in p.state_summary.items():
            if isinstance(content, dict):
                L.append(f"\n**{section}**\n")
                L += [f"- {k} : {v}" for k, v in content.items()]
            else:
                L.append(f"- {section} : {content}")
        if p.parameters and full_params:
            L += ["", "**Paramètres configurés dans Live** (valeurs normalisées 0–100 %, telles que Live les a notées — l'état interne du plugin fait foi)", "",
                  "| Paramètre | ID | Valeur | Automation | Env. de clip |", "|---|---|---|---|---|"]
            for x in p.parameters:
                L.append(f"| {x.name or '—'} | {x.param_id} | {_pct(x.value)} | "
                         f"{'oui' if x.automated else '—'} | {x.clip_envelopes or '—'} |")
        L.append("")
    if r.errors:
        L += ["**Erreurs**", ""] + [f"- {e}" for e in r.errors] + [""]
    return "\n".join(L)


def folder_markdown(reports: list[SetReport], folder: str) -> str:
    plugins = [p for r in reports for p in r.plugins]
    missing = [p for p in plugins if p.install_status == "manquant"]
    L = [f"# Rapport ReAble — {folder}", "",
         f"- Sets analysés : {len(reports)}",
         f"- Plugins tiers trouvés : {len(plugins)}",
         f"- Plugins manquants : {len(missing)}", ""]
    for cat, title in _SECTIONS:
        sel = [p for p in missing if classify(p) == cat]
        if not sel:
            continue
        L += [f"## {title}", "", "| Plugin | Occurrences | Sets | Disponible |", "|---|---|---|---|"]
        sets_of: dict[str, set[str]] = {}
        avail: dict[str, str] = {}
        for r in reports:
            for p in r.plugins:
                if classify(p) == cat:
                    k = f"{p.name} ({p.format})"
                    sets_of.setdefault(k, set()).add(r.path)
                    avail[k] = ", ".join(p.replacements or p.family_installed) or "—"
        for k, n in Counter(f"{p.name} ({p.format})" for p in sel).most_common():
            L.append(f"| {k} | {n} | {len(sets_of[k])} | {avail[k]} |")
        L.append("")
    rows = []
    for r in reports:
        m = [p for p in r.plugins if p.install_status == "manquant"]
        if m:
            rows.append((len(m), sum(classify(p) == "a-reinstaller" for p in m), Path(r.path).name))
    L += ["## Sets par nombre de plugins à traiter", "", "| Set | Manquants | Dont à réinstaller |", "|---|---|---|"]
    L += [f"| {name} | {n} | {k} |" for n, k, name in sorted(rows, reverse=True)] + [""]
    with_plugins = [r for r in reports if r.plugins or r.errors]
    without = [r for r in reports if not (r.plugins or r.errors)]
    L += [set_markdown(r) for r in with_plugins]
    if without:
        L += [f"## Sets sans plugin tiers ({len(without)})", ""]
        L += [f"- `{r.path}`" for r in without] + [""]
    return "\n".join(L)


def write(reports: list[SetReport], folder: str, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / "reable-report.md"
    js = out_dir / "reable-report.json"
    md.write_text(folder_markdown(reports, folder), encoding="utf-8")
    js.write_text(json.dumps([r.to_dict() for r in reports], ensure_ascii=False, indent=1,
                             default=lambda o: o.hex() if isinstance(o, bytes) else str(o)),
                  encoding="utf-8")
    return md, js
