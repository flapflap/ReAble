"""Point d'entrée : reable scan <dossier|fichier> [--out DOSSIER]."""
from __future__ import annotations

import argparse
from pathlib import Path

from . import alsfile, inventory, report
from .extract import extract


def _compare(set_file: Path, name: str) -> int:
    from .compare import compare_states
    r = extract(set_file)
    formats: dict = {}
    for p in r.plugins:
        if p.name == name:
            formats.setdefault(p.format, p)
    if len(formats) < 2:
        print(f"« {name} » n'existe pas dans deux formats dans ce set (trouvé : {sorted(formats) or 'rien'}).")
        return 2
    (fa, pa), (fb, pb) = list(formats.items())[:2]
    res = compare_states(pa, pb)
    print(f"{name} : {fa} vs {fb} → {res['verdict']} "
          f"({res['bytes_a']} o / {res['bytes_b']} o, {res['common_keys']} clés égales, schéma {'identique' if res['same_schema'] else 'différent'})")
    for k in res["diff_keys"]:
        print(f"  ≠ {k}")
    return 0


def _plugins_cmd(args) -> int:
    import json
    from . import registry
    a = args.action
    if a == "list":
        print(f"{'Identifiant':20} {'Éditeur':20} {'Adaptateur':15} {'Statut':13} {'Source':11} Validations")
        for d in registry.load_all():
            print(f"{d.id[:19]:20} {d.vendor[:19]:20} {str(d.adapter or '—'):15} {d.status:13} {d.source:11} {len(d.validated)}")
        print(f"\nDossier utilisateur : {registry.user_dir()}")
        return 0
    if a == "add":
        if not args.arg or not args.match:
            print("usage : reable plugins add <id> --match <regex> [--adapter …]")
            return 2
        d = registry.add_definition(args.arg, args.match, args.adapter, args.vendor, args.notes)
        print(f"« {d.id} » ajouté ({d.status}) : {'bloqué tant qu’il n’est pas validé' if d.status == 'experimental' else 'non supporté'}")
        return 0
    if a == "validate":
        if not args.arg or not args.result:
            print("usage : reable plugins validate <id> --result ok|ko [--variant …] [--live …]")
            return 2
        d = registry.record_validation(args.arg, args.result, args.variant, args.live, args.note)
        print(f"« {d.id} » : {d.status} ({len(d.validated)} validation(s) enregistrée(s))")
        return 0
    if a == "export":
        bundle = registry.export_bundle(beta=args.beta)
        text = json.dumps(bundle, ensure_ascii=False, indent=1)
        if args.beta:
            print(text)
            print("\n↑ Voici EXACTEMENT ce qui serait partagé. Relisez-le ; rien n'est envoyé automatiquement :")
            print("  joignez le fichier à une issue « Résultat bêta » du dépôt reable-definitions.")
        if args.out:
            Path(args.out).expanduser().write_text(text, encoding="utf-8")
            print(f"Fichier écrit : {args.out}")
        elif not args.beta:
            print(text)
        return 0
    if a == "import":
        if not args.arg:
            print("usage : reable plugins import <fichier.json>")
            return 2
        print(f"{registry.import_bundle(args.arg)} définition(s) importée(s) (couche « partagé »)")
        return 0
    if a == "sync":
        ok, msg = registry.sync(args.url)
        print(("✅ " if ok else "⚠️ ") + msg)
        return 0 if ok else 2
    if a == "config":
        s = registry.configure(args.repo_url, args.definitions_dir)
        print(json.dumps(s, ensure_ascii=False, indent=1))
        return 0
    if a == "beta":
        if args.arg not in ("on", "off"):
            print("usage : reable plugins beta on|off")
            return 2
        cfg = registry.set_beta(args.arg == "on")
        print(f"Programme bêta : {'activé' if cfg['enabled'] else 'désactivé'}" +
              (f" — pseudonyme {cfg['contributor_id']} (aléatoire, sans lien avec votre identité)" if cfg["enabled"] else ""))
        return 0
    return 2


