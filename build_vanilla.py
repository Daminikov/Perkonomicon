# -*- coding: utf-8 -*-
"""Сборка базы ванильных перков v3 — правильная.

Ключевое:
1. FormID хранится как (mod_prefix, local_id) — уникальный ключ.
2. AVIF-узлы содержат ГЛОБАЛЬНЫЕ formid → резолвим через masters плагина.
3. В таблицу идут ТОЛЬКО перки из AVIF-деревьев (18 навыков + вампир/оборотень).
4. Патчи: если переопределяют перк из дерева — заменяют; если нет — игнор.
5. Без дедупликации по edid — оригинал и переопределение сосуществуют.
"""
import json
import struct
import zlib
import subprocess
from pathlib import Path

GAME = Path(r"C:/Program Files (x86)/Steam/steamapps/common/Skyrim Special Edition/Data")
MODS = Path(r"C:/MO2 Daminikov/mods")
SCRATCH = Path(r"C:/Users/Daminikov_/AppData/Local/hermes/cache/scratch")
OUT = Path(r"C:/Code/My IDE SKSE/DataBase/perk-table/data/perks/Vanilla.json")
UNPACKED = 0x00040000

FILES = [
    ("Skyrim.esm", GAME / "Skyrim.esm"),
    ("Update.esm", GAME / "Update.esm"),
    ("Dawnguard.esm", GAME / "Dawnguard.esm"),
    ("HearthFires.esm", GAME / "HearthFires.esm"),
    ("Dragonborn.esm", GAME / "Dragonborn.esm"),
    ("USSEP", MODS / "[PATCH] - Unofficial Skyrim Special Edition Patch - USSEP" / "unofficial skyrim special edition patch.esp"),
    ("USMP", MODS / "[PATCH] - Unofficial Skyrim Modder's Patch - USMP SE" / "Unofficial Skyrim Modders Patch.esp"),
]

AV_NAMES = {6:"One-Handed",7:"Two-Handed",8:"Marksman",9:"Block",10:"Smithing",
            11:"HeavyArmor",12:"LightArmor",13:"Pickpocket",14:"Lockpicking",15:"Sneak",
            16:"Alchemy",17:"Speech",18:"Alteration",19:"Conjuration",20:"Destruction",
            21:"Illusion",22:"Restoration",23:"Enchanting"}
BRANCH_RU = {"AVOneHanded":"Одноручное оружие","AVTwoHanded":"Двуручное оружие",
    "AVMarksman":"Стрельба","AVBlock":"Блокирование","AVSmithing":"Кузнечное дело",
    "AVHeavyArmor":"Тяжёлая броня","AVLightArmor":"Лёгкая броня","AVPickpocket":"Карманные кражи",
    "AVLockpicking":"Взлом","AVSneak":"Скрытность","AVAlchemy":"Алхимия","AVSpeechcraft":"Красноречие",
    "AVIllusion":"Иллюзия","AVConjuration":"Колдовство","AVDestruction":"Разрушение",
    "AVRestoration":"Восстановление","AVAlteration":"Изменение","AVEnchanting":"Зачарование",
    "AVMysticism":"Иллюзия",
    "AVHealRatePowerMod":"Вампиризм (Dawnguard)","AVMagickaRateMod":"Оборотень (Dawnguard)"}
BRANCH_ID = {"AVOneHanded":"one-handed","AVTwoHanded":"two-handed","AVMarksman":"archery",
    "AVBlock":"block","AVSmithing":"smithing","AVHeavyArmor":"heavy-armor","AVLightArmor":"light-armor",
    "AVPickpocket":"pickpocket","AVLockpicking":"lockpicking","AVSneak":"sneak","AVAlchemy":"alchemy",
    "AVSpeechcraft":"speech","AVIllusion":"illusion","AVConjuration":"conjuration","AVDestruction":"destruction",
    "AVRestoration":"restoration","AVAlteration":"alteration","AVEnchanting":"enchanting",
    "AVMysticism":"illusion","AVHealRatePowerMod":"vampirism","AVMagickaRateMod":"werewolf"}
