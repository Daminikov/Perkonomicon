# -*- coding: utf-8 -*-
"""Сборка перков из мода-оверхаула (Ordinator и подобных).

Отличия от ванильного сборщика:
- Текст (FULL/DESC) прямо в записях, не LString — читаем как строки.
- Деревья = AVIF-переопределения в этом ESP, узлы → перки.
- FormID: префикс по мастерам (0=Skyrim, 1=Update, 2=Dragonborn, 3=свой).
- Мусорные перки (NPC-перки, дубликаты) помечаются, но включаются — юзер решит.
"""
import json
import struct
import sys
import zlib
from pathlib import Path
from collections import defaultdict

UNPACKED = 0x00040000

# Ванильные EditorID по локальному formid (Skyrim.esm) — для резолва prereq.
# Загружаем из уже собранной ванильной базы.
VANILLA_EDID = {}
_vj = Path(r"C:\Code\My IDE SKSE\DataBase\perk-table\data\perks\Vanilla.json")
if _vj.exists():
    for _p in json.load(open(_vj, encoding="utf-8")):
        _fid = _p.get("formid", "")
        if len(_fid) == 8:
            VANILLA_EDID[int(_fid, 16) & 0xFFFFFF] = _p["eid"]

AV_NAMES = {0:"Aggression",1:"Confidence",2:"Energy",3:"Morality",4:"Mood",5:"Assistance",
            6:"One-Handed",7:"Two-Handed",8:"Marksman",9:"Block",10:"Smithing",11:"HeavyArmor",
            12:"LightArmor",13:"Pickpocket",14:"Lockpicking",15:"Sneak",16:"Alchemy",17:"Speech",
            18:"Alteration",19:"Conjuration",20:"Destruction",21:"Illusion",22:"Restoration",
            23:"Enchanting"}

