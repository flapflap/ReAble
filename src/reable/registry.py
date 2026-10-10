"""Registre des définitions de plugins : ce que ReAble sait (ou a appris) sur chaque plugin.

Les définitions ne sont PAS dans le dépôt de code : elles vivent dans un dépôt public séparé (reable-definitions).
Couches, la dernière gagnant en cas d'identifiant commun :
  1. instantané livré avec une version de ReAble (src/reable/definitions_snapshot/, généré à la publication, absent du dépôt) ;
  2. dépôt de définitions cloné : `<dossier utilisateur>/definitions-repo/definitions/` (voir `sync`), et les dossiers
     listés dans `settings.json` → `definitions_dirs` ; puis `shared/` (fichiers importés) ;
  3. définitions locales de l'utilisateur (`<dossier utilisateur>/definitions/`) : jamais envoyées sans action explicite.

Statuts : « validated » (autorisé par défaut), « experimental » (BLOQUÉ par défaut : à activer explicitement),
« unsupported » (aucun adaptateur : détection et fiche de recréation seulement).
Dossier utilisateur : ~/Library/Application Support/ReAble (migré depuis l'ancien dossier PlugRescue), ou $REABLE_HOME.
"""
from __future__ import annotations

import json
import os
import platform
import re
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

ADAPTERS = ("container-copy", "izotope", "none")
STATUSES = ("validated", "experimental", "unsupported")
SNAPSHOT_DIR = Path(__file__).parent / "definitions_snapshot"
DEFAULT_LIBRARY_URL = "https://github.com/flapflap/ReAble-library"      # dépôt public des définitions (privé tant que le projet n'est pas publié)
DEV_DEFINITIONS_CANDIDATES = [Path(__file__).resolve().parents[3] / n / "definitions"
                              for n in ("ReAble-library", "PlugRescue-definitions")]   # développement : dépôt voisin du dépôt de code


_ACRONYMS = {"fm8": "FM8", "wlm": "WLM", "t-racks": "T-RackS", "ik": "IK", "eq": "EQ", "ni": "NI", "pro-q": "Pro-Q", "pro-c": "Pro-C",
             "pro-l": "Pro-L", "pro-mb": "Pro-MB"}


def pretty_name(ident: str) -> str:
    """Nom lisible d'un identifiant de définition : « fabfilter pro-q » -> « FabFilter Pro-Q »."""
    words = []
    for w in ident.replace("_", " ").split():
        low = w.lower()
        if low in _ACRONYMS:
            words.append(_ACRONYMS[low])
        elif low == "fabfilter":
            words.append("FabFilter")
        else:
            words.append("-".join(part.capitalize() for part in w.split("-")))
    return " ".join(words)


@dataclass
class Definition:
    id: str
    match: list[str]
    vendor: str = ""
    adapter: str | None = None
    decoder: str | None = None
    status: str = "experimental"
    validated: list[dict] = field(default_factory=list)
    notes: str = ""
    preferred_state_mode: str = "transfer"
    state_transfer_from: list[str] = field(default_factory=list)   # versions sources dont l'état est repris (vide = toutes)
    copy_controller_state: bool = False   # écrire aussi l'état dans ControllerState (requis par Ozone 10)
    title: str = ""                  # nom lisible (facultatif) ; sinon déduit de l'identifiant
    source: str = "intégré"          # intégré | partagé | utilisateur

    def matches(self, name: str) -> bool:
        n = name.lower().strip()
        return any(re.search(p, n) for p in self.match)

    def transfers_state(self, source_name: str) -> bool:
        """L'état de ce plugin source est-il repris par la version cible ? (liste vide = oui pour toutes les versions)"""
        if not self.state_transfer_from:
            return True
        n = source_name.lower().strip()
        return any(re.search(p, n) for p in self.state_transfer_from)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("source")
        return d

    def display_name(self) -> str:
        return self.title or pretty_name(self.id)


def user_dir() -> Path:
    env = os.environ.get("REABLE_HOME") or os.environ.get("PLUGRESCUE_HOME")
    if env:
        return Path(env).expanduser()
    base = Path.home() / "Library/Application Support"
    new, old = base / "ReAble", base / "PlugRescue"
    if not new.exists() and old.is_dir():          # migration unique depuis l'ancien nom : réglages, gabarits, définitions
        try:
            old.rename(new)
        except OSError:
            return old
    return new