# Dawnguard: AVHealRatePowerMod = вампир, AVMagickaRateMod = оборотень (по контексту DLC)

# ── strings ─────────────────────────────────────────
def load_str(path):
    p = Path(path)
    if not p.exists(): return {}
    d = p.read_bytes()
    cnt, dsize = struct.unpack_from("<ii", d, 0)
    base = 8 + cnt * 8
    out = {}
    for i in range(cnt):
        sid, off = struct.unpack_from("<II", d, 8 + i * 8)
        start = base + off
        if start + 4 > len(d): continue
        ln = struct.unpack_from("<I", d, start)[0]
        if ln and start + 4 + ln <= len(d):
            txt = d[start+4:start+4+ln].decode("utf-8", "replace")
        else:
            try:
                end = d.index(b"\x00", start)
                txt = d[start:end].decode("utf-8", "replace")
            except ValueError:
                continue
        if sid: out[sid & 0x7FFFFFFF] = txt.rstrip("\x00").strip()
    return out

STRINGS = {}
for key, fname in [("Skyrim.esm","ru.strings"),("Skyrim.esm","ru.dlstrings"),
                   ("Update.esm","update_ru.strings"),("Update.esm","update_ru.dlstrings"),
                   ("Dawnguard.esm","dawnguard_ru.strings"),("Dawnguard.esm","dawnguard_ru.dlstrings"),
                   ("HearthFires.esm","hearthfires_ru.strings"),("HearthFires.esm","hearthfires_ru.dlstrings"),
                   ("Dragonborn.esm","dragonborn_ru.strings"),("Dragonborn.esm","dragonborn_ru.dlstrings")]:
    short = "dlstrings" in fname
    STRINGS[(key, short)] = load_str(SCRATCH / fname)

A = r"S:/Skyrim IDE/tools/esp-analyzer/bin/esp-analyzer.exe"
def extract_bsa(bsa, inner, out):
    p = Path(out)
    if p.exists(): return
    try:
        subprocess.run([A, "archives", str(bsa), "--extract", inner, "--out", str(p)],
                       capture_output=True, timeout=120)
    except Exception:
        pass

for name, bsa, inner_s, inner_dl in [
    ("USSEP", FILES[5][1].parent / "unofficial skyrim special edition patch.bsa",
     "strings/unofficial skyrim special edition patch_russian.strings",
     "strings/unofficial skyrim special edition patch_russian.dlstrings"),
    ("USMP", FILES[6][1].parent / "Unofficial Skyrim Modders Patch.bsa",
     "strings/unofficial skyrim modders patch_russian.strings",
     "strings/unofficial skyrim modders patch_russian.dlstrings")]:
    if bsa.exists():
        extract_bsa(bsa, inner_s, SCRATCH / (name.lower() + "_ru.strings"))
        extract_bsa(bsa, inner_dl, SCRATCH / (name.lower() + "_ru.dlstrings"))
        STRINGS[(name, False)] = load_str(SCRATCH / (name.lower() + "_ru.strings"))
        STRINGS[(name, True)] = load_str(SCRATCH / (name.lower() + "_ru.dlstrings"))

print("строки загружены:", {k[0] + ("(dl)" if k[1] else ""): len(v) for k, v in STRINGS.items()})

# ── ESP parser ──────────────────────────────────────
def subs(body, limit=None):
    out = []
    i = 0
    while i + 6 <= len(body):
        tag = body[i:i+4].decode("latin1")
        ln = struct.unpack_from("<H", body, i+4)[0]
        out.append((tag, body[i+6:i+6+ln]))
        i += 6 + ln
        if limit and len(out) >= limit: break
    return out

