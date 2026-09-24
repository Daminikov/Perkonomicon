# -*- coding: utf-8 -*-
"""Сборка Skyrim AE Redone (SkyRE): Core.esm (перки) + Main.esp (деревья).

Структура:
- Core.esm: 542 PERK (текст в записях, edid вида skyre_XXX)
- Main.esp: 180 PERK (переопределения ванильных) + 18 AVIF деревьев
- Деревья в Main.esp ссылаются на перки из Core.esm через глобальные formid
  (prefix 06 = Core.esm, т.к. в мастерах Main он на позиции 6)
"""
import json
import struct
import zlib
from pathlib import Path
from collections import Counter

UNPACKED = 0x40000
BASE = Path(r"C:/MO2 Daminikov/mods/T3nd0's Skyrim AE Redone")
OUT = Path(r"C:/Code/My IDE SKSE/DataBase/perk-table/data/perks/SkyRE.json")

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

VANILLA_EDID = {}
_vj = Path(r"C:\Code\My IDE SKSE\DataBase\perk-table\data\perks\Vanilla.json")
if _vj.exists():
    for _p in json.load(open(_vj, encoding="utf-8")):
        _fid = _p.get("formid","")
        if len(_fid)==8: VANILLA_EDID[int(_fid,16)&0xFFFFFF] = _p["eid"]

def iter_records(path):
    data = Path(path).read_bytes()
    hs = struct.unpack_from("<i", data, 4)[0]
    def walk(start, end):
        pos = start
        while pos+24 <= end:
            tag = data[pos:pos+4].decode("latin1"); size = struct.unpack_from("<i", data, pos+4)[0]
            flags = struct.unpack_from("<I", data, pos+8)[0]; fid = struct.unpack_from("<I", data, pos+12)[0]
            if tag == "GRUP":
                if size < 24 or pos+size > end: return
                yield from walk(pos+24, pos+size); pos += size; continue
            if pos+24+size > end: return
            body = data[pos+24:pos+24+size]
            if flags & UNPACKED:
                try: body = zlib.decompress(body[4:])
                except: body = b""
            yield tag, fid, body
            pos += 24 + size
    yield from walk(24+hs, len(data))

def read_masters(path):
    d = Path(path).read_bytes(); hs = struct.unpack_from("<i", d, 4)[0]
    ms=[]; pos=24
    while pos+6<=24+hs and pos+6<=len(d):
        t=d[pos:pos+4].decode("latin1"); ln=struct.unpack_from("<H",d,pos+4)[0]
        if t=="MAST": ms.append(d[pos+6:pos+6+ln].rstrip(b"\x00").decode("latin1"))
        pos+=6+ln
    return ms

def parse_perk(body):
    subs = []; i = 0
    while i+6 <= len(body):
        t = body[i:i+4].decode("latin1"); ln = struct.unpack_from("<H", body, i+4)[0]
        subs.append((t, body[i+6:i+6+ln])); i += 6+ln
    edid = next((v.rstrip(b"\x00").decode("latin1","replace") for t,v in subs if t=="EDID"), "")
    full = next((v.rstrip(b"\x00").decode("utf-8","replace") for t,v in subs if t=="FULL"), "")
    desc = next((v.rstrip(b"\x00").decode("utf-8","replace") for t,v in subs if t=="DESC"), "")
    level = None; prereq_gfids = []; nnam_next = None; num_ranks = 1
    for t, v in subs:
        if t=="DATA" and len(v)>=5: num_ranks = v[2]
        elif t=="NNAM" and len(v)>=4: nnam_next = struct.unpack_from("<I", v, 0)[0]
        elif t=="CTDA" and len(v)>=28:
            fn = struct.unpack_from("<H", v, 8)[0]; p1 = struct.unpack_from("<I", v, 12)[0]
            fval = struct.unpack_from("<f", v, 4)[0]
            if fn==277 and p1 in AV_NAMES:
                if level is None: level = int(fval)
            elif fn==448: prereq_gfids.append(p1)
    return {"edid":edid,"name":full,"desc":desc,"level":level,
            "prereq_gfids":prereq_gfids,"nnam_next":nnam_next,"num_ranks":num_ranks}

# ── 1. Перки из обоих файлов. Ключ: полный fid ──
perks = {}
for fname in ["Skyrim AE Redone - Core.esm", "Skyrim AE Redone - Main.esp"]:
    for tag, fid, body in iter_records(BASE / fname):
        if tag == "PERK":
            perks[fid] = parse_perk(body)
            perks[fid]["src"] = fname

