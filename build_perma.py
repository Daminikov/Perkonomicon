# -*- coding: utf-8 -*-
"""Сборка Perkus Maximus (4 модуля: Master + Warrior + Thief + Mage) в один файл мода.

Ключевое:
- Деревья AVIF в каждом модуле ссылаются на перки через ГЛОБАЛЬНЫЕ formid с префиксом мастера.
  prefix=00..03 = Skyrim/Update/Dragonborn/Dawnguard; 04 = PerkusMaximus_Master (в модулях).
- Резолвим через мастера того модуля, где лежит дерево.
- Текст (FULL/DESC) прямо в записях, не LString.
"""
import json
import struct
import sys
import zlib
from pathlib import Path
from collections import defaultdict, Counter

UNPACKED = 0x40000
BASE = Path(r"C:/MO2 Daminikov/mods/T3nd0's Perkus Maximus SSE")
OUT = Path(r"C:/Code/My IDE SKSE/DataBase/perk-table/data/perks/Perkus Maximus.json")

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

MODULES = ["PerkusMaximus_Master","PerkusMaximus_Warrior","PerkusMaximus_Thief","PerkusMaximus_Mage"]
MODULE_SHORT = {"PerkusMaximus_Master":"Master","PerkusMaximus_Warrior":"Warrior",
                "PerkusMaximus_Thief":"Thief","PerkusMaximus_Mage":"Mage"}

# ── 1. Читаем все перки всех модулей. Ключ: ПОЛНЫЙ fid (у PerMa fid с префиксом модуля) ──
perks = {}           # full_fid -> perk
perk_module = {}     # full_fid -> module name
for mn in MODULES:
    esp = BASE / (mn + ".esp")
    masters = read_masters(esp)
    for tag, fid, body in iter_records(esp):
        if tag != "PERK": continue
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
        perks[fid] = {"module":mn,"edid":edid,"name":full,"desc":desc,"level":level,
            "prereq_gfids":prereq_gfids,"nnam_next":nnam_next,"num_ranks":num_ranks}
        perk_module[fid] = mn

# ── 2. Индекс по локальному fid (младшие 24 бита) — для перков со старым форматом ──
by_local = defaultdict(list)
for fid, pk in perks.items():
    by_local[fid & 0xFFFFFF].append(pk)

print("перков прочитано: %d" % len(perks))

# ── 3. Деревья: резолвим через мастера модуля, где лежит дерево ──
out = []
seen_keys = set()
for mn in MODULES:
    esp = BASE / (mn + ".esp")
    masters = read_masters(esp)
    for tag, fid, body in iter_records(esp):
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
            # У PerMa fid полные (с префиксом) — резолвим напрямую
            target = perks.get(gfid)
            if target is None:
                continue  # ванильный или чужой — не берём
            if "NPC" in target["edid"].upper(): continue
            key = (target["edid"], branch)
            if key in seen_keys: continue
            seen_keys.add(key)
            # prereq
            pre = []
            for pf in target["prereq_gfids"]:
                if pf == target["nnam_next"]: continue
                e = None
                pp = perks.get(pf)
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
            out.append({"id":target["edid"]+"_"+MODULE_SHORT[target["module"]],"mod":"Perkus Maximus",
                "branch":branch,"branch_id":bid,
                "name":target["name"] or target["edid"],"eid":target["edid"],"formid":"%08X"%gfid,
                "desc":target["desc"],"lvl":target["level"] if target["level"] is not None else -1,
                "prereq":"; ".join(pre),"ranks":target["num_ranks"],"tags":tags,
                "x":node.get("x"),"y":node.get("y"),"build":0})

OUT.parent.mkdir(parents=True, exist_ok=True)
json.dump(out, open(OUT,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
print("записано: %d -> %s" % (len(out), OUT))
c = Counter(p["branch"] for p in out)
for k,v in sorted(c.items()): print("  %-28s %d" % (k,v))