def iter_records(path):
    data = Path(path).read_bytes()
    hs = struct.unpack_from("<i", data, 4)[0]
    def walk(start, end):
        pos = start
        while pos + 24 <= end:
            tag = data[pos:pos+4].decode("latin1")
            size = struct.unpack_from("<i", data, pos+4)[0]
            flags = struct.unpack_from("<I", data, pos+8)[0]
            form_id = struct.unpack_from("<I", data, pos+12)[0]
            if tag == "GRUP":
                if size < 24 or pos + size > end: return
                yield from walk(pos + 24, pos + size)
                pos += size
                continue
            if pos + 24 + size > end: return
            body = data[pos+24:pos+24+size]
            if flags & UNPACKED:
                try: body = zlib.decompress(body[4:])
                except Exception: body = b""
            yield tag, form_id, body
            pos += 24 + size
    yield from walk(24 + hs, len(data))

def read_masters(path):
    d = Path(path).read_bytes()
    hs = struct.unpack_from("<i", d, 4)[0]
    masters = []
    pos = 24
    while pos + 6 <= 24 + hs and pos + 6 <= len(d):
        tag = d[pos:pos+4].decode("latin1")
        ln = struct.unpack_from("<H", d, pos+4)[0]
        if tag == "MAST":
            masters.append(d[pos+6:pos+6+ln].rstrip(b"\x00").decode("latin1"))
        pos += 6 + ln
    return masters

# ── собираем ────────────────────────────────────────
# Глобальный реестр: (mod_name, local_formid) → perk_dict
# Глобальный formid (как в AVIF-узлах) → (mod_name, local_formid)
perk_registry = {}   # (mod, local) -> perk
global_map = {}      # global_formid -> (mod, local)  [последняя запись побеждает]
tree_nodes = []      # (avif_edid, branch_ru, global_perk_fid, x, y, index)