print("перков: %d (Core=%d, Main=%d)" % (len(perks),
    sum(1 for p in perks.values() if "Core" in p["src"]),
    sum(1 for p in perks.values() if "Main" in p["src"])))

# ── 2. Деревья из Main.esp ──
main_esp = BASE / "Skyrim AE Redone - Main.esp"
main_masters = read_masters(main_esp)
# карта prefix -> имя мастера (без расширения)
def master_name(prefix, masters):
    if prefix < len(masters):
        return masters[prefix]
    return None

out = []
seen_keys = set()
for tag, fid, body in iter_records(main_esp):
    if tag != "AVIF": continue
    subs = []; i=0
    while i+6<=len(body):
        t=body[i:i+4].decode("latin1"); ln=struct.unpack_from("<H",body,i+4)[0]
        subs.append((t, body[i+6:i+6+ln])); i+=6+ln
    avif_edid = next((v.rstrip(b"\x00").decode("latin1") for t,v in subs if t=="EDID"), "")
    if not avif_edid: continue
    branch = BRANCH_RU.get(avif_edid, avif_edid)
    bid = BRANCH_ID.get(avif_edid, "")
    nodes=[]; cur={}
    for t,v in subs:
        if t=="PNAM" and len(v)>=4: cur["perk"]=struct.unpack_from("<I",v,0)[0]
        elif t=="XNAM" and len(v)>=4: cur["x"]=struct.unpack_from("<i",v,0)[0]
        elif t=="YNAM" and len(v)>=4: cur["y"]=struct.unpack_from("<i",v,0)[0]
        elif t=="INAM" and len(v)>=4:
            cur["idx"]=struct.unpack_from("<I",v,0)[0]; nodes.append(cur); cur={}
    for node in nodes:
        gfid = node.get("perk", 0)
        if not gfid: continue
        # SkyRE: prefix 06 в Main.esp = Core.esm (prefix 05 в Core.esm). Нормализуем.
        lookup = gfid
        if (gfid >> 24) == 0x06:
            lookup = 0x05000000 | (gfid & 0xFFFFFF)
        target = perks.get(lookup) or perks.get(gfid)
        if target is None: continue
        if "NPC" in target["edid"].upper(): continue
        key = (target["edid"], branch)
        if key in seen_keys: continue
        seen_keys.add(key)
        # prereq
        pre = []
        for pf in target["prereq_gfids"]:
            if pf == target["nnam_next"]: continue
            e = None
            plookup = pf
            if (pf >> 24) == 0x06:
                plookup = 0x05000000 | (pf & 0xFFFFFF)
            pp = perks.get(plookup) or perks.get(pf)
            if pp: e = pp["edid"]
            elif (pf>>24)==0: e = VANILLA_EDID.get(pf&0xFFFFFF)
            if e and e != target["edid"] and e not in pre: pre.append(e)
        # tags
        txt = (target["name"]+" "+target["desc"]).lower()
        tags=[]
        for kw,t in [("меч","sword"),("топор","axe"),("булав","mace"),("кинжал","dagger"),
                     ("двух рук","dual"),("парн","dual"),("лук","bow"),("арбалет","bow"),
                     ("брон","armor"),("щит","shield"),("магия","magic"),("заклинан","magic"),
                     ("зель","alchemy"),("яд","poison"),("скрытн","sneak"),("взлом","lockpick"),
                     ("карман","pickpocket"),("критическ","crit"),("силов","power"),("кровотеч","bleed")]:
            if kw in txt: tags.append(t)
        if not tags: tags=["core"]
        out.append({"id":target["edid"],"mod":"SkyRE","branch":branch,"branch_id":bid,
            "name":target["name"] or target["edid"],"eid":target["edid"],"formid":"%08X"%gfid,
            "desc":target["desc"],"lvl":target["level"] if target["level"] is not None else -1,
            "prereq":"; ".join(pre),"ranks":target["num_ranks"],"tags":tags,
            "x":node.get("x"),"y":node.get("y"),"build":0})

OUT.parent.mkdir(parents=True, exist_ok=True)
json.dump(out, open(OUT,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
print("записано: %d -> %s" % (len(out), OUT))
c = Counter(p["branch"] for p in out)
for k,v in sorted(c.items()): print("  %-28s %d" % (k,v))