def _verify_cmd(args) -> int:
    from .compare import verify_upgrade
    def pick(path, name, nth=0, need_state=True):
        found = [p for p in extract(Path(path).expanduser()).plugins
                 if p.name.lower() == name.lower() and (p.state_bytes or not need_state)]
        return found[nth] if len(found) > nth else None
    old = pick(args.original, args.plugin, args.nth)
    if old is None or "json" not in old.state_full:
        print(f"« {args.plugin} » introuvable dans l'original, ou état non décodable (JSON iZotope attendu).")
        return 2
    target = args.target or args.plugin
    new = [p for p in extract(Path(args.saved).expanduser()).plugins if p.name.lower() == target.lower() and p.format == "VST3"
           and "json" in p.state_full]
    if not new:
        print(f"Aucun « {target} » VST3 avec un état dans le set sauvegardé.")
        return 2
    default = None
    if args.default_from:
        d = pick(args.default_from, target)
        default = d.state_full.get("json") if d else None
    res = verify_upgrade(old.state_full["json"], new[0].state_full["json"], default, min_meaningful=10)
    print(f"{args.plugin} → {target} : {res['verdict']}")
    print(f"  valeurs communes : {res['common']} ; significatives (≠ défaut) : {res['meaningful']} ; "
          f"reprises : {res['kept']} ; revenues au défaut : {res['at_default']}")
    for k, v in res["examples_kept"]:
        print(f"  ✓ {k} = {v}")
    for k, o, n in res["examples_lost"]:
        print(f"  ✗ {k} : ancien {o} → nouveau {n}")
    return 0


