"""Extraction des pistes, plugins, presets, paramètres et automations d'un set."""
from __future__ import annotations

import binascii
import plistlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from . import alsfile
from .decoders import decode_state
from .model import Parameter, Plugin, SetReport

TRACK_TAGS = ("MidiTrack", "AudioTrack", "GroupTrack", "ReturnTrack", "MainTrack", "MasterTrack")
PLUGIN_TAGS = ("PluginDevice", "AuPluginDevice")
# Valeur sentinelle écrite par Live quand il ne connaît pas la valeur du paramètre
LIVE_PLACEHOLDER = 0.1234567687


def _val(el: ET.Element | None, path: str, default: str = "") -> str:
    if el is None:
        return default
    x = el.find(path)
    if x is None:
        return default
    return x.get("Value", default)


def _hex(el: ET.Element | None) -> bytes:
    if el is None or not (el.text or "").strip():
        return b""
    return binascii.unhexlify(re.sub(r"\s", "", el.text))


def fourcc(n: str | int) -> str:
    try:
        b = (int(n) & 0xFFFFFFFF).to_bytes(4, "big")
        return b.decode("latin-1") if all(32 <= c < 127 for c in b) else hex(int(n))
    except (ValueError, TypeError):
        return str(n)


def _track_name(t: ET.Element) -> str:
    if t.tag in ("MainTrack", "MasterTrack"):
        return "Main"
    return _val(t, "Name/EffectiveName") or _val(t, "Name/UserName") or t.tag


def _chain_path(dev: ET.Element, track: ET.Element, parents: dict) -> str:
    """Chemin lisible dans les racks : 'Rack > Chaîne > Device'."""
    parts = []
    node = parents.get(dev)
    while node is not None and node is not track:
        if node.tag.endswith("GroupDevice"):
            parts.append(_val(node, "UserName") or node.tag.replace("GroupDevice", " Rack"))
        elif node.tag.endswith("Branch"):
            parts.append(_val(node, "Name/EffectiveName") or "Chaîne")
        node = parents.get(node)
    return " > ".join(reversed(parts))


def _parameters(dev: ET.Element) -> list[Parameter]:
    out = []
    plist = dev.find("ParameterList")
    if plist is None:
        return out
    for p in plist:
        if not p.tag.startswith("Plugin"):
            continue
        name = _val(p, "ParameterName")
        pid = int(_val(p, "ParameterId", "-1") or -1)
        if pid < 0 and not name:
            continue  # emplacement vide (paramètre non configuré dans Live)
        manual = _val(p, "ParameterValue/Manual", "0")
        at = p.find("ParameterValue/AutomationTarget")
        mt = p.find("ParameterValue/ModulationTarget")
        try:
            v = float(manual)
        except ValueError:
            v = float("nan")
        if abs(v - LIVE_PLACEHOLDER) < 1e-9:
            v = float("nan")  # Live n'a jamais lu la valeur réelle
        out.append(Parameter(name=name, param_id=pid, value=v,
                             automation_target=at.get("Id") if at is not None else None,
                             modulation_target=mt.get("Id") if mt is not None else None))
    return out


