"""Réécriture AU -> VST3 d'un plugin d'un set Live (prototype, plugins NI à `vstdata`).

Principe (voir docs/EVALUATION.md §4) :
- le device VST3 vient d'un **gabarit** copié d'un vrai set (jamais de XML inventé) ;
- l'état du plugin (`vstdata` de l'AU) est injecté dans `ProcessorState` ;
- les Id d'automation de l'AU sont repris, pour que les automations restent branchées :
  par position pour le device lui-même, par nom pour les paramètres configurés ;
- tous les autres Id du gabarit reçoivent des Id neufs (ils doivent rester uniques).
L'original n'est jamais modifié : le résultat est écrit dans un nouveau fichier.
"""
from __future__ import annotations

import binascii
import copy
import hashlib
import plistlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from datetime import datetime, timezone

from . import alsfile, trace
from .adapters import adapt_state, effective_mode, state_note
from .registry import definition_of
from .decoders import decode_state
from .extract import fourcc

TARGET_TAGS = ("AutomationTarget", "ModulationTarget")
ID_TAGS = TARGET_TAGS + ("Pointee",)   # types de base ; voir is_pointee() pour l'ensemble


def is_pointee(tag: str) -> bool:
    """Éléments dont l'Id vit dans l'espace d'Id global « Pointee » de Live (uniques dans tout le set) :
    Pointee, *Target (AutomationTarget, ModulationTarget, VolumeModulationTarget…) et ControllerTargets.N."""
    if tag == "Target":                  # <Target Value="AudioIn/None"/> : routage, jamais d'Id
        return False
    return tag == "Pointee" or tag.endswith("Target") or tag.startswith("ControllerTargets.")
HEX_LINE = 80


@dataclass
class RewriteResult:
    converted: int = 0
    warnings: list[str] = field(default_factory=list)
    devices: list[dict] = field(default_factory=list)   # une entrée par device converti


def norm_param_name(name: str) -> str:
    """« 01 LFO Amt » (VST3) et « LFO Amt » (AU) désignent le même paramètre."""
    return re.sub(r"^\d+\s+", "", name).strip().lower()


def hex_block(data: bytes, indent: str) -> str:
    """Hexadécimal majuscule en lignes de 80 caractères, comme Live l'écrit."""
    h = binascii.hexlify(data).decode().upper()
    lines = [h[i:i + HEX_LINE] for i in range(0, len(h), HEX_LINE)]
    return "\n" + "\n".join(indent + ln for ln in lines) + "\n" + indent[:-1]


def _name(info: ET.Element | None) -> str:
    if info is None:
        return ""
    n = info.find("PlugName") if info.tag == "VstPluginInfo" else info.find("Name")
    return n.get("Value", "") if n is not None else ""


def _hex_bytes(el: ET.Element) -> bytes:
    return binascii.unhexlify(re.sub(r"\s", "", el.text or ""))


def au_state(dev: ET.Element) -> bytes | None:
    """`vstdata` du plist AU (clé utilisée par NI), ou None."""
    buf = dev.find(".//AuPreset/Buffer")
    if buf is None or not (buf.text or "").strip():
        return None
    try:
        return plistlib.loads(_hex_bytes(buf)).get("vstdata") or None
    except Exception:
        return None


def source_id(dev: ET.Element, source_format: str) -> str:
    if source_format == "AU":
        i = dev.find(".//AuPluginInfo")
        return "/".join(fourcc(i.find(t).get("Value")) for t in
                        ("ComponentType", "ComponentSubType", "ComponentManufacturer"))
    if source_format == "VST3":
        i = dev.find(".//Vst3PluginInfo")
        try:
            return "".join(f"{int(i.find(f'Uid/Fields.{k}').get('Value')) & 0xFFFFFFFF:08X}" for k in range(4))
        except (AttributeError, ValueError):
            return ""
    i = dev.find(".//VstPluginInfo")
    return fourcc(i.find("UniqueId").get("Value")) if i is not None and i.find("UniqueId") is not None else ""


def vst3_state(dev: ET.Element) -> bytes | None:
    ps = dev.find(".//Vst3Preset/ProcessorState")
    if ps is None or not (ps.text or "").strip():
        return None
    return _hex_bytes(ps)


