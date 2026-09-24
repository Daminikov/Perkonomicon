# -*- coding: utf-8 -*-
"""
Локальный сервер таблицы перков Skyrim.

Данные лежат в файлах:
  data/mods.json          — список сборок (модов)
  data/branches.json      — список веток (18 ванильных + свои)
  data/perks/<Мод>.json   — перки каждого мода, ОТДЕЛЬНЫМ файлом
  data/backups/           — автоматические бэкапы при каждом сохранении

Запуск:  python app.py            (откроет браузер сам)
         python app.py --no-browser --port 8823
"""
import argparse
import json
import os
import shutil
import socket
import sys
import threading
import time
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
PERKS = os.path.join(DATA, "perks")
BACKUPS = os.path.join(DATA, "backups")

DEFAULT_MODS = [
    "Vanilla", "Adamant 5.9.2", "Ordinator 9.31", "Vokrii 3.8.2",
    "CHIM - Perk Tree Overhaul 1.2", "SkyRe 2.1.2", "SkyPE 2.0", "Iron Path 1.0.5",
    "Perkus Maximus Beta 0.9", "Synergy Beta 1.10", "Paragon 1.0", "Perkapalooza 1.1",
    "SPERG 1.8", "Master of One 2.1", "Requiem 6.0.2",
]

# 18 ванильных веток (деревья навыков) оригинального Skyrim
DEFAULT_BRANCHES = [
    {"id": "one-handed",  "name": "Одноручное оружие", "vanilla": True},
    {"id": "two-handed",  "name": "Двуручное оружие",  "vanilla": True},
    {"id": "archery",     "name": "Стрельба",          "vanilla": True},
    {"id": "block",       "name": "Блокирование",      "vanilla": True},
    {"id": "smithing",    "name": "Кузнечное дело",    "vanilla": True},
    {"id": "heavy-armor", "name": "Тяжёлая броня",     "vanilla": True},
    {"id": "light-armor", "name": "Лёгкая броня",      "vanilla": True},
    {"id": "pickpocket",  "name": "Карманные кражи",   "vanilla": True},
    {"id": "lockpicking", "name": "Взлом",             "vanilla": True},
    {"id": "sneak",       "name": "Скрытность",        "vanilla": True},
    {"id": "alchemy",     "name": "Алхимия",           "vanilla": True},
    {"id": "speech",      "name": "Красноречие",       "vanilla": True},
    {"id": "illusion",    "name": "Иллюзия",           "vanilla": True},
    {"id": "conjuration", "name": "Колдовство",        "vanilla": True},
    {"id": "destruction", "name": "Разрушение",        "vanilla": True},
    {"id": "restoration", "name": "Восстановление",    "vanilla": True},
    {"id": "alteration",  "name": "Изменение",         "vanilla": True},
    {"id": "enchanting",  "name": "Зачарование",       "vanilla": True},
]

BAD_CHARS = '\\/:*?"<>|'


def safe_name(mod: str) -> str:
    out = "".join(("-" if c in BAD_CHARS else c) for c in (mod or "").strip())
    out = out.rstrip(". ") or "mod"
    return out


def perk_file(mod: str) -> str:
    return os.path.join(PERKS, safe_name(mod) + ".json")


def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json_atomic(path, obj, backup=True):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if backup and os.path.exists(path):
        os.makedirs(BACKUPS, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d_%H%M%S")
        base = os.path.splitext(os.path.basename(path))[0]
        shutil.copy2(path, os.path.join(BACKUPS, "%s_%s.json" % (base, stamp)))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def ensure_data():
    os.makedirs(PERKS, exist_ok=True)
    os.makedirs(BACKUPS, exist_ok=True)
    if not os.path.exists(os.path.join(DATA, "mods.json")):
        write_json_atomic(os.path.join(DATA, "mods.json"), DEFAULT_MODS, backup=False)
    if not os.path.exists(os.path.join(DATA, "branches.json")):
        write_json_atomic(os.path.join(DATA, "branches.json"), DEFAULT_BRANCHES, backup=False)
    mods = read_json(os.path.join(DATA, "mods.json"), DEFAULT_MODS)
    for m in mods:
        p = perk_file(m)
        if not os.path.exists(p):
            write_json_atomic(p, [], backup=False)


def load_state():
    mods = read_json(os.path.join(DATA, "mods.json"), DEFAULT_MODS)
    branches = read_json(os.path.join(DATA, "branches.json"), DEFAULT_BRANCHES)
    perks = {}
    files = {}
    for m in mods:
        p = perk_file(m)
        perks[m] = read_json(p, [])
        files[m] = os.path.relpath(p, ROOT).replace("\\", "/")
    return {"mods": mods, "branches": branches, "perks": perks, "files": files}


class Handler(BaseHTTPRequestHandler):
    server_version = "PerkTable/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    # ── helpers ────────────────────────────────────────────
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _static(self, rel):
        if rel in ("", "/"):
            rel = "index.html"
        rel = unquote(rel).lstrip("/")
        path = os.path.normpath(os.path.join(ROOT, rel))
        if not path.startswith(ROOT) or not os.path.isfile(path):
            self.send_error(404, "Not found")
            return
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
            ".woff2": "font/woff2",
            ".csv": "text/csv; charset=utf-8",
        }.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except ValueError:
            return {}

    # ── routes ─────────────────────────────────────────────
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/state":
            self._json(load_state())
        elif path == "/api/ping":
            self._json({"ok": True, "root": ROOT})
        else:
            self._static(path)

    def do_POST(self):
        path = urlparse(self.path).path
        data = self._body()

        if path == "/api/save":
            mod = (data.get("mod") or "").strip()
            perks = data.get("perks")
            if not mod or not isinstance(perks, list):
                return self._json({"ok": False, "error": "нужен mod и perks[]"}, 400)
            write_json_atomic(perk_file(mod), perks)
            return self._json({"ok": True, "file": os.path.relpath(perk_file(mod), ROOT).replace("\\", "/"),
                               "count": len(perks)})

        if path == "/api/save-all":
            perks_map = data.get("perks") or {}
            saved = []
            for mod, items in perks_map.items():
                if isinstance(items, list):
                    write_json_atomic(perk_file(mod), items)
                    saved.append(mod)
            return self._json({"ok": True, "saved": saved})

        if path == "/api/mods":
            mods = data.get("mods")
            if not isinstance(mods, list):
                return self._json({"ok": False, "error": "нужен mods[]"}, 400)
            mods = [str(m).strip() for m in mods if str(m).strip()]
            write_json_atomic(os.path.join(DATA, "mods.json"), mods)
            for m in mods:
                if not os.path.exists(perk_file(m)):
                    write_json_atomic(perk_file(m), [], backup=False)
            return self._json({"ok": True, "mods": mods})

        if path == "/api/branches":
            branches = data.get("branches")
            if not isinstance(branches, list):
                return self._json({"ok": False, "error": "нужен branches[]"}, 400)
            write_json_atomic(os.path.join(DATA, "branches.json"), branches)
            return self._json({"ok": True, "branches": branches})

        self.send_error(404, "Not found")


def free_port(start):
    for p in range(start, start + 40):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise SystemExit("нет свободного порта рядом с %s" % start)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8823)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    ensure_data()
    port = free_port(args.port)
    url = "http://127.0.0.1:%d/" % port
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("Таблица перков запущена: %s" % url)
    print("Данные: %s" % DATA)
    print("Остановить: Ctrl+C или просто закрой это окно.")
    if not args.no_browser:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлено.")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()