def parse_plugin(mod_name, path):
    """Парсит PERK и AVIF, возвращает (n_perks, n_trees)."""
    if not path.exists():
        return 0, 0
    masters = read_masters(path)
    master_names = [m for m in masters]  # 0=Skyrim.esm по умолчанию у нас
    # Для наших файлов мастер-индексы известны по позиции в FILES:
    # 0x00 = Skyrim.esm, 0x01 = Update.esm, 0x02 = Dawnguard.esm, 0x03 = HearthFires.esm, 0x04 = Dragonborn.esm
    # USSEP/USMP имеют своих мастеров в MAST — маппим по имени файла
    name_to_prefix = {"Skyrim.esm":0, "Update.esm":1, "Dawnguard.esm":2,
                      "HearthFires.esm":3, "Dragonborn.esm":4}
    n_p = n_t = 0
    for tag, form_id, body in iter_records(path):
        s = subs(body)
        edid = next((v.split(b"\x00")[0].decode("latin1", "replace") for t, v in s if t == "EDID"), "")
        if tag == "AVIF" and edid in BRANCH_RU:
            # узлы дерева
            cur = {}
            idx = 0
            for t, v in s:
                if t == "PNAM" and len(v) >= 4:
                    cur["perk"] = struct.unpack_from("<I", v, 0)[0]
                elif t == "XNAM" and len(v) >= 4:
                    cur["x"] = struct.unpack_from("<i", v, 0)[0]
                elif t == "YNAM" and len(v) >= 4:
                    cur["y"] = struct.unpack_from("<i", v, 0)[0]
                elif t == "INAM" and len(v) >= 4:
                    cur["index"] = struct.unpack_from("<i", v, 0)[0]
                    if cur.get("perk") is not None:
                        tree_nodes.append({
                            "avif": edid, "branch": BRANCH_RU[edid],
                            "perk_global": cur["perk"], "x": cur.get("x"), "y": cur.get("y"),
                            "idx": cur["index"], "plugin": mod_name})
                    cur = {}
            n_t += 1
        elif tag == "PERK":
            # локальный formid в этом плагине
            prefix = (form_id >> 24) & 0xFF
            local = form_id & 0xFFFFFF
            # резолв: мастер vs новый
            if prefix == 0xFE:
                owner = mod_name + " (ESL)"
            elif prefix < len(master_names):
                owner = master_names[prefix]
            else:
                owner = mod_name
            full_id = desc_id = None
            level = None
            prereq_edids = []
            num_ranks = 1
            playable = True
            effects = []
            conds = []
            nnam_next = None
            for t, v in s:
                if t == "FULL" and len(v) == 4:
                    full_id = struct.unpack_from("<I", v, 0)[0]
                elif t == "DESC" and len(v) == 4:
                    desc_id = struct.unpack_from("<I", v, 0)[0]
                elif t == "DATA" and len(v) >= 5:
                    num_ranks = v[2]
                    playable = v[3] != 0
                elif t == "NNAM" and len(v) >= 4:
                    nnam_next = struct.unpack_from("<I", v, 0)[0]
                elif t == "CTDA" and len(v) >= 28:
                    # CTDA 32 байта (SSE): flags(1) runon(1) unused(2) fval(4) func(2) pad(2) p1(4) p2(4) ...
                    fn = struct.unpack_from("<H", v, 8)[0]
                    p1 = struct.unpack_from("<I", v, 12)[0]
                    fval = struct.unpack_from("<f", v, 4)[0]
                    if fn == 277:  # GetBaseActorValue
                        if level is None and p1 in AV_NAMES:
                            level = int(fval)
                    elif fn == 448:  # HasPerk
                        prereq_edids.append(p1)  # глобальный formid пока
                    conds.append({"func": fn, "p1": p1, "val": fval})
                elif t == "EPFT" and len(v) >= 1:
                    effects.append({"type": v[0]})
                elif t == "EPFD" and len(v) >= 4:
                    if effects:
                        effects[-1]["value"] = struct.unpack_from("<f", v, 0)[0]
            # FULL (короткое имя) → .strings; DESC (длинное описание) → .dlstrings
            # Приоритет: сначала строки СВОЕГО мода, потом остальные.
            name_ru = desc_ru = ""
            mod_key = mod_name if mod_name in ("Skyrim.esm","Update.esm","Dawnguard.esm",
                          "HearthFires.esm","Dragonborn.esm") else "Skyrim.esm"
            name_order = [(mod_key, False), ("Skyrim.esm", False), ("Update.esm", False),
                          ("Dawnguard.esm", False), ("HearthFires.esm", False),
                          ("Dragonborn.esm", False), ("USSEP", False), ("USMP", False)]
            desc_order = [(mod_key, True), ("Skyrim.esm", True), ("Update.esm", True),
                          ("Dawnguard.esm", True), ("HearthFires.esm", True),
                          ("Dragonborn.esm", True), ("USSEP", True), ("USMP", True)]
            for k in name_order:
                if full_id is not None and full_id < 0x10000000 and k in STRINGS and full_id in STRINGS[k] and STRINGS[k][full_id]:
                    name_ru = STRINGS[k][full_id]; break
            for k in desc_order:
                if desc_id is not None and desc_id < 0x10000000 and k in STRINGS and desc_id in STRINGS[k] and STRINGS[k][desc_id]:
                    desc_ru = STRINGS[k][desc_id]; break
            perk = {
                "mod": mod_name, "edid": edid, "local_fid": "%06X" % local,
                "global_fid": "%08X" % form_id, "owner": owner,
                "name": name_ru, "desc": desc_ru, "level": level,
                "prereq_gfids": prereq_edids, "ranks": num_ranks, "playable": playable,
                "effects": effects, "conds": conds, "nnam_next": nnam_next,
                "full_id": full_id, "desc_id": desc_id,
            }
            perk_registry[(mod_name, local)] = perk
            global_map[form_id] = (mod_name, local)
            n_p += 1
    return n_p, n_t

print("парсинг плагинов...")
for mod_name, path in FILES:
    np_, nt_ = parse_plugin(mod_name, path)
    print("  %-40s PERK=%d AVIF=%d" % (mod_name, np_, nt_))

# ── формируем итоговый список ───────────────────────
# Перк попадает в таблицу ТОЛЬКО если на него ссылается узел AVIF-дерева.
# Из всех плагинов берём последнюю версию (порядок FILES = порядок загрузки).
print("формирование таблицы...")
out = []
seen_global = set()  # global formid — одна запись на перк