def vst2_state(dev: ET.Element) -> bytes | None:
    """Tampon d'état d'un device VST2 (conteneur NI : `<taille> 00000000 01000000 …`)."""
    buf = dev.find(".//VstPreset/Buffer")
    if buf is None or not (buf.text or "").strip():
        return None
    return _hex_bytes(buf)


def _param_elements(dev: ET.Element) -> set[int]:
    pl = dev.find("ParameterList")
    return {id(x) for x in pl.iter()} if pl is not None else set()


def _device_targets(dev: ET.Element) -> list[ET.Element]:
    inside = _param_elements(dev)
    return [e for e in dev.iter() if e.tag in TARGET_TAGS and id(e) not in inside]


def _all_ids(root: ET.Element) -> list[int]:
    out = []
    for e in root.iter():
        if is_pointee(e.tag) and e.get("Id", "").lstrip("-").isdigit():
            out.append(int(e.get("Id")))
    return out


def _find_devices(root: ET.Element, tag: str, info_tag: str, name: str) -> list[ET.Element]:
    return [d for d in root.iter(tag) if _name(d.find(f".//{info_tag}")).lower() == name.lower()]


TRACK_ID_TAGS = ("MidiTrack", "AudioTrack", "GroupTrack", "ReturnTrack")


def track_of(el: ET.Element, parents: dict) -> ET.Element | None:
    n = parents.get(el)
    while n is not None and not n.tag.endswith("Track"):
        n = parents.get(n)
    return n


def fresh_ids(el: ET.Element, next_id: list[int]) -> dict[str, str]:
    """Donne des Id neufs à tous les Id globaux de `el` et suit les enveloppes internes (PointeeId)."""
    mapping: dict[str, str] = {}
    for e in el.iter():
        if is_pointee(e.tag) and e.get("Id", "").lstrip("-").isdigit():
            old = e.get("Id")
            if old not in mapping:
                mapping[old] = str(next_id[0])
                next_id[0] += 1
            e.set("Id", mapping[old])
    for pid in el.iter("PointeeId"):
        if pid.get("Value") in mapping:
            pid.set("Value", mapping[pid.get("Value")])
    return mapping


def _set_track_name(trk: ET.Element, fn) -> None:
    """Applique `fn` au nom de la piste (nom choisi, sinon nom automatique de Live) et l'écrit partout."""
    usr, eff = trk.find("Name/UserName"), trk.find("Name/EffectiveName")
    base = (usr.get("Value", "") if usr is not None else "") or (eff.get("Value", "") if eff is not None else "")
    new = fn(base)
    for el in (usr, eff):
        if el is not None:
            el.set("Value", new)


def set_track_active(trk: ET.Element, active: bool) -> None:
    sp = trk.find("DeviceChain/Mixer/Speaker/Manual")
    if sp is not None:
        sp.set("Value", "true" if active else "false")


def duplicate_track(root: ET.Element, trk: ET.Element, parents: dict, next_id: list[int],
                    mute_original: bool, original_suffix: str) -> ET.Element:
    """Copie la piste juste après l'originale (Id neufs partout) ; l'originale est mutée et suffixée."""
    cp = copy.deepcopy(trk)
    fresh_ids(cp, next_id)
    tid = max(int(t.get("Id", "0")) for tag in TRACK_ID_TAGS for t in root.iter(tag)) + 1
    cp.set("Id", str(tid))
    cp.tail = trk.tail
    parent = parents[trk]
    parent.insert(list(parent).index(trk) + 1, cp)
    parents[cp] = parent
    for node in cp.iter():
        for c in node:
            parents[c] = node
    if mute_original:
        set_track_active(trk, False)
    if original_suffix:
        _set_track_name(trk, lambda n: n if n.endswith(original_suffix) else n + original_suffix)
    return cp


