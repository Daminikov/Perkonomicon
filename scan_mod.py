# -*- coding: utf-8 -*-
"""Полный сканер ESP: вытаскивает всё, классифицирует, сравнивает с базой, запоминает решения.

Использование:
  python scan_mod.py <esp> <имя_мода> <выходной_json>

Что делает:
1. Парсит ESP: PERK, AVIF, KYWD, MGEF, SPEL, BOOK, MESG, GLOB, FLST, ENCH, ALCH, INGR, WEAP, ARMO
2. Классифицирует перки (role, mechanics, element, magictype, weapon_type, condition, trigger)
3. Сравнивает с базой (data/perks/*.json) — что нового, что изменилось
4. Показывает новые механики/элементы/условия, которых нет в базе
5. Сохраняет решения в data/decisions.json — чтобы не спрашивать повторно
6. Записывает в базу только одобренное
"""
import json
import struct
import sys
import zlib
import re
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

UNPACKED = 0x00040000

# ── пути ──
BASE = Path(r"C:\Code\My IDE SKSE\DataBase")
PERKS_DIR = BASE / "perk-table" / "data" / "perks"
DECISIONS = BASE / "perk-table" / "data" / "decisions.json"

# ── классификация (из build_mod.py) ──
ROLE_RULES = [
    ("control",  ["страх","ярост","ошелом","парали","обездвиж","отбрасыва","отброс","замедл","ослепл","немот","прерыва","interrupt","подчин","контрол разум","успокоен","бешенств","паник"]),
    ("summon",   ["призыв","призван","атронах","некромант","подним","оживлен","тотем","гаргуль","питомц","вызов ","сумон"]),
    ("stealth",  ["скрытн","незамет","крад","карман","взлом","убийств из тени","подкрад","шум","обнаружен"]),
    ("craft",    ["кузнеч","зачаров","алхим","зель","ингредиент","кование","создава","улучшени предмет","плавильн"]),
    ("defense",  ["брон","защит","блок","щит","сопротив","уклон","поглоща","устойчив","получаете на .* меньше урона","снижа.*урон"]),
    ("support",  ["лечен","восстанавлива","регенерац","исцел","союзник","спутник","бафф","оберег","aura","аура"]),
    ("attack",   ["урон","атак","критическ","крит ","пробива","игнорирует брон","дополнительн"]),
    ("utility",  ["скорость передвиж","переносим","вес","торгов","цены","скидк","быстрее","время","улучшает","добыч","золото","опыт","обучени"]),
]
MECH_RULES = [
    ("dmg",        ["наносит на \\d+% больше урона","урон увеличен","дополнительн.* урон","\\+\\d+% к урону","урона на \\d+","увеличение урона"]),
    ("crit",       ["критическ","критического урона","крит\\. удар","обезглавл"]),
    ("dot",        ["кровотеч","кровопотер","в секунду в течение","урон с течением времени","истекают кров","горен"]),
    ("power_attack",["силов","мощная атака","power attack","power bash","силовой атаки","силовые атаки","силовым ударом"]),
    ("cost",       ["расход","тратит на .* меньше","меньше магии","меньше запаса сил","меньше выносливости","стоимость"]),
    ("pierce",     ["игнорирует .* брон","пробивает брон","игнорирование брони"]),
    ("speed",      ["скорость атаки","быстрее атак","на \\d+% быстрее","скорость натяжения"]),
    ("on_kill",    ["при убийстве","убийство противника","убив","после убийства"]),
    ("conditional",["противник.*замах","противников, которые","при атаке сбоку","при атаке сзади","если цель","когда здоровье","целям с менее","ошеломленным","спящ"]),
    ("stack",      ["суммируется","накапливается","эффект складывается","stack"]),
    ("block",      ["блокир","щитом","отражени"]),
    ("resist",     ["сопротивление","устойчивость","иммунитет"]),
    ("regen",      ["восстанавливается","регенерац","восполнение"]),
    ("range",      ["дальность","радиус","дистанц"]),
]
ELEMENT_RULES = [
    ("fire",      ["огонь","огненн","поджог","воспламен","плам","fire","burn"]),
    ("frost",     ["мороз","лед","замороз","холод","frost","ice","freez"]),
    ("shock",     ["молния","шок","электрич","thunder","lightning","shock","spark"]),
    ("poison",    ["яд","отрав","poison","toxic"]),
    ("light",     ["свет","holy","свят","dawn","рассвет","sun","солнце"]),
    ("dark",      ["тьма","тень","shadow","dark","ноч","умрак","necro","некро"]),
    ("arcane",    ["arcane","тайн","магическ","энергия","magicka","мана"]),
    ("physical",  ["физическ","blunt","pierce","slash","колющ","рубящ","дробящ"]),
]
MAGICTYPE_RULES = [
    ("ward",      ["оберег","ward","защита от заклинаний","magic resist","поглощение заклинаний"]),
    ("heal",      ["лечение","heal","исцел","регенерац","восстановление здоровья","restoration"]),
    ("summon",    ["призыв","summon","атронах","atronach","зомби","skeleton","вызов существа"]),
    ("illusion",  ["иллюзия","illusion","страх","fear","ярость","frenzy","спокойствие","calm","обман","charm"]),
    ("destruction",["разрушение","destruction","урон стихиями","elemental damage"]),
    ("alteration",["изменение","alteration","обнаружение","detect","transmutation","трансмутация","paralysis","паралич"]),
    ("enchanting",["зачарование","enchant","душа","soul","перезарядка","recharge"]),
]
WEAPON_RULES = [
    ("sword",     ["меч","sword","blade","клинок","шпаг","рапир","сабл","палаш"]),
    ("axe",       ["топор","axe","battleaxe","рубящ","секир","алебард"]),
    ("mace",      ["булав","mace","hammer","молот","дробящ","дубин","палиц","боевой молот"]),
    ("dagger",    ["кинжал","dagger","knife","нож","кортик","стилет","кинжальч"]),
    ("bow",       ["лук","bow","arrow","стрел","archery","стрельб","тетив"]),
    ("crossbow",  ["арбалет","crossbow","болт","самострел"]),
    ("dual",      ["парное","dual","два оружия","обеих руках","двойной"]),
    ("twohand",   ["двуручн","two-hand","greatsword","battleaxe","warhammer","двумя руками"]),
    ("onehand",   ["одноручн","one-hand","single","одной рукой"]),
    ("unarmed",   ["кулак","unarmed","fist","рукопаш"]),
    ("staff",     ["посох","staff","wand","жезл"]),
    ("shield",    ["щит","shield","блок","block"]),
]
CONDITION_RULES = [
    ("power",     ["силов","power attack","power bash","сильная атака","заряженная"]),
    ("crit",      ["критическ","critical","крит","обезглавл","decapit"]),
    ("kill",      ["убийств","kill","при убийстве","смертельный удар","finishing"]),
    ("low_hp",    ["низкое здоровье","low health","при здоровье","when health","ранен","wounded"]),
    ("full_hp",   ["полное здоровье","full health","максимальное здоровье"]),
    ("sneak",     ["скрытн","sneak","подкрад","незамет","stealth","тих"]),
    ("moving",    ["в движении","moving","бег","sprint","спринт","бегом"]),
    ("standing",  ["стоя","standing","неподвижн","на месте"]),
    ("behind",    ["сзади","behind","backstab","в спину"]),
    ("staggered", ["ошеломл","stagger","disorient","оглуш"]),
    ("blocked",   ["блокир","blocked","щитом","block"]),
    ("night",     ["ночь","night","темнот","darkness"]),
    ("day",       ["день","day","светлое время"]),
]
TRIGGER_RULES = [
    ("on_hit",    ["при ударе","on hit","при попадании","при атаке"]),
    ("on_block",  ["при блоке","on block","при блокировании","блокируя"]),
    ("on_dodge",  ["при уклонении","on dodge","уклон","dodge"]),
    ("on_cast",   ["при сотворении","on cast","при касте","casting"]),
    ("on_kill",   ["при убийстве","on kill","убив"]),
    ("on_crit",   ["при критическом","on crit","при крите"]),
    ("on_damaged",["при получении урона","when damaged","при получении","taking damage"]),
    ("passive",   ["пассивн","passive","всегда","always","постоянн"]),
]