def settings() -> dict:
    p = user_dir() / "settings.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(data: dict) -> None:
    user_dir().mkdir(parents=True, exist_ok=True)
    (user_dir() / "settings.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def _load_dir(d: Path, source: str) -> list[Definition]:
    out: list[Definition] = []
    for f in sorted(d.rglob("*.json")) if d.is_dir() else []:
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for item in doc.get("definitions", []):
            try:
                known = {k: v for k, v in item.items() if k in Definition.__dataclass_fields__ and k != "source"}
                out.append(Definition(**known, source=source))
            except TypeError:
                continue
    return out


def load_all() -> list[Definition]:
    """Toutes les définitions, la plus prioritaire d'abord (utilisateur > partagé > intégré)."""
    layers = [(SNAPSHOT_DIR, "intégré"), (user_dir() / "definitions-repo" / "definitions", "partagé")]
    for d in settings().get("definitions_dirs", []):
        layers.append((Path(d).expanduser(), "partagé"))
    layers.append((user_dir() / "shared", "partagé"))
    layers.append((user_dir() / "definitions", "utilisateur"))
    merged: dict[str, Definition] = {}
    for d, source in layers:
        for df in _load_dir(d, source):
            merged[df.id] = df              # la couche suivante remplace l'identifiant précédent
    if not merged:                          # développement : dépôt de définitions voisin du dépôt de code
        for cand in DEV_DEFINITIONS_CANDIDATES:
            for df in _load_dir(cand, "partagé"):
                merged[df.id] = df
    ordered = list(merged.values())
    prio = {"utilisateur": 0, "partagé": 1, "intégré": 2}
    return sorted(ordered, key=lambda x: prio[x.source])


def definition_of(name: str) -> Definition | None:
    for d in load_all():
        if d.matches(name):
            return d
    return None


def family_of(name: str) -> str | None:
    d = definition_of(name)
    return d.id if d else None


def allowed_families() -> frozenset[str]:
    """Familles converties par défaut : adaptateur présent ET statut « validated »."""
    return frozenset(d.id for d in load_all() if d.adapter and d.status == "validated")


def adapter_of(name: str) -> str | None:
    d = definition_of(name)
    return d.adapter if d else None


# ----------------------------------------------------------------------------- écriture (utilisateur)

def _user_file() -> Path:
    return user_dir() / "definitions" / "user.json"


def _read_user() -> list[dict]:
    try:
        return json.loads(_user_file().read_text(encoding="utf-8")).get("definitions", [])
    except (OSError, ValueError):
        return []


def _write_user(items: list[dict]) -> None:
    _user_file().parent.mkdir(parents=True, exist_ok=True)
    _user_file().write_text(json.dumps({"schema": "reable-definitions/1", "definitions": items},
                                       ensure_ascii=False, indent=1), encoding="utf-8")


def add_definition(id_: str, match: list[str], adapter: str | None, vendor: str = "", notes: str = "") -> Definition:
    """Crée (ou remplace) une définition de l'utilisateur ; elle démarre « experimental » donc bloquée."""
    if adapter is not None and adapter not in ADAPTERS:
        raise ValueError(f"adaptateur inconnu : {adapter} (choix : {', '.join(ADAPTERS)})")
    for p in match:
        re.compile(p)                       # lève re.error si le motif est invalide
    d = Definition(id_, match, vendor, adapter, None, "experimental" if adapter else "unsupported", [], notes,
                   source="utilisateur")
    items = [i for i in _read_user() if i.get("id") != id_] + [d.to_dict()]
    _write_user(items)
    return d


def record_validation(id_: str, result: str, variant: str = "transfer", live_version: str = "", note: str = "") -> Definition:
    """Enregistre le résultat d'un test dans Live. `ok` → « validated » pour cet utilisateur ; `ko` → reste bloqué."""
    if result not in ("ok", "ko"):
        raise ValueError("résultat : ok ou ko")
    base = next((d for d in load_all() if d.id == id_), None)
    if base is None:
        raise KeyError(f"définition inconnue : {id_}")
    rec = {"live": live_version, "date": date.today().isoformat(), "variant": variant, "result": result,
           "by": "utilisateur", "note": note}
    item = base.to_dict()
    item["validated"] = list(base.validated) + [rec]
    if result == "ok" and base.adapter:
        item["status"] = "validated"
        item["preferred_state_mode"] = variant
    elif result == "ko" and base.status == "validated":
        item["status"] = "experimental"     # un échec retire la confiance locale
    items = [i for i in _read_user() if i.get("id") != id_] + [item]
    _write_user(items)
    return next(d for d in load_all() if d.id == id_)


# ----------------------------------------------------------------------------- partage et bêta

def export_bundle(beta: bool = False) -> dict:
    """Définitions de l'utilisateur (et leurs validations) dans un fichier à partager.

    `beta` : version minimale et anonyme pour le programme bêta — aucun chemin, aucun nom de set ni de piste ;
    seulement le plugin, l'adaptateur, la variante testée, le résultat, les versions de Live/macOS/ReAble."""
    items = _read_user()
    meta = {"schema": "reable-beta/1" if beta else "reable-definitions/1",
            "reable": _version(), "macos": platform.mac_ver()[0] or platform.platform(), "python": sys.version.split()[0]}
    if beta:
        cfg = settings().setdefault("beta", {})
        meta["contributor"] = cfg.get("contributor_id") or "anonyme"
        meta["results"] = [{"plugin": i["id"], "match": i.get("match", []), "vendor": i.get("vendor", ""),
                            "adapter": i.get("adapter"), "status": i.get("status"),
                            "validations": [{k: v.get(k, "") for k in ("live", "date", "variant", "result")}
                                            for v in i.get("validated", []) if v.get("by") == "utilisateur"]}
                           for i in items]
    else:
        meta["definitions"] = items
    return meta


def import_bundle(path: str | Path) -> int:
    """Copie des définitions partagées dans `<dossier utilisateur>/shared/` (couche « partagé »)."""
    doc = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    defs = doc.get("definitions") or []
    if not defs:
        raise ValueError("aucune définition dans ce fichier (un export bêta n'est pas importable)")
    dest = user_dir() / "shared"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"import-{uuid.uuid4().hex[:8]}.json").write_text(
        json.dumps({"schema": "reable-definitions/1", "definitions": defs}, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(defs)


def set_beta(enabled: bool) -> dict:
    s = settings()
    cfg = s.setdefault("beta", {})
    cfg["enabled"] = enabled
    if enabled and not cfg.get("contributor_id"):
        cfg["contributor_id"] = "beta-" + uuid.uuid4().hex[:10]       # pseudonyme aléatoire, sans lien avec l'identité
    save_settings(s)
    return cfg


def _version() -> str:
    try:
        from importlib.metadata import version
        return version("reable")
    except Exception:
        return "dev"


# ----------------------------------------------------------------------------- dépôt de définitions

def configure(repo_url: str | None = None, definitions_dir: str | None = None) -> dict:
    """URL du dépôt de définitions (pour `sync`) et/ou dossier local de définitions (ex. un clone de travail)."""
    s = settings()
    if repo_url:
        s["definitions_repo"] = repo_url
    if definitions_dir:
        dirs = [d for d in s.get("definitions_dirs", []) if d != definitions_dir] + [definitions_dir]
        s["definitions_dirs"] = dirs
    save_settings(s)
    return s


def sync(url: str | None = None) -> tuple[bool, str]:
    """Clone ou met à jour le dépôt de définitions dans `<dossier utilisateur>/definitions-repo`."""
    import subprocess
    url = url or settings().get("definitions_repo") or DEFAULT_LIBRARY_URL
    if not url:
        return False, ("aucune URL de dépôt de définitions : "
                       "`reable plugins config --repo-url <url>` ou `reable plugins sync --url <url>`")
    dest = user_dir() / "definitions-repo"
    try:
        if (dest / ".git").is_dir():
            cmd, cwd = ["git", "pull", "--ff-only", "--quiet"], dest
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            cmd, cwd = ["git", "clone", "--depth", "1", "--quiet", url, str(dest)], None
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"git indisponible ou délai dépassé : {e}"
    if r.returncode != 0:
        return False, r.stderr.strip() or "échec de git"
    return True, f"{len(_load_dir(dest / 'definitions', 'partagé'))} définition(s) disponible(s) dans {dest}"