def transfer_ids(src: ET.Element, dst: ET.Element, fixed: set[int], warnings: list[str]) -> None:
    """Reprend sur `dst` les Id d'automation de `src` : device par position, paramètres configurés par nom."""
    dst.find("Pointee").set("Id", src.find("Pointee").get("Id"))
    fixed.add(id(dst.find("Pointee")))
    t_src, t_dst = _device_targets(src), _device_targets(dst)
    if len(t_src) == len(t_dst):
        for a, b in zip(t_src, t_dst):
            b.set("Id", a.get("Id"))
            fixed.add(id(b))
    else:
        warnings.append(f"cibles du device : {len(t_src)} ≠ {len(t_dst)}, Id neufs")
    slots = {}
    for p in dst.find("ParameterList"):
        n = norm_param_name(p.find("ParameterName").get("Value", ""))
        if n:
            slots[n] = p
    for p in src.find("ParameterList"):
        raw = p.find("ParameterName").get("Value", "")
        if not raw:
            continue
        d = slots.get(norm_param_name(raw))
        if d is None:
            warnings.append(f"paramètre « {raw} » absent du gabarit : automations perdues")
            continue
        for tag in TARGET_TAGS:
            d.find(f"ParameterValue/{tag}").set("Id", p.find(f"ParameterValue/{tag}").get("Id"))
            fixed.add(id(d.find(f"ParameterValue/{tag}")))
        d.find("ParameterValue/Manual").set("Value", p.find("ParameterValue/Manual").get("Value"))


def _convert(au: ET.Element, template: ET.Element, state: bytes, next_id: list[int],
             warnings: list[str], copy_controller: bool = False) -> ET.Element:
    new = copy.deepcopy(template)
    fixed: set[int] = set()   # éléments dont l'Id vient de l'AU

    transfer_ids(au, new, fixed, warnings)

    # 3. Tout le reste reçoit des Id neufs
    for e in new.iter():
        if is_pointee(e.tag) and e.get("Id") is not None and id(e) not in fixed:
            e.set("Id", str(next_id[0]))
            next_id[0] += 1

    # 4. État du plugin
    ps = new.find(".//ProcessorState")
    indent = "\t" * 13
    m = re.match(r"\n(\t*)", ps.text or "")
    if m:
        indent = m.group(1)
    ps.text = hex_block(state, indent) if state else ""
    # iZotope (Ozone 8/9 en VST3) range le même état dans ControllerState ; Ozone 10 le laisse vide
    new.find(".//ControllerState").text = hex_block(state, indent) if (copy_controller and state) else ""

    # 5. Réglages propres à la piste
    for tag in ("UserName",):
        new.find(tag).set("Value", au.find(tag).get("Value"))
    new.find("Annotation").set("Value", au.find("Annotation").get("Value", ""))
    new.find("On/Manual").set("Value", au.find("On/Manual").get("Value"))
    new.set("Id", au.get("Id"))
    new.tail = au.tail
    return new


SOURCES = {
    "AU": ("AuPluginDevice", "AuPluginInfo", au_state),
    "VST2": ("PluginDevice", "VstPluginInfo", vst2_state),
    "VST3": ("PluginDevice", "Vst3PluginInfo", vst3_state),   # mise à niveau : Ozone 8 VST3 → Ozone 10 VST3
}