AV_NAMES = {6:"One-Handed",7:"Two-Handed",8:"Marksman",9:"Block",10:"Smithing",11:"HeavyArmor",
            12:"LightArmor",13:"Pickpocket",14:"Lockpicking",15:"Sneak",16:"Alchemy",17:"Speech",
            18:"Alteration",19:"Conjuration",20:"Destruction",21:"Illusion",22:"Restoration",23:"Enchanting"}
BRANCH_RU = {"AVOneHanded":"Одноручное оружие","AVTwoHanded":"Двуручное оружие","AVMarksman":"Стрельба",
    "AVBlock":"Блокирование","AVSmithing":"Кузнечное дело","AVHeavyArmor":"Тяжёлая броня",
    "AVLightArmor":"Лёгкая броня","AVPickpocket":"Карманные кражи","AVLockpicking":"Взлом",
    "AVSneak":"Скрытность","AVAlchemy":"Алхимия","AVSpeechcraft":"Красноречие",
    "AVIllusion":"Иллюзия","AVConjuration":"Колдовство","AVDestruction":"Разрушение",
    "AVRestoration":"Восстановление","AVAlteration":"Изменение","AVEnchanting":"Зачарование",
    "AVMysticism":"Иллюзия","AVHealRatePowerMod":"Вампиризм (Dawnguard)","AVMagickaRateMod":"Оборотень (Dawnguard)"}
