# -*- coding: utf-8 -*-
"""Сборщик CSF-модов (Custom Skills Framework) для базы перков.

CSF-моды НЕ используют AVIF-деревья. Структура:
  - NetScriptFramework\\Plugins\\CustomSkill.<Имя>.config.txt — описание дерева:
      Name = "..."; NodeN.PerkFile/PerkId/GridX/GridY/Links; NodeN.Enable
  - <мод>.esp — PERK-записи (FULL/DESC/CTDA), ссылки по локальному FormID из конфига.

Использование:
  python build_csf.py <папка_мода> <имя_в_базе> <выходной_json>
Пример:
  python build_csf.py "C:/MO2 Daminikov/mods/Draconic Nature perk tree" "Draconic Nature 1.4" out.json
"""
import json
import re
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scan_mod import iter_records, subrecs, classify_all, UNPACKED

def parse_config(cfg_path):
    """Парсит CustomSkill.*.config.txt -> (name, desc, nodes[{perkfile, perkid, x, y, links}])."""
    txt = cfg_path.read_text(encoding="utf-8", errors="replace")
    name_m = re.search(r'^Name\s*=\s*"([^"]*)"', txt, re.M)
    desc_m = re.search(r'^Description\s*=\s*"([^"]*)"', txt, re.M)
    name = name_m.group(1) if name_m else cfg_path.stem
    desc = desc_m.group(1) if desc_m else ""
    nodes = {}
    # NodeN.<Key> = value
    for m in re.finditer(r'^Node(\d+)\.(\w+)\s*=\s*(.*)$', txt, re.M):
        idx, key, val = int(m.group(1)), m.group(2), m.group(3).strip()
        nodes.setdefault(idx, {})[key] = val.strip('"')
    out = []
    for idx in sorted(nodes):
        n = nodes[idx]
        if str(n.get("Enable", "true")).lower() not in ("true", "1"):
            continue
        perkid = n.get("PerkId", "")
        if not perkid:
            continue
        try:
            local_id = int(perkid, 16) if perkid.lower().startswith("0x") else int(perkid)
        except ValueError:
            continue
        links = [int(x) for x in re.findall(r"\d+", n.get("Links", ""))]
        out.append({
            "node": idx,
            "perkfile": n.get("PerkFile", ""),
            "local_id": local_id,
            "x": float(n.get("X", 0) or 0) + int(float(n.get("GridX", 0) or 0)) * 100,
            "y": float(n.get("Y", 0) or 0) + int(float(n.get("GridY", 0) or 0)) * 100,
            "links": links,
        })
    return name, desc, out

def load_perks_from_esp(esp_path):
    """Все PERK из ESP по локальному FormID."""
    perks = {}
    for tag, fid, body in iter_records(str(esp_path)):
        if tag != "PERK":
            continue
        local = fid & 0xFFFFFF
        subs = subrecs(body)
        edid = name = desc = ""
        level = None
        num_ranks = 1
        prereq_gfids = []
        for t, v in subs:
            if t == "EDID":
                edid = v.rstrip(b"\x00").decode("latin1", "replace")
            elif t == "FULL":
                if len(v) != 4:
                    name = v.rstrip(b"\x00").decode("utf-8", "replace")
            elif t == "DESC":
                if len(v) != 4:
                    desc = v.rstrip(b"\x00").decode("utf-8", "replace")
            elif t == "DATA" and len(v) == 5:
                num_ranks = v[2]
            elif t == "CTDA" and len(v) >= 28:
                fn = struct.unpack_from("<H", v, 8)[0]
                p1 = struct.unpack_from("<I", v, 12)[0]
                fval = struct.unpack_from("<f", v, 4)[0]
                if fn == 277 and 6 <= p1 <= 23:
                    if level is None:
                        level = int(fval)
                elif fn == 448:
                    prereq_gfids.append(p1)
        perks[local] = {"edid": edid, "name": name, "desc": desc, "level": level,
                        "prereq_gfids": prereq_gfids, "num_ranks": num_ranks}
    return perks

def build(mod_dir, mod_label, out_path):
    mod_dir = Path(mod_dir)
    # 1. конфиг
    cfgs = list(mod_dir.glob("NetScriptFramework/Plugins/CustomSkill.*.config.txt"))
    cfgs += list(mod_dir.glob("NetScriptFramework/Plugins/CustomSkill.*.txt"))
    cfgs = list(dict.fromkeys(cfgs))
    if not cfgs:
        print("  КОНФИГ НЕ НАЙДЕН в %s" % mod_dir)
        return []
    cfg = cfgs[0]
    tree_name, tree_desc, nodes = parse_config(cfg)
    print("=== %s ===" % mod_label)
    print("  конфиг: %s | дерево: «%s» | узлов: %d" % (cfg.name, tree_name, len(nodes)))

    # 2. все esp модa (перки могут быть в разных файлах — PerkFile в конфиге)
    esps = {e.name.lower(): e for e in list(mod_dir.glob("*.esp")) + list(mod_dir.glob("*.esm")) + list(mod_dir.glob("*.esl"))}
    # грузим все esp сразу (ключ = локальный id, конфликт маловероятен внутри одного мода)
    perks = {}
    for e in esps.values():
        perks.update(load_perks_from_esp(e))
    print("  PERK в esp: %d | файлов esp/esm/esl: %d" % (len(perks), len(esps)))

    # 3. собираем
    out = []
    for nd in nodes:
        p = perks.get(nd["local_id"])
        if not p:
            continue
        prereq_edids = []
        seen = set()
        for pfid in p["prereq_gfids"]:
            pl = pfid & 0xFFFFFF
            pp = perks.get(pl)
            if pp and pp["edid"] and pp["edid"] != p["edid"] and pp["edid"] not in seen:
                seen.add(pp["edid"])
                prereq_edids.append(pp["edid"])
        cls = classify_all(p["name"], p["desc"])
        out.append({
            "id": "CSF_%s_%06X" % (re.sub(r"\W+", "", cfg.stem.replace("CustomSkill.", "")), nd["local_id"]),
            "mod": mod_label,
            "csf": True,
            "csf_tree": tree_name,
            "branch": tree_name,
            "branch_id": "csf-" + re.sub(r"[^a-z0-9]+", "-", tree_name.lower()).strip("-"),
            "name": p["name"] or p["edid"],
            "eid": p["edid"],
            "formid": "%06X" % nd["local_id"],
            "desc": p["desc"],
            "lvl": p["level"] if p["level"] is not None else -1,
            "prereq": "; ".join(prereq_edids),
            "ranks": p["num_ranks"],
            "role": cls["role"], "mechanics": cls["mechanics"], "element": cls["element"],
            "magictype": cls["magictype"], "weapon_type": cls["weapon_type"],
            "condition": cls["condition"], "trigger": cls["trigger"],
            "x": nd["x"], "y": nd["y"],
            "build": 0,
        })
    out.sort(key=lambda r: (r["lvl"], r["eid"]))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    no_name = sum(1 for o in out if not o["name"] or o["name"] == o["eid"])
    print("  записано: %d -> %s (без имени: %d)" % (len(out), out_path, no_name))
    return out

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("usage: build_csf.py <mod_dir> <mod_label> <out_json>")
        sys.exit(1)
    build(sys.argv[1], sys.argv[2], sys.argv[3])
