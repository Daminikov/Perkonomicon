# Perkonomicon

Локальная база перков Skyrim SE/AE из модов-оверхаулов с веб-интерфейсом для просмотра, фильтрации и отметки «в сборке».

![Python](https://img.shields.io/badge/python-3.11+-blue) ![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

## Возможности

- **4744 перка из 28 модов** (Vanilla + 18 обычных оверхаулов + 9 модов Custom Skills Framework)
- Фильтры: ветка, мод, роль, механика, стихия, тип магии, оружие, условие, триггер, уровень
- Поиск по названию / EditorID / FormID / описанию
- Галочки «в сборке» для планирования билда
- Группировка мод → ветка, эксклюзивный/множественный режим фильтров
- Импорт/экспорт CSV
- Всё локально — без облаков и аккаунтов

## Быстрый старт

```
cd perk-table
start.cmd
```

Откроется http://127.0.0.1:8823/ (Python 3.10+, зависимостей нет — только stdlib).

## Структура

```
perk-table/           # веб-приложение
  app.py              # сервер (http.server, порт 8823)
  index.html          # весь UI (таблица, фильтры, формы)
  start.cmd           # запуск (Windows)
  data/
    mods.json         # список модов
    branches.json     # 20 веток навыков
    perks/<Мод>.json  # перки каждого мода отдельным файлом
    backups/          # автобэкапы при записи (в git не попадают)
```

## Моды в базе

### Обычные (19)

| Мод | Перков |
|---|---|
| Vanilla (Skyrim + DLC + USSEP + USMP) | 199 |
| Ordinator 9.35 | 469 |
| Synergy 1.0.2 | 445 |
| SkyPE 2.0 | 420 |
| Perkus Maximus 0.9b | 357 |
| CHIM 1.3.1 | 347 |
| SkyRE 2.2.3 | 296 |
| Vokrii 3.8.2 | 267 |
| SPERG 1.8 | 245 |
| PerkUP 1.1 | 238 |
| Master of One 2.1 | 222 |
| Requiem 6.0.2 | 220 |
| Perkapalooza 1.2 | 219 |
| Adamant 6.0.4 | 202 |
| Path of Sorcery 3.2 | 138 |
| Paragon 1.0 | 132 |
| Iron Path 1.0.5 | 78 |
| Vanguard Path 1.0 | 70 |
| Smithing Perks Overhaul 2.2 | 10 |

### Custom Skills Framework (9)

| Мод | Перков | Деревья |
|---|---|---|
| Unarmoured Defense 1.1 | 28 | Unarmoured Defense |
| Firmament 1.0 | 34 | Всадник, Исследование, Философия |
| Constellations 1.0 | 27 | Атлетика, Рукопашный бой, Чародейство |
| VIGILANT 2.0 | 20 | Vigilant of Stendarr |
| Hand To Hand 1.1 | 20 | Hand To Hand |
| GLENMORIL 2.1 | 20 | Insight |
| Pyromancy 1.0 | 10 | Pyromancy |
| Draconic Nature 1.4 | 6 | Draconic Nature |
| Pilgrim 1.2 | 5 | Pilgrim |

## Как добавить новый мод

Данные собираются из ESP/ESM модов отдельными скриптами (не входят в репозиторий). Готовый результат — JSON в `perk-table/data/perks/` + строка в `mods.json`.

## Поля перка

`id, mod, branch, branch_id, name, eid, formid, desc, lvl, prereq, ranks, role, mechanics[], element[], magictype[], weapon_type[], condition[], trigger[], x, y, build`

- `build` — галочка «в сборке»
- `csf: true` + `csf_tree` — у CSF-модов