def _plugin_from_device(dev: ET.Element, track_name: str, chain: str) -> Plugin | None:
    desc = dev.find("PluginDesc")
    if desc is None or len(desc) == 0:
        return None
    info = desc[0]
    p = Plugin(track=track_name, chain_path=chain, format="?", name="")
    p.user_name = _val(dev, "UserName")
    p.enabled = _val(dev, "On/Manual", "true") == "true"
    p.last_preset_file = _val(dev, "LastPresetRef/Value/FilePresetRef/FileRef/Path")
    raw = b""

    if info.tag == "AuPluginInfo":
        p.format = "AU"
        p.name = _val(info, "Name")
        p.manufacturer = _val(info, "Manufacturer")
        p.identifier = "/".join(fourcc(_val(info, k)) for k in
                                ("ComponentType", "ComponentSubType", "ComponentManufacturer"))
        buf = _hex(info.find("Preset/AuPreset/Buffer"))
        if buf:
            try:
                pl = plistlib.loads(buf)
                nm = pl.get("name", "")
                if nm and nm != "<none>":
                    p.preset_name, p.preset_source = nm, "AU preset (plist)"
                # Les plugins NI rangent leur état VST dans 'vstdata'
                raw = pl.get("vstdata") or pl.get("jucePluginState") or pl.get("data") or b""
            except Exception:
                raw = buf
    elif info.tag == "Vst3PluginInfo":
        p.format = "VST3"
        p.name = _val(info, "Name")
        fields = [_val(info, f"Uid/Fields.{i}") for i in range(4)]
        try:
            p.identifier = "".join(f"{int(f) & 0xFFFFFFFF:08X}" for f in fields)
        except ValueError:
            p.identifier = ""
        raw = _hex(info.find("Preset/Vst3Preset/ProcessorState"))
        nm = _val(info, "Preset/Vst3Preset/Name")
        if nm:
            p.preset_name, p.preset_source = nm, "Live (Vst3Preset/Name)"
    elif info.tag == "VstPluginInfo":
        p.format = "VST2"
        p.name = _val(info, "PlugName")
        p.identifier = fourcc(_val(info, "UniqueId"))
        raw = _hex(info.find("Preset/VstPreset/Buffer"))
        nm = _val(info, "Preset/VstPreset/Name")
        if nm:
            p.preset_name, p.preset_source = nm, "Live (VstPreset/Name)"
    else:
        p.format = info.tag
        p.name = _val(info, "Name") or info.tag

    p.state_bytes = len(raw)
    if raw:
        res = decode_state(raw, p.name)
        if res:
            preset, summary, full = res
            if preset:
                p.preset_name, p.preset_source = preset, "état interne du plugin"
            p.state_summary, p.state_full = summary, full
    p.parameters = _parameters(dev)
    return p


def _link_automation(root: ET.Element, plugins: list[Plugin]) -> None:
    """Relie les enveloppes (arrangement et clips) aux paramètres de plugins."""
    clip_targets: dict[str, int] = {}
    for env in root.iter("ClipEnvelope"):
        pid = _val(env, "EnvelopeTarget/PointeeId")
        clip_targets[pid] = clip_targets.get(pid, 0) + 1
    arr_only = {_val(env, "EnvelopeTarget/PointeeId") for env in root.iter("AutomationEnvelope")}
    for pl in plugins:
        for prm in pl.parameters:
            prm.automated = prm.automation_target in arr_only
            prm.clip_envelopes = clip_targets.get(prm.automation_target or "", 0) + \
                clip_targets.get(prm.modulation_target or "", 0)


def extract(path: str | Path) -> SetReport:
    tree = alsfile.load(path)
    root = tree.getroot()
    parents = {c: p for p in root.iter() for c in p}
    liveset = root.find("LiveSet")
    tracks: list[ET.Element] = []
    if liveset is not None:
        tr = liveset.find("Tracks")
        if tr is not None:
            tracks.extend(t for t in tr if t.tag in TRACK_TAGS)
        for tag in ("MainTrack", "MasterTrack"):
            t = liveset.find(tag)
            if t is not None:
                tracks.append(t)
    report = SetReport(path=str(path), live_version=alsfile.live_version(tree),
                       tracks=[_track_name(t) for t in tracks], plugins=[])
    for t in tracks:
        tname = _track_name(t)
        for dev in t.iter():
            if dev.tag not in PLUGIN_TAGS:
                continue
            try:
                pl = _plugin_from_device(dev, tname, _chain_path(dev, t, parents))
                if pl:
                    report.plugins.append(pl)
            except Exception as e:  # on continue le scan, on note l'erreur
                report.errors.append(f"{tname}: {e!r}")
    _link_automation(root, report.plugins)
    return report