BRANCH_ID = {"AVOneHanded":"one-handed","AVTwoHanded":"two-handed","AVMarksman":"archery",
    "AVBlock":"block","AVSmithing":"smithing","AVHeavyArmor":"heavy-armor","AVLightArmor":"light-armor",
    "AVPickpocket":"pickpocket","AVLockpicking":"lockpicking","AVSneak":"sneak","AVAlchemy":"alchemy",
    "AVSpeechcraft":"speech","AVIllusion":"illusion","AVConjuration":"conjuration","AVDestruction":"destruction",
    "AVRestoration":"restoration","AVAlteration":"alteration","AVEnchanting":"enchanting",
    "AVMysticism":"illusion","AVHealRatePowerMod":"vampirism","AVMagickaRateMod":"werewolf"}

def classify_text(text, rules):
    t = text.lower()
    out = []
    for tag, kws in rules:
        for kw in kws:
            if kw.startswith("\\") or any(c in kw for c in "[](){}.*+?|^$"):
                if re.search(kw, t): out.append(tag); break
            elif kw in t: out.append(tag); break
    return out

def classify_role(text):
    t = text.lower()
    for role, kws in ROLE_RULES:
        for kw in kws:
            if kw in t: return role
    return "passive"

def classify_all(name, desc):
    text = (name + " " + desc).lower()
    return {
        "role": classify_role(text),
        "mechanics": classify_text(text, MECH_RULES),
        "element": classify_text(text, ELEMENT_RULES),
        "magictype": classify_text(text, MAGICTYPE_RULES),
        "weapon_type": classify_text(text, WEAPON_RULES),
        "condition": classify_text(text, CONDITION_RULES),
        "trigger": classify_text(text, TRIGGER_RULES),
    }

# ── ESP парсер ──
def iter_records(path):
    data = Path(path).read_bytes()
    hs = struct.unpack_from("<i", data, 4)[0]
    def walk(start, end):
        pos = start
        while pos + 24 <= end:
            tag = data[pos:pos+4].decode("latin1")
            size = struct.unpack_from("<i", data, pos+4)[0]
            flags = struct.unpack_from("<I", data, pos+8)[0]
            fid = struct.unpack_from("<I", data, pos+12)[0]
            if tag == "GRUP":
                if size < 24 or pos + size > end: return
                yield from walk(pos+24, pos+size)
                pos += size
                continue
            if pos + 24 + size > end: return
            body = data[pos+24:pos+24+size]
            if flags & UNPACKED:
                try: body = zlib.decompress(body[4:])
                except Exception: body = b""
            yield tag, fid, body
            pos += 24 + size
    yield from walk(24 + hs, len(data))

