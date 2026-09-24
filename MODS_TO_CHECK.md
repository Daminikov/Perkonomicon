# Моды с перками для базы — список для ручной проверки

## Основные перк-оверхаулы (уже в базе)

| Мод | Версия | Статус |
|---|---|---|
| Vanilla | — | ✅ в базе (199 перков) |
| Ordinator - Perks of Skyrim | 9.35 | ✅ в базе (469 перков) |
| SPERG - Skyrim Perk Enhancements | 1.8 | ✅ в базе (245 перков) |
| Perkus Maximus | 0.9b | ✅ в базе (357 перков) |
| SkyRE (T3nd0's Skyrim AE Redone) | 2.2.3 | ✅ в базе (296 перков) |
| Vokrii - Minimalistic Perks | 3.8.2 | ✅ в базе (267 перков) |
| Adamant - A Perk Overhaul | 6.0.4 | ✅ в базе (202 перков) |
| Path of Sorcery | 3.2 | ✅ в базе (138 перков) |
| Vanguard Path | 1.0 | ✅ в базе (70 перков) |
| SkyPE - Skyrim Perk Extravaganza | 2.0 | ✅ в базе (420 перков) |
| Iron Path | 1.0.5 | ✅ в базе (78 перков) |
| Master of One | 2.1 | ✅ в базе (222 перков) |
| Synergy | 1.0.2 | ✅ в базе (445 перков) |
| CHIM - Perk Tree Overhaul | 1.3.1 | ✅ в базе (347 перков) |
| Perkapalooza | 1.2 | ✅ в базе (219 перков) |
| Requiem | 6.0.2 | ✅ в базе (220 перков) |
| Paragon | 1.0 | ✅ в базе (132 перков) |

**Итого в базе: 4326 перков**

---

## Установлено пользователем (не загружено в базу)

| Мод | Что добавляет | Статус |
|---|---|---|
| **Smithing Perks Overhaul SE** | Переработанное дерево кузнечного дела (2 варианта: Modified Vanilla / New Perk Tree) | ⚠️ установлен, не в базе |
| **PerkUP Restored SSE - Ultimate Perk Mod** | 70+ новых перков, ранги до 10, многоуровневые | ⚠️ установлен, не в базе |
| **Overlord - Become an Evil Lich (SE-AE)** | Дерево лича (23 перка, некромантия) | ⚠️ установлен, не в базе |
| **Sets of Skills - a Skyrim Class Mod** | Система классов через наборы навыков/перков | ⚠️ установлен, не в базе |

### Custom Skills Framework (установлено, не в базе)

| Мод | Что добавляет | Статус |
|---|---|---|
| **Custom Skills Framework** | Платформа для новых деревьев | ⚠️ установлен, не в базе |
| **Custom Skills - VIGILANT** | Дерево «Вигилант Стендарра» (против нежити/даэдра) | ⚠️ установлен, не в базе |
| **Custom Skills - Hand To Hand** | Дерево рукопашного боя | ⚠️ установлен, не в базе |
| **Custom Skills - Unarmoured Defense** | Дерево защиты без брони | ⚠️ установлен, не в базе |
| **Pyromancy - Custom Skill Tree** | Дерево пиромантии (огонь) | ⚠️ установлен, не в базе |
| **Draconic Nature perk tree** | Дерево «Драконья природа» (перки за подвиги) | ⚠️ установлен, не в базе |

---

## НЕ установлено — кандидаты с Nexus (со ссылками)

### Custom Skills Framework

| Мод | Что добавляет | Ссылка |
|---|---|---|
| **Custom Skills - GLENMORIL** | Дерево для GLENMORIL (ведьмовство) | https://www.nexusmods.com/skyrimspecialedition/mods/44999 |
| **Pilgrim - Custom Skills** | Дерево «Пилигрим» (паломник/жрец) | https://www.nexusmods.com/skyrimspecialedition/mods/67563 |
| **Custom Skills Menu** | Меню для CSF (UI, не перки) | https://www.nexusmods.com/skyrimspecialedition/mods/62423 |

### Отдельные моды

| Мод | Что добавляет | Ссылка |
|---|---|---|
| **Riding skill with own perk tree** | Дерево верховой езды (старый Skyrim LE, требует порт) | https://www.nexusmods.com/skyrim/mods/46415 |
| **Revised Perks of Skyrim** | Правки существующих веток, замена устаревших перков | https://www.nexusmods.com/skyrimspecialedition/mods/103848 |
| **Perk Trees - Unlocked Mechanics and Tweaks** | Близкий к ваниле модульный оверхаул веток | https://www.nexusmods.com/skyrimspecialedition/mods/134760 |

---

## Как проверять

1. Найти ESP/ESM мода в `C:\MO2 Daminikov\mods\<имя мода>`
2. Прогнать через сканер:
   ```
   cd C:\Code\My IDE SKSE\DataBase
   python scan_mod.py "путь\к\моду.esp" "Имя мода" "perk-table\data\perks\Имя мода.json"
   ```
3. Проверить: перков, веток, новые механики (в логе «ОБНАРУЖЕНО НОВОЕ»)
4. Если ок — добавить в `mods.json`

---

## Заметки

- **Custom Skills Framework** — обязательная зависимость для всех Custom Skills-модов. Без него они не работают.
- **Smithing Perks Overhaul SE** — конфликтует с Vokrii/Ordinator в дереве кузнечного дела. Выбрать один.
- **PerkUP** — даёт много перков, но может конфликтовать с другими оверхаулами. Проверить совместимость.
- **Sets of Skills** — система классов, не просто перки. Требует отдельной обработки (классы ≠ ветки).