BRANCH_RU = {"AVOneHanded":"Одноручное оружие","AVTwoHanded":"Двуручное оружие","AVMarksman":"Стрельба",
    "AVBlock":"Блокирование","AVSmithing":"Кузнечное дело","AVHeavyArmor":"Тяжёлая броня",
    "AVLightArmor":"Лёгкая броня","AVPickpocket":"Карманные кражи","AVLockpicking":"Взлом",
    "AVSneak":"Скрытность","AVAlchemy":"Алхимия","AVSpeechcraft":"Красноречие",
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


# ── Классификация (встроенная, без retag.py) ──
import re

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

def classify_text(text, rules):
    t = text.lower()
    out = []
    for tag, kws in rules:
        for kw in kws:
            if kw.startswith("\\") or any(c in kw for c in "[](){}.*+?|^$"):
                if re.search(kw, t):
                    out.append(tag); break
            elif kw in t:
                out.append(tag); break
    return out

def classify_role(text):
    t = text.lower()
    for role, kws in ROLE_RULES:
        for kw in kws:
            if kw in t:
                return role
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

def detect_tags(text):
    t = text.lower()
    tags = set()
    for kw, tag in [("меч", "sword"), ("топор", "axe"), ("булав", "mace"),
                    ("кинжал", "dagger"), ("когт", "dagger"),
                    ("двух рук", "dual"), ("обеих руках", "dual"), ("парн", "dual"),
                    ("лук", "bow"), ("арбалет", "bow"), ("стрел", "bow"),
                    ("вампир", "vampire"), ("оборотен", "werewolf"), ("волк", "werewolf"),
                    ("заклинан", "magic"), ("магии", "magic"), ("магия", "magic"),
                    ("брон", "armor"), ("щит", "block"), ("блок", "block"),
                    ("силов", "power"), ("крит", "crit"), ("скрыт", "sneak"), ("тих", "sneak"),
                    ("яд", "poison"), ("зель", "potion"), ("алхим", "alchemy"),
                    ("карман", "pickpocket"), ("взлом", "lockpick"), ("замок", "lockpick"),
                    ("кузнец", "smithing"), ("кузни", "smithing"), ("зачаров", "enchant"),
                    ("красноречи", "speech"), ("торгов", "speech"), ("крик", "shout")]:
        if kw in t: tags.add(tag)
    return sorted(tags) if tags else ["core"]


def build_mod(esp_path, mod_label, out_path):
    print("=== %s ===" % mod_label)
    masters = read_masters(esp_path)
    print("  мастера:", masters)
    master_count = len(masters)
    # префикс своего плагина = master_count (как hex-индекс)
    own_prefix = master_count

    # 1. Читаем PERK и AVIF
    perks = {}        # local_fid -> perk dict
    avif_trees = {}   # avif_edid -> nodes
    avif_names = {}   # local_fid -> edid (для AVIF)

    for tag, fid, body in iter_records(esp_path):
        sub = subrecs(body)
        local = fid & 0xFFFFFF
        if tag == "PERK":
            edid = name = desc = ""
            full_id = desc_id = None
            level = None
            prereq_gfids = []
            nnam_next = None
            effects = []
            num_ranks = 1
            for t, v in sub:
                if t == "EDID":
                    edid = v.rstrip(b"\x00").decode("latin1", "replace")
                elif t == "FULL":
                    # текст или LString id
                    if len(v) == 4:
                        full_id = struct.unpack("<I", v)[0]
                    else:
                        name = v.rstrip(b"\x00").decode("utf-8", "replace")
                elif t == "DESC":
                    if len(v) == 4:
                        desc_id = struct.unpack("<I", v)[0]
                    else:
                        desc = v.rstrip(b"\x00").decode("utf-8", "replace")
                elif t == "DATA" and len(v) == 5:
                    num_ranks = v[2]
                elif t == "NNAM" and len(v) >= 4:
                    nnam_next = struct.unpack_from("<I", v, 0)[0]
                elif t == "CTDA" and len(v) >= 28:
                    fn = struct.unpack_from("<H", v, 8)[0]
                    p1 = struct.unpack_from("<I", v, 12)[0]
                    fval = struct.unpack_from("<f", v, 4)[0]
                    if fn == 277:
                        if level is None and p1 in AV_NAMES:
                            level = int(fval)
                    elif fn == 448:
                        prereq_gfids.append(p1)
                elif t == "EPFT":
                    effects.append({"type": v[0] if len(v) else 0, "value": None})
                elif t == "EPFD" and len(v) >= 4:
                    if effects:
                        effects[-1]["value"] = struct.unpack_from("<f", v, 0)[0]
            perks[local] = {
                "edid": edid, "local_fid": "%06X" % local,
                "name": name, "desc": desc, "full_id": full_id, "desc_id": desc_id,
                "level": level, "prereq_gfids": prereq_gfids, "nnam_next": nnam_next,
                "effects": effects, "num_ranks": num_ranks,
            }
        elif tag == "AVIF":
            edid = ""
            nodes = []
            cur = {}
            for t, v in sub:
                if t == "EDID":
                    edid = v.rstrip(b"\x00").decode("latin1")
                elif t == "PNAM" and len(v) >= 4:
                    cur["perk"] = struct.unpack_from("<I", v, 0)[0]
                elif t == "XNAM" and len(v) >= 4:
                    cur["x"] = struct.unpack_from("<I", v, 0)[0]
                elif t == "YNAM" and len(v) >= 4:
                    cur["y"] = struct.unpack_from("<I", v, 0)[0]
                elif t == "INAM":
                    nodes.append({"x": cur.get("x"), "y": cur.get("y"), "perk_gfid": cur.get("perk", 0)})
                    cur = {}
            if edid and nodes:
                avif_trees[edid] = nodes
                avif_names[local] = edid

    print("  PERK: %d | деревьев AVIF: %d" % (len(perks), len(avif_trees)))

    # 2. Резолвим глобальные formid узлов в (local_fid)
    # глобальный formid = (prefix << 24) | local. prefix 0..master_count-1 = мастера, own = свой.
    # Нам нужны перки только из этого мода (own_prefix) — но ванильные перки (prefix 0) тоже могут быть в дереве.
    # Для них берём только локальный id (prefix 0 = Skyrim.esm) — из ванильной базы.
    # Собираем реестр: global_fid -> local_fid (для своих) и global_fid -> "vanilla" (prefix 0)
    def resolve(gfid):
        prefix = gfid >> 24
        local = gfid & 0xFFFFFF
        if prefix == own_prefix:
            return (mod_label, local)
        elif prefix < master_count:
            # из мастера — для отображения prereq и т.п.
            return ("__master__%s" % masters[prefix] if prefix < len(masters) else "__master0", local)
        return (None, local)

    # 3. Формируем список перков из деревьев
    # Реестр для резолва prereq: global_fid -> edid
    gfid_to_edid = {}
    for (label, local), p in [( (mod_label, l), p) for l, p in perks.items()]:
        gfid_to_edid[(own_prefix << 24) | local if False else 0] = None  # placeholder
    # проще: для prereq маппим global_fid -> edid через perks (свои) и известные ванильные edid (по local)
    vanilla_edid = {}  # local -> edid (из Skyrim.esm) — для резолва prereq на ванильные перки

    out = []
    for avif_edid, nodes in avif_trees.items():
        branch = BRANCH_RU.get(avif_edid, avif_edid)
        branch_id = BRANCH_ID.get(avif_edid, "")
        for node in nodes:
            gfid = node["perk_gfid"]
            if not gfid:
                continue
            prefix = gfid >> 24
            local = gfid & 0xFFFFFF
            # берём перки любого префикса, если они есть в файле (не только свои)
            p = perks.get(local)
            if not p:
                # пробуем полный fid (перки с префиксом мастера, например Mysticism)
                p = perks.get(gfid)
            if not p:
                continue
            # prereq
            prereq_edids = []
            seen = set()
            for pfid in p["prereq_gfids"]:
                if pfid == p["nnam_next"]:
                    continue
                pprefix = pfid >> 24
                plocal = pfid & 0xFFFFFF
                if pprefix == own_prefix and plocal in perks:
                    e = perks[plocal]["edid"]
                elif pprefix == 0:
                    e = VANILLA_EDID.get(plocal, "%06X" % plocal)
                elif pprefix == 2:  # Dawnguard
                    e = VANILLA_EDID.get(plocal, "%06X" % plocal)
                elif pprefix == 4:  # Dragonborn
                    e = VANILLA_EDID.get(plocal, "%06X" % plocal)
                else:
                    e = "%06X" % plocal
                if e and e not in seen and e != p["edid"]:
                    seen.add(e)
                    prereq_edids.append(e)
            tags = detect_tags(p["name"] + " " + p["desc"])
            cls = classify_all(p["name"], p["desc"])
            # rank chain
            ranks = p["num_ranks"]
            rank_data = []
            cur_fid = local
            for _ in range(min(ranks, 8)):
                rp = perks.get(cur_fid)
                if not rp: break
                rank_data.append({"edid": rp["edid"], "level": rp["level"], "name": rp["name"], "desc": rp["desc"]})
                nxt = rp.get("nnam_next")
                if not nxt: break
                nx_local = nxt & 0xFFFFFF
                if (nxt >> 24) != own_prefix or nx_local not in perks:
                    break
                cur_fid = nx_local
            out.append({
                "id": "%08X" % gfid,
                "mod": mod_label,
                "branch": branch,
                "branch_id": branch_id,
                "name": p["name"] or p["edid"],
                "eid": p["edid"],
                "formid": "%08X" % gfid,
                "desc": p["desc"],
                "lvl": p["level"] if p["level"] is not None else -1,
                "prereq": "; ".join(prereq_edids),
                "ranks": ranks,
                "rank_data": rank_data,
                "tags": tags,
                "role": cls["role"],
                "mechanics": cls["mechanics"],
                "element": cls["element"],
                "magictype": cls["magictype"],
                "weapon_type": cls["weapon_type"],
                "condition": cls["condition"],
                "trigger": cls["trigger"],
                "x": node["x"], "y": node["y"],
                "build": 0,
            })
    # дедуп по id (перк может быть в двух позициях дерева)
    seen_id = {}
    for o in out:
        seen_id[o["id"]] = o
    out = list(seen_id.values())
    out.sort(key=lambda p: (p["branch"], p["lvl"], p["eid"]))
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("  записано перков: %d -> %s" % (len(out), out_path))
    # сводка по веткам
    from collections import Counter
    c = Counter(o["branch"] for o in out)
    for b, n in sorted(c.items()):
        print("    %-30s %d" % (b, n))


if __name__ == "__main__":
    esp = sys.argv[1] if len(sys.argv) > 1 else r"C:\MO2 Daminikov\mods\Ordinator - Perks of Skyrim\Ordinator - Perks of Skyrim.esp"
    label = sys.argv[2] if len(sys.argv) > 2 else "Ordinator 9.35"
    out = sys.argv[3] if len(sys.argv) > 3 else r"C:\Code\My IDE SKSE\DataBase\perk-table\data\perks\Ordinator 9.35.json"
    build_mod(esp, label, out)