def _convert_cmd(args) -> int:
    import json
    from .api import analyze, convert, propose
    from .batch import ConvertOptions, load_profile, save_profile
    opts = load_profile(args.profile) if args.profile else ConvertOptions()
    if args.all:
        opts.only_missing = False
    if args.no_note:
        opts.write_note = False
    if args.no_embed:
        opts.embed_original = False
    if args.out:
        opts.out_dir = Path(args.out).expanduser()
    if args.if_exists:
        opts.if_exists = args.if_exists
    if args.copy_controller_state:
        opts.copy_controller_state = True
    if args.family:
        opts.families = frozenset(opts.families) | frozenset(args.family)
    for attr in ("replace_mode", "rename_target", "rename_template", "missing_preset", "state_mode"):
        if getattr(args, attr) is not None:
            setattr(opts, attr, getattr(args, attr))
    if args.no_track_info:
        opts.track_info = False
    if args.track_info_template is not None:
        opts.track_info_template = args.track_info_template
    if args.map:
        opts.mapping = {**opts.mapping, **dict(m.split("=", 1) for m in args.map)}
    if args.skip:
        opts.skip_plugins = list(opts.skip_plugins) + args.skip
    if args.save_profile:
        save_profile(opts, args.save_profile)
    a = analyze(args.target, args.plugins_root, args.include_packs, template_dirs=args.templates,
                
                progress=lambda step, i, n: print(f"{step} {i}/{n}", flush=True) if i % 50 == 0 else None)
    items = propose(a, opts)
    ok = [i for i in items if i.status == "convertible"]
    blocked = [i for i in items if i.status == "bloqué"]
    skipped = [i for i in items if i.status == "ignoré"]
    print(f"{len(a.reports)} set(s) analysé(s) — {len(ok)} conversion(s) possible(s), {len(blocked)} bloquée(s)"
          + (f", {len(skipped)} déjà faite(s)" if skipped else ""))
    from collections import Counter
    for reason, n in Counter(i.reason.split(" (")[0].split(" « ")[0] for i in blocked).most_common(6):
        print(f"   bloqué ×{n} : {reason}")
    old = sorted({i.set_path for i in blocked if i.target_name and "trop ancien" in i.reason})
    if old:
        print(f"{len(old)} set(s) contiennent des plugins convertibles mais sont trop anciens : "
              "à ouvrir et enregistrer dans Live 12 d'abord (liste dans --report)")
    result = None
    if not args.dry_run and ok:
        result = convert(a, opts, items)
        print(f"{len(result.written)} set(s) écrit(s)")
        for w in result.written[:10]:
            print("  →", w)
    if args.report:
        data = {"items": [i.to_dict() for i in items], "written": result.written if result else [], "a_reenregistrer_dans_live_12": old}
        Path(args.report).expanduser().write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="reable",
                                 description="Analyse des sets Ableton Live : plugins manquants, presets, paramètres.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sc = sub.add_parser("scan", help="analyser un dossier ou un fichier .als/.xml")
    sc.add_argument("target")
    sc.add_argument("--out", default=None, help="dossier du rapport (défaut : à côté de la cible)")
    sc.add_argument("--plugins-root", action="append", default=None,
                    help="dossier(s) Plug-Ins à inventorier (défaut : emplacements macOS standard)")
    sc.add_argument("--include-packs", action="store_true",
                    help="inclure les « Factory Packs » d'Ableton (ignorés par défaut)")
    cp = sub.add_parser("compare", help="comparer l'état d'un même plugin chargé dans deux formats")
    cp.add_argument("set_file")
    cp.add_argument("plugin", help="nom du plugin, ex. « Ozone 8 »")
    rw = sub.add_parser("rewrite", help="réécrire un plugin AU en VST3 (nouveau fichier, original intact)")
    rw.add_argument("set_file")
    rw.add_argument("--plugin", required=True, help="nom du plugin, ex. « Massive X »")
    rw.add_argument("--template", default=None, help="set contenant le plugin en VST3 (défaut : le même set)")
    rw.add_argument("--from", dest="source_format", default="AU", choices=["AU", "VST2"],
                    help="format d'origine du plugin (défaut : AU)")
    rw.add_argument("--as", dest="target_name", default=None,
                    help="nom du plugin VST3 cible si différent (ex. Kontakt 5 -> « Kontakt 8 »)")
    rw.add_argument("--suffix", default="", help="texte ajouté dans [ReAble…] du nom de sortie")
    rw.add_argument("--out", default=None, help="dossier de sortie (défaut : à côté du set)")
    rs = sub.add_parser("restore", help="remettre les plugins d'origine à partir des notes ReAble")
    rs.add_argument("set_file")
    rs.add_argument("--out", default=None, help="dossier de sortie (défaut : à côté du set)")
    rs.add_argument("--original", default=None, help="set d'origine (si la note n'embarque pas l'original)")
    rw.add_argument("--no-note", action="store_true", help="ne pas écrire de note ReAble dans le device")
    rw.add_argument("--no-embed", action="store_true", help="ne pas embarquer l'original (note plus courte, pas de restore)")
    cv = sub.add_parser("convert", help="convertir en lot les plugins AU/VST2 d'un dossier vers VST3")
    cv.add_argument("target", help="dossier de sets ou fichier .als")
    cv.add_argument("--out", default=None, help="dossier de sortie (structure reproduite ; défaut : à côté des sets)")
    cv.add_argument("--dry-run", action="store_true", help="essai à blanc : rien n'est écrit")
    cv.add_argument("--all", action="store_true", help="convertir aussi les plugins déjà installés dans leur format")
    cv.add_argument("--profile", default=None, help="profil de réglages JSON (les options ci-dessous le surchargent)")
    cv.add_argument("--save-profile", default=None, help="enregistrer les réglages effectifs dans ce fichier JSON")
    cv.add_argument("--replace-mode", choices=["replace", "duplicate_track", "keep_device"], default=None,
                    help="remplacer sur place, dupliquer la piste (original muté), ou garder l'ancien effet désactivé")
    cv.add_argument("--rename-target", choices=["track", "device", "none"], default=None)
    cv.add_argument("--rename-template", default=None,
                    help="modèle de nom, variables : {track} {plugin} {from} {to} {preset} {date}")
    cv.add_argument("--missing-preset", choices=["omit", "plugin", "question"], default=None)
    cv.add_argument("--state-mode", choices=["transfer", "header", "none"], default=None,
                    help="transfer : garder l'état ; header : adapter l'en-tête à la version cible ; none : réglages par défaut")
    cv.add_argument("--copy-controller-state", action="store_true",
                    help="écrire aussi l'état dans ControllerState (comme Ozone 8/9 en VST3)")
    cv.add_argument("--family", action="append", default=[], metavar="FAMILLE",
                    help="autoriser une famille supplémentaire (ex. ozone, en test)")
    cv.add_argument("--templates", action="append", default=[], metavar="DOSSIER|SET",
                    help="sets ou dossiers supplémentaires où chercher des gabarits VST3 (répétable)")
    cv.add_argument("--if-exists", choices=["skip", "overwrite", "number"], default=None,
                    help="si le fichier de sortie existe : skip (défaut, ne pas refaire), overwrite (sauvegarde horodatée), number")
    cv.add_argument("--no-track-info", action="store_true", help="ne pas écrire le texte d'info des pistes")
    cv.add_argument("--track-info-template", default=None, help="modèle du texte d'info ({plugin} {from} {to} {preset} {date} {track} {original_track})")
    cv.add_argument("--map", action="append", default=[], metavar="SOURCE=CIBLE",
                    help="forcer une cible, ex. « Kontakt 5=Kontakt 8 » (répétable)")
    cv.add_argument("--skip", action="append", default=[], metavar="PLUGIN", help="ne jamais convertir ce plugin")
    cv.add_argument("--no-note", action="store_true")
    cv.add_argument("--no-embed", action="store_true")
    cv.add_argument("--plugins-root", action="append", default=None)
    cv.add_argument("--include-packs", action="store_true")
    cv.add_argument("--report", default=None, help="écrire le rapport JSON de conversion ici")
    pl = sub.add_parser("plugins", help="définitions de plugins : liste, ajout, validation, partage, synchronisation")
    pl.add_argument("action", choices=["list", "add", "validate", "export", "import", "sync", "config", "beta"])
    pl.add_argument("arg", nargs="?", help="identifiant (add, validate), fichier (import) ou on/off (beta)")
    pl.add_argument("--match", action="append", default=[], help="add : expression régulière sur le nom (répétable)")
    pl.add_argument("--adapter", default=None, help="add : container-copy | izotope | none (défaut : aucun, plugin non supporté)")
    pl.add_argument("--vendor", default="")
    pl.add_argument("--notes", default="")
    pl.add_argument("--result", choices=["ok", "ko"], default=None, help="validate : résultat du test dans Live")
    pl.add_argument("--variant", default="transfer", help="validate : transfer | header | none")
    pl.add_argument("--live", default="", help="validate : version de Live testée (ex. 12.4)")
    pl.add_argument("--note", default="")
    pl.add_argument("--beta", action="store_true", help="export : version anonyme pour le programme bêta")
    pl.add_argument("--out", default=None, help="export : fichier de sortie")
    pl.add_argument("--url", default=None, help="sync : URL du dépôt de définitions")
    pl.add_argument("--repo-url", default=None, help="config : URL du dépôt de définitions")
    pl.add_argument("--definitions-dir", default=None, help="config : dossier local de définitions (clone de travail)")
    vf = sub.add_parser("verify", help="vérifier qu'un plugin mis à niveau a bien repris l'état d'origine (set re-sauvegardé dans Live)")
    vf.add_argument("original", help="set d'origine (avec l'ancien plugin)")
    vf.add_argument("saved", help="set converti, ouvert puis re-sauvegardé dans Live")
    vf.add_argument("--plugin", required=True, help="ancien plugin dans l'original, ex. « Ozone 9 »")
    vf.add_argument("--target", default=None, help="nouveau plugin dans le set sauvegardé, ex. « Ozone 10 »")
    vf.add_argument("--default-from", default=None, help="set contenant le nouveau plugin avec ses réglages par défaut (défaut : le set re-sauvegardé du mode none)")
    vf.add_argument("--nth", type=int, default=0, help="n-ième instance si le plugin apparaît plusieurs fois (défaut : 0)")
    ap_ = sub.add_parser("app", help="lancer l'interface ReAble (serveur local 127.0.0.1)")
    ap_.add_argument("--port", type=int, default=3000)
    ap_.add_argument("--browser", action="store_true", help="ouvrir dans le navigateur au lieu de la fenêtre native")
    tp = sub.add_parser("templates", help="bibliothèque de gabarits VST3 (devices écrits par Live, gardés pour les analyses)")
    tp.add_argument("action", choices=["scan", "list"])
    tp.add_argument("target", nargs="?", help="scan : dossier ou set à mémoriser")
    pb = sub.add_parser("probe", help="classer le conteneur d'état de chaque plugin d'un dossier (extension : plugins inconnus)")
    pb.add_argument("target")
    pb.add_argument("--min", type=int, default=3, help="n'afficher que les plugins utilisés au moins N fois")
    args = ap.parse_args(argv)

    if args.cmd == "plugins":
        return _plugins_cmd(args)

    if args.cmd == "verify":
        return _verify_cmd(args)

    if args.cmd == "templates":
        from . import templates as tl
        if args.action == "list":
            for f in tl.library_files():
                print(f.stem)
            print(f"\n{len(tl.library_files())} gabarit(s) dans {tl.library_dir()}")
            return 0
        t = Path(args.target or ".").expanduser()
        added = tl.remember([t] if t.is_file() else alsfile.find_sets(t))
        print(f"{len(added)} gabarit(s) ajouté(s) ou mis à jour : {', '.join(sorted(added)) or '—'}")
        return 0

    if args.cmd == "app":
        if args.browser:
            from .app.server import main as app_main
            return app_main(args.port, open_browser=True)
        try:
            from .app.window import run as window_run
        except ImportError:
            print("pywebview n'est pas installé : `pip install pywebview`, ou lancez avec --browser.")
            return 2
        return window_run(args.port if args.port != 3000 else None)

    if args.cmd == "probe":
        from .probe import KINDS, probe
        t = Path(args.target).expanduser()
        rows = probe([t] if t.is_file() else alsfile.find_sets(t))
        print(f"{'Plugin':34} {'Formats':22} {'Conteneur':11} {'Instances':>9}  Statut")
        for r in rows:
            n = sum(r.formats.values())
            if n < args.min:
                continue
            kind = max(r.kinds, key=r.kinds.get)
            print(f"{r.name[:33]:34} {','.join(f'{k}:{v}' for k, v in sorted(r.formats.items())):22} {kind:11} {n:>9}  {r.status}")
        return 0

    if args.cmd == "restore":
        from .api import restore
        dst, r = restore(args.set_file, args.out, args.original)
        for w in r.warnings:
            print(f"⚠️ {w}")
        if dst is None:
            return 2
        print(f"{r.restored} device(s) restauré(s) → {dst}")
        return 0

    if args.cmd == "convert":
        return _convert_cmd(args)

    if args.cmd == "rewrite":
        from .rewrite import rewrite_file
        dst, res = rewrite_file(Path(args.set_file).expanduser(), args.plugin, args.out, args.template,
                                  args.source_format, args.target_name, args.suffix,
                                  not args.no_note, not args.no_embed)
        for w in res.warnings:
            print(f"⚠️ {w}")
        if dst is None:
            return 2
        print(f"{res.converted} device(s) converti(s) → {dst}")
        return 0

    if args.cmd == "compare":
        return _compare(Path(args.set_file).expanduser(), args.plugin)

    target = Path(args.target).expanduser()
    files = [target] if target.is_file() else alsfile.find_sets(target, args.include_packs)
    if not files:
        print("Aucun fichier .als trouvé.")
        return 1
    inv = inventory.scan_installed([Path(p).expanduser() for p in args.plugins_root] if args.plugins_root else None)
    reports = []
    for f in files:
        print(f"→ {f}")
        try:
            r = extract(f)
        except Exception as e:
            print(f"   ⚠️ illisible : {e}")
            continue
        inventory.check(r.plugins, inv)
        reports.append(r)
    out = Path(args.out) if args.out else (target if target.is_dir() else target.parent)
    md, js = report.write(reports, str(target), out)
    missing = sum(p.install_status == "manquant" for r in reports for p in r.plugins)
    print(f"\n{len(reports)} set(s), {sum(len(r.plugins) for r in reports)} plugin(s), {missing} manquant(s)")
    print(f"Rapport : {md}\nDonnées complètes : {js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