def rewrite_tree(tree: ET.ElementTree, plugin: str,
                 template_tree: ET.ElementTree | None = None,
                 source_format: str = "AU", target_name: str | None = None,
                 write_note: bool = True, embed_original: bool = True,
                 max_embed_bytes: int = 100_000, source_file: str = "",
                 replace_mode: str = "replace", mute_original: bool = True,
                 original_suffix: str = " [original]", state_mode: str = "transfer",
                 old_device_suffix: str = " [ancien]", copy_controller_state: bool = False) -> RewriteResult:
    """Convertit les devices `plugin` (format `source_format`) en VST3 `target_name` (défaut : même nom).

    replace_mode : « replace » (remplace sur place), « duplicate_track » (copie de la piste, l'originale
    est mutée ; seul moyen de garder un instrument), « keep_device » (effets : l'ancien device reste,
    désactivé, après le nouveau). Un instrument demandé en keep_device passe en duplicate_track.
    """
    root = tree.getroot()
    res = RewriteResult()
    dev_tag, info_tag, get_state = SOURCES[source_format]
    target_name = target_name or plugin
    srcs = _find_devices(root, dev_tag, info_tag, plugin)
    if not srcs:
        res.warnings.append(f"aucun « {plugin} » en {source_format} dans ce set")
        return res
    src = (template_tree or tree).getroot()
    tpls = _find_devices(src, "PluginDevice", "Vst3PluginInfo", target_name)
    if not tpls:
        res.warnings.append(f"aucun gabarit VST3 « {target_name} » (charger le plugin en VST3 dans un set, "
                            "puis le donner avec --template)")
        return res
    template = tpls[0]
    tpl_state = _hex_bytes(template.find(".//ProcessorState"))
    is_instrument = (template.find(".//Vst3PluginInfo/DeviceType") is not None
                     and template.find(".//Vst3PluginInfo/DeviceType").get("Value") == "1")

    copy_controller_state = copy_controller_state or any(
        d is not None and d.copy_controller_state for d in (definition_of(plugin), definition_of(target_name)))
    nxt = next(root.iter("NextPointeeId"))
    next_id = [max(int(nxt.get("Value")), max(_all_ids(root)) + 1)]
    schema = attribute_schema(root, src)
    parents = {c: p for p in root.iter() for c in p}
    per_track: dict[ET.Element, list[ET.Element]] = {}
    for d in srcs:
        t = track_of(d, parents)
        if t is not None:
            per_track.setdefault(t, []).append(d)
    dups: dict[ET.Element, tuple[ET.Element, list[ET.Element]]] = {}
    for dev in srcs:
        state = get_state(dev)
        if state is None:
            res.warnings.append("état sans données exploitables (plugin non NI ?) : device ignoré")
            continue
        mode_used, mode_why = effective_mode(plugin, state_mode)
        if mode_why and mode_why not in res.warnings:
            res.warnings.append(mode_why)
        new_state, why = adapt_state(plugin, state, tpl_state, mode_used)
        if new_state is None:
            res.warnings.append(f"{why} : device ignoré")
            continue
        mode = replace_mode
        trk = track_of(dev, parents)
        if mode == "keep_device" and is_instrument:
            mode = "duplicate_track"
        if mode == "duplicate_track" and (trk is None or trk.tag not in ("MidiTrack", "AudioTrack")):
            if is_instrument:
                res.warnings.append("duplication impossible hors piste MIDI/audio : remplacement sur place")
                mode = "replace"
            else:   # piste principale, retour, groupe : on garde l'ancien effet, désactivé, à côté du nouveau
                res.warnings.append("piste non dupliquable (principale, retour ou groupe) : "
                                    "ancien effet conservé et désactivé")
                mode = "keep_device"
        n_before = len(res.warnings)
        target_dev, original_track_id, track_id = dev, "", ""
        if mode == "duplicate_track":
            if trk not in dups:
                cp = duplicate_track(root, trk, parents, next_id, mute_original, original_suffix)
                dups[trk] = (cp, _find_devices(cp, dev_tag, info_tag, plugin))
            cp, copy_devs = dups[trk]
            target_dev = copy_devs[per_track[trk].index(dev)]
            original_track_id, track_id = trk.get("Id", ""), cp.get("Id", "")
        new = _convert(target_dev, template, new_state, next_id, res.warnings, copy_controller_state)
        old_pointee = ""
        if mode == "keep_device":
            fresh_ids(target_dev, next_id)                     # l'ancien device perd ses Id (repris par le nouveau)
            target_dev.find("On/Manual").set("Value", "false")  # ... et est désactivé
            un = target_dev.find("UserName")
            if un is not None and old_device_suffix:
                un.set("Value", (un.get("Value") or plugin) + old_device_suffix)
            old_pointee = target_dev.find("Pointee").get("Id")
        try:
            preset = (decode_state(state, plugin) or ("",))[0] or ""
            if preset.strip().lower() in ("presets", "default", "<default>"):   # « aucun preset chargé »
                preset = ""
        except Exception:
            preset = ""
        info = {"v": 2, "tool": "ReAble", "when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source_format": source_format, "source_name": plugin, "source_id": source_id(dev, source_format),
                "target_name": target_name, "preset": preset, "replace_mode": mode, "state_mode": mode_used,
                "old_pointee": old_pointee, "old_device_suffix": old_device_suffix if mode == "keep_device" else "",
                "original_track_id": original_track_id, "track_id": track_id,
                "original_suffix": original_suffix if mode == "duplicate_track" else "",
                "state_sha256": hashlib.sha256(state).hexdigest(),
                "state_bytes": len(state), "warnings": res.warnings[n_before:]}
        if write_note:
            old = target_dev.find("Annotation")
            user = trace.strip_note(old.get("Value", "")) if old is not None else ""
            info["pointee"] = target_dev.find("Pointee").get("Id") if target_dev.find("Pointee") is not None else ""
            info["source_file"] = source_file
            if embed_original and mode == "replace":
                packed = trace.pack_original(dev)
                if len(packed) <= max_embed_bytes:
                    info["original_gz_b64"] = packed
                else:
                    res.warnings.append(f"original trop gros pour la note ({len(packed) // 1000} Ko) : "
                                        "restauration depuis le fichier d'origine")
            new.find("Annotation").set("Value", trace.build_note(user, info))
        res.devices.append({k: v for k, v in info.items() if k != "original_gz_b64"})
        parent = parents[target_dev]
        if mode == "keep_device":
            siblings = [int(c.get("Id")) for c in parent if c.get("Id", "").lstrip("-").isdigit()]
            new.set("Id", str(max(siblings, default=-1) + 1))      # Id unique dans la liste de devices
            parent.insert(list(parent).index(target_dev), new)
            new.tail = target_dev.tail
        else:
            parent[list(parent).index(target_dev)] = new
        parents[new] = parent
        for node in new.iter():
            for c in node:
                parents[c] = node
        res.converted += 1
    nxt.set("Value", str(next_id[0]))
    res.warnings += check_tree(root) + check_schema(root, schema)
    return res


