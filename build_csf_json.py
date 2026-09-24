# -*- coding: utf-8 -*-
"""Сборщик CSF v3-модов (JSON-формат: Firmament, Constellations).

Структура:
  SKSE/Plugins/CustomSkills/<Мод>/<Дерево>.json — дерево:
      { "id": "...", "name": "$Key", "description": "$Key",
        "nodes": [ {"id","perk":"ESP|LocalID","x","y","links":[...] } ] }
  interface/translations/<esp>_russian.txt — переводы ($Key\\tТекст, UTF-16 LE BOM)
  <esp> — PERK-записи (FULL/DESC могут быть LString -> перевод из translations)

Использование:
  python build_csf_json.py <папка_мода> <имя_в_базе> <выходной_json>
  Выход: один файл на МОД, внутри перки всех деревьев мода (branch = имя дерева).
"""
import json
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scan_mod import iter_records, subrecs, classify_all

def read_translations(mod_dir):
    """Читает interface/translations/*_russian.txt (UTF-16 LE BOM, TAB-разделитель)."""
    out = {}
    for pat in ("interface/translations/*_russian.txt", "Interface/Translations/*_russian.txt"):
        for f in mod_dir.glob(pat):
            raw = f.read_bytes()
            for enc in ("utf-16", "utf-16-le", "utf-8-sig"):
                try:
                    txt = raw.decode(enc)
                    break
                except Exception:
                    continue
            else:
                continue
            for line in txt.splitlines():
                if "\t" in line:
                    k, v = line.split("\t", 1)
                    out[k.strip()] = v.strip()
    return out

def load_perks_from_esp(esp_path):
    """PERK из ESP: локальный id -> данные (FULL/DESC могут быть LString id)."""
    perks = {}
    for tag, fid, body in iter_records(str(esp_path)):
        if tag != "PERK":
            continue
        local = fid & 0xFFFFFF
        subs = subrecs(body)
        edid = name = desc = ""
        num_ranks = 1
        for t, v in subs:
            if t == "EDID":
                edid = v.rstrip(b"\x00").decode("latin1", "replace")
            elif t == "FULL":
                if len(v) == 4:
                    name = "$LSTR:%d" % struct.unpack_from("<I", v, 0)[0]
                else:
                    name = v.rstrip(b"\x00").decode("utf-8", "replace")
            elif t == "DESC":
                if len(v) == 4:
                    desc = "$LSTR:%d" % struct.unpack_from("<I", v, 0)[0]
                else:
                    desc = v.rstrip(b"\x00").decode("utf-8", "replace")
            elif t == "DATA" and len(v) == 5:
                num_ranks = v[2]
        perks[local] = {"edid": edid, "name": name, "desc": desc, "num_ranks": num_ranks}
    return perks

def resolve_lstrings(perks, esp_path, mod_dir):
    """Резолвит $LSTR:id через .strings файлы ESP (interface/translations не для FULL/DESC).
    CSF v3: FULL/DESC обычно уже текст; если LString — читаем <esp>_russian.strings? Нет:
    у ESP-строк переводы в strings рядом с esp. Но у Firmament/Constellations FULL — прямой текст,
    а $Name только у названий деревьев в json. Так что тут только подстраховка."""
    return perks

def build(mod_dir, mod_label, out_path):
    mod_dir = Path(mod_dir)
    print("=== %s ===" % mod_label)

    # 1. деревья: SKSE/Plugins/CustomSkills/<ПодпапкаМода>/*.json
    cs_root = mod_dir / "SKSE" / "Plugins" / "CustomSkills"
    tree_files = []
    for sub in cs_root.iterdir():
        if sub.is_dir():
            tree_files += list(sub.glob("*.json"))
    tree_files = [f for f in tree_files if f.name != "SKILLS.json"]
    print("  деревьев: %d (%s)" % (len(tree_files), ", ".join(f.stem for f in tree_files)))

    # 2. переводы (названия/описания деревьев)
    tr = read_translations(mod_dir)
    print("  переводов: %d" % len(tr))

    # 3. ESP -> перки (все esp мода)
    perks = {}
    for esp in list(mod_dir.glob("*.esp")) + list(mod_dir.glob("*.esm")) + list(mod_dir.glob("*.esl")):
        perks.update(load_perks_from_esp(esp))
    print("  PERK в esp: %d" % len(perks))

    # 4. собираем
    out = []
    for tf in tree_files:
        tree = json.load(open(tf, encoding="utf-8"))
        tree_name = tr.get(tree.get("name", ""), tree.get("id", tf.stem))
        nodes = tree.get("nodes", [])
        got = 0
        for nd in nodes:
            perk_ref = nd.get("perk", "")
            m = re.match(r"^([^|]+)\|([0-9A-Fa-f]+)$", perk_ref)
            if not m:
                continue
            local_id = int(m.group(2), 16)
            p = perks.get(local_id)
            if not p:
                continue
            # ссылки на другие перки дерева (по node id) -> edid
            cls = classify_all(p["name"], p["desc"])
            out.append({
                "id": "CSF_%s_%s_%06X" % (re.sub(r"\W+", "", mod_label), tree.get("id", tf.stem), local_id),
                "mod": mod_label,
                "csf": True,
                "csf_tree": tree_name,
                "branch": tree_name,
                "branch_id": "csf-" + re.sub(r"[^a-z0-9а-яё]+", "-", tree_name.lower()).strip("-"),
                "name": p["name"] or p["edid"],
                "eid": p["edid"] or nd.get("id", ""),
                "formid": "%06X" % local_id,
                "desc": p["desc"],
                "lvl": -1,
                "prereq": "",
                "ranks": p["num_ranks"],
                "role": cls["role"], "mechanics": cls["mechanics"], "element": cls["element"],
                "magictype": cls["magictype"], "weapon_type": cls["weapon_type"],
                "condition": cls["condition"], "trigger": cls["trigger"],
                "x": nd.get("x", 0), "y": nd.get("y", 0),
                "build": 0,
            })
            got += 1
        print("    %-20s %2d/%2d перков (дерево «%s»)" % (tf.stem, got, len(nodes), tree_name))

    out.sort(key=lambda r: (r["branch"], r["eid"]))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    no_name = sum(1 for o in out if not o["name"] or o["name"].startswith("$LSTR"))
    lat = sum(1 for o in out if o["name"] and all(ord(c) < 128 for c in o["name"]))
    print("  записано: %d -> %s (без имени: %d, латиница: %d)" % (len(out), out_path, no_name, lat))
    return out

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("usage: build_csf_json.py <mod_dir> <mod_label> <out_json>")
        sys.exit(1)
    build(sys.argv[1], sys.argv[2], sys.argv[3])