# Порядок: сначала Skyrim, потом Update, DLC, потом патчи.
# Но таблица должна показывать ФИНАЛЬНУЮ версию (патч побеждает).
# Поэтому идём от конца к началу и берём первое вхождение.
for node in tree_nodes:
    gfid = node["perk_global"]
    if gfid == 0 or gfid in seen_global:
        continue
    seen_global.add(gfid)
    # резолвим глобальный formid в (mod, local)
    if gfid not in global_map:
        continue  # перк не найден (не должно быть)
    mod_name, local = global_map[gfid]
    p = perk_registry.get((mod_name, local))
    if not p:
        continue
    # Если это патч-версия (USSEP/USMP) — ищем лучшую версию по edid:
    # приоритет на имя/описание (у Skyrim/DLC они есть, у патча часто нет),
    # но берём патч, если у него есть имя (значит патч что-то менял осмысленно).
    if mod_name in ("USSEP", "USMP"):
        best = p
        for (om, ol), op in perk_registry.items():
            if op["edid"] != p["edid"]:
                continue
            if om not in ("USSEP", "USMP"):
                # оригинал из Skyrim/DLC — предпочитаем, если у него есть имя
                if op["name"] or op["desc"]:
                    best = op
                    break
            elif om == "USMP" and (op["name"] or op["desc"]):
                best = op  # USMP поверх USSEP, если у него есть текст
        p = best
    # prereq: резолвим глобальные fid в edid, дедупликация.
    # Исключаем: самоссылки на следующий ранг (NNAM) — это не требование.
    prereq_edids = []
    seen_prereq = set()
    for pfid in p["prereq_gfids"]:
        if pfid == p["nnam_next"]:
            continue  # ссылка на следующий ранг — не требование
        if pfid in global_map:
            pm, pl = global_map[pfid]
            pp = perk_registry.get((pm, pl))
            if pp and pp["edid"] not in seen_prereq and pp["edid"] != p["edid"]:
                seen_prereq.add(pp["edid"])
                prereq_edids.append(pp["edid"])
    # tags
    txt = (p["name"] + " " + p["desc"]).lower()
    tags = []
    if "меч" in txt or "sword" in txt: tags.append("меч")
    if "топор" in txt or "axe" in txt: tags.append("топор")
    if "булав" in txt or "mace" in txt: tags.append("булава")
    if "кинжал" in txt or "dagger" in txt: tags.append("кинжал")
    if "двух рук" in txt or "dual" in txt or "парн" in txt: tags.append("парное")
    if "лук" in txt or "bow" in txt: tags.append("лук")
    if "вампир" in txt or "vampire" in txt: tags.append("вампир")
    if "оборотень" in txt or "werewolf" in txt or "волколак" in txt: tags.append("оборотень")
    if "заклинан" in txt or "магия" in txt or "magic" in txt: tags.append("магия")
    if "брон" in txt or "armor" in txt: tags.append("броня")
    if "силов" in txt or "power attack" in txt: tags.append("силовая")
    if "крит" in txt or "critical" in txt: tags.append("крит")
    if "скрытн" in txt or "sneak" in txt: tags.append("скрытность")
    if not tags: tags = ["core"]
    out.append({
        "id": p["global_fid"],
        "mod": "Vanilla",
        "branch": node["branch"],
        "branch_id": BRANCH_ID.get(node["avif"], ""),
        "name": p["name"] if p["name"] else p["edid"],
        "eid": p["edid"],
        "formid": p["global_fid"],
        "desc": p["desc"],
        "lvl": p["level"] if p["level"] is not None else -1,
        "prereq": "; ".join(prereq_edids),
        "ranks": p["ranks"],
        "tags": tags,
        "x": node.get("x"),
        "y": node.get("y"),
        "build": 0,
        "source": mod_name,
    })

# Сортировка: по ветке, потом по уровню
out.sort(key=lambda x: (x["branch"], x["lvl"] if x["lvl"] >= 0 else 999, x["eid"]))

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)

print("итого перков:", len(out))
print()
from collections import Counter
c = Counter(p["branch"] for p in out)
for b, n in sorted(c.items()):
    print("  %-30s %d" % (b, n))
print()
print("записано:", OUT)