def attribute_schema(*roots: ET.Element) -> dict[str, set[str]]:
    """Pour chaque type d'élément, l'ensemble des attributs vus dans les sets de référence."""
    schema: dict[str, set[str]] = {}
    for root in roots:
        for e in root.iter():
            schema.setdefault(e.tag, set()).update(e.attrib)
    return schema


def check_schema(root: ET.Element, schema: dict[str, set[str]]) -> list[str]:
    """Signale tout élément portant un attribut que son type n'a jamais eu dans les sets de référence
    (Live refuse le fichier : « Unknown attribute »)."""
    bad: dict[str, set[str]] = {}
    for e in root.iter():
        extra = set(e.attrib) - schema.get(e.tag, set(e.attrib))
        if extra:
            bad.setdefault(e.tag, set()).update(extra)
    return [f"Attribut inconnu : <{t}> {sorted(a)}" for t, a in sorted(bad.items())]


def check_list_ids(root: ET.Element) -> list[str]:
    """Dans une liste, les enfants portant un attribut Id doivent avoir des Id distincts (Live : « Non-unique list ids »).
    Règle vérifiée sur les 365 sets d'origine du corpus : aucun écart."""
    bad = []
    for parent in root.iter():
        ids = [c.get("Id") for c in parent if c.get("Id") is not None]
        dup = sorted({i for i in ids if ids.count(i) > 1}) if len(ids) != len(set(ids)) else []
        if dup:
            bad.append(f"Id de liste en double dans <{parent.tag}> : {dup[:5]}")
    return bad


def check_tree(root: ET.Element) -> list[str]:
    """Vérifie l'unicité des Id et que chaque enveloppe vise un Id existant."""
    warnings = check_list_ids(root)
    ids = _all_ids(root)
    dup = {i for i in ids if ids.count(i) > 1} if len(ids) < 20000 else set()
    if len(set(ids)) != len(ids):
        dup = {i for i in set(ids) if ids.count(i) > 1}
        warnings.append(f"Id en double : {sorted(dup)[:10]}")
    known = {str(i) for i in ids}
    dangling = {e.get("Value") for e in root.iter("PointeeId")} - known
    if dangling:
        warnings.append(f"enveloppes sans cible : {sorted(dangling)[:10]}")
    return warnings


def rewrite_file(src: str | Path, plugin: str, out_dir: str | Path | None = None,
                 template: str | Path | None = None, source_format: str = "AU",
                 target_name: str | None = None, suffix: str = "", write_note: bool = True,
                 embed_original: bool = True, max_embed_bytes: int = 100_000,
                 replace_mode: str = "replace") -> tuple[Path | None, RewriteResult]:
    src = Path(src)
    tree = alsfile.load(src)
    res = rewrite_tree(tree, plugin, alsfile.load(template) if template else None,
                       source_format, target_name, write_note, embed_original,
                       max_embed_bytes, src.name, replace_mode)
    if not res.converted:
        return None, res
    out = Path(out_dir) if out_dir else src.parent
    out.mkdir(parents=True, exist_ok=True)
    dst = out / f"{src.stem} [ReAble{suffix}]{src.suffix}"
    if dst.resolve() == src.resolve():
        raise ValueError("refus d'écraser l'original")
    alsfile.save(tree, dst)
    return dst, res