def subrecs(body):
    out = []
    i = 0
    while i + 6 <= len(body):
        t = body[i:i+4].decode("latin1")
        ln = struct.unpack_from("<H", body, i+4)[0]
        v = body[i+6:i+6+ln]
        out.append((t, v))
        i += 6 + ln
    return out

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

# ── сканер ──
def scan_mod(esp_path, mod_label, out_path):
    print("=== %s ===" % mod_label)
    masters = read_masters(esp_path)
    print("  мастера:", masters)
    own_prefix = len(masters)

    # Собираем ВСЕ типы записей
    all_records = defaultdict(list)  # tag -> [ (fid, subs) ]
    for tag, fid, body in iter_records(esp_path):
        all_records[tag].append((fid, subrecs(body)))

    print("  записей: %d | типов: %d" % (sum(len(v) for v in all_records.values()), len(all_records)))
    for tag, recs in sorted(all_records.items(), key=lambda x: -len(x[1]))[:15]:
        print("    %-6s %d" % (tag, len(recs)))

    # PERK + AVIF для таблицы
    perks = {}
    avif_trees = {}
    for tag, fid, body in iter_records(esp_path):
        local = fid & 0xFFFFFF
        if tag == "PERK":
            sub = subrecs(body)
            edid = name = desc = ""
            level = None; prereq_gfids = []; nnam_next = None; num_ranks = 1
            for t, v in sub:
                if t == "EDID": edid = v.rstrip(b"\x00").decode("latin1", "replace")
                elif t == "FULL":
                    if len(v) == 4: pass  # LString — пропускаем
                    else: name = v.rstrip(b"\x00").decode("utf-8", "replace")
                elif t == "DESC":
                    if len(v) == 4: pass
                    else: desc = v.rstrip(b"\x00").decode("utf-8", "replace")
                elif t == "DATA" and len(v) == 5: num_ranks = v[2]
                elif t == "NNAM" and len(v) >= 4: nnam_next = struct.unpack_from("<I", v, 0)[0]
                elif t == "CTDA" and len(v) >= 28:
                    fn = struct.unpack_from("<H", v, 8)[0]
                    p1 = struct.unpack_from("<I", v, 12)[0]
                    fval = struct.unpack_from("<f", v, 4)[0]
                    if fn == 277:
                        if level is None and p1 in AV_NAMES: level = int(fval)
                    elif fn == 448: prereq_gfids.append(p1)
            perks[local] = {"edid": edid, "name": name, "desc": desc,
                "level": level, "prereq_gfids": prereq_gfids, "nnam_next": nnam_next, "num_ranks": num_ranks}
        elif tag == "AVIF":
            sub = subrecs(body)
            edid = next((v.rstrip(b"\x00").decode("latin1") for t,v in sub if t=="EDID"), "")
            nodes = []; cur = {}
            for t, v in sub:
                if t == "PNAM" and len(v) >= 4: cur["perk"] = struct.unpack_from("<I", v, 0)[0]
                elif t == "XNAM" and len(v) >= 4: cur["x"] = struct.unpack_from("<I", v, 0)[0]
                elif t == "YNAM" and len(v) >= 4: cur["y"] = struct.unpack_from("<I", v, 0)[0]
                elif t == "INAM": nodes.append({"x": cur.get("x"), "y": cur.get("y"), "perk_gfid": cur.get("perk", 0)}); cur = {}
            if edid and nodes: avif_trees[edid] = nodes

    # Формируем перки из деревьев
    out = []
    for avif_edid, nodes in avif_trees.items():
        branch = BRANCH_RU.get(avif_edid, avif_edid)
        branch_id = BRANCH_ID.get(avif_edid, "")
        for node in nodes:
            gfid = node["perk_gfid"]
            if not gfid: continue
            prefix = gfid >> 24
            local = gfid & 0xFFFFFF
            p = perks.get(local)
            if not p: p = perks.get(gfid)
            if not p: continue
            # prereq
            prereq_edids = []
            seen = set()
            for pfid in p["prereq_gfids"]:
                if pfid == p["nnam_next"]: continue
                pprefix = pfid >> 24; plocal = pfid & 0xFFFFFF
                e = None
                if pprefix == own_prefix and plocal in perks: e = perks[plocal]["edid"]
                elif pprefix == 0: e = None  # ваниль — не резолвим тут
                if e and e not in seen and e != p["edid"]: seen.add(e); prereq_edids.append(e)
            cls = classify_all(p["name"], p["desc"])
            out.append({
                "id": "%08X" % gfid, "mod": mod_label, "branch": branch, "branch_id": branch_id,
                "name": p["name"] or p["edid"], "eid": p["edid"], "formid": "%08X" % gfid,
                "desc": p["desc"], "lvl": p["level"] if p["level"] is not None else -1,
                "prereq": "; ".join(prereq_edids), "ranks": p["num_ranks"],
                "role": cls["role"], "mechanics": cls["mechanics"], "element": cls["element"],
                "magictype": cls["magictype"], "weapon_type": cls["weapon_type"],
                "condition": cls["condition"], "trigger": cls["trigger"],
                "x": node["x"], "y": node["y"], "build": 0,
            })

    # Дедуп
    seen_id = {}
    for o in out: seen_id[o["id"]] = o
    out = list(seen_id.values())
    out.sort(key=lambda p: (p["branch"], p["lvl"], p["eid"]))

    # ── Сравнение с базой ──
    existing = {}
    for f in PERKS_DIR.glob("*.json"):
        for p in json.load(open(f, encoding="utf-8")):
            existing[p["id"]] = p

    new_perks = [o for o in out if o["id"] not in existing]
    changed = [o for o in out if o["id"] in existing and o != existing[o["id"]]]
    print("  новых: %d | изменено: %d | всего: %d" % (len(new_perks), len(changed), len(out)))

    # ── Новые механики/элементы/условия ──
    known_mechs = set()
    known_elements = set()
    known_conditions = set()
    known_triggers = set()
    known_magics = set()
    known_weapons = set()
    for p in existing.values():
        known_mechs.update(p.get("mechanics", []))
        known_elements.update(p.get("element", []))
        known_conditions.update(p.get("condition", []))
        known_triggers.update(p.get("trigger", []))
        known_magics.update(p.get("magictype", []))
        known_weapons.update(p.get("weapon_type", []))

    new_mechs = Counter()
    new_elements = Counter()
    new_conditions = Counter()
    new_triggers = Counter()
    new_magics = Counter()
    new_weapons = Counter()
    for p in out:
        for m in p.get("mechanics", []):
            if m not in known_mechs: new_mechs[m] += 1
        for e in p.get("element", []):
            if e not in known_elements: new_elements[e] += 1
        for c in p.get("condition", []):
            if c not in known_conditions: new_conditions[c] += 1
        for t in p.get("trigger", []):
            if t not in known_triggers: new_triggers[t] += 1
        for m in p.get("magictype", []):
            if m not in known_magics: new_magics[m] += 1
        for w in p.get("weapon_type", []):
            if w not in known_weapons: new_weapons[w] += 1

    if new_mechs or new_elements or new_conditions or new_triggers or new_magics or new_weapons:
        print("\n  === ОБНАРУЖЕНО НОВОЕ ===")
        if new_mechs: print("  Механики:", dict(new_mechs.most_common()))
        if new_elements: print("  Стихии:", dict(new_elements.most_common()))
        if new_magics: print("  Типы магии:", dict(new_magics.most_common()))
        if new_weapons: print("  Оружие:", dict(new_weapons.most_common()))
        if new_conditions: print("  Условия:", dict(new_conditions.most_common()))
        if new_triggers: print("  Триггеры:", dict(new_triggers.most_common()))

    # ── Решения ──
    decisions = {}
    if DECISIONS.exists():
        decisions = json.load(open(DECISIONS, encoding="utf-8"))

    # Записываем
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("  записано: %d -> %s" % (len(out), out_path))

    # Сводка по веткам
    c = Counter(o["branch"] for o in out)
    for b, n in sorted(c.items()): print("    %-28s %d" % (b, n))

    return out, new_perks, changed

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("usage: scan_mod.py <esp> <mod_label> <out_json>")
        sys.exit(1)
    scan_mod(sys.argv[1], sys.argv[2], sys.argv[3])
