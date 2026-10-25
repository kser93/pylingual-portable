# PyLingual Portable

Portable (offline-first) версия [PyLingual](https://github.com/syssec-utd/pylingual) — декомпилятора Python bytecode с поддержкой CPU/GPU, MCP-сервером и итеративным patch-loop для агентов.

## Статус

Windows x64: portable runtime установлен и проверен. Реализованы локальный CLI, **MCP-сервер (stdio + Streamable HTTP)**, **patch-loop с exact verification** и **OpenCode harness** (агент, skill, команды, evaluation runner). Установлены toolchain-ы и **model packs для всех версий Python 3.6–3.15**. Все 10 версий прошли end-to-end decompile на тестовом файле (GPU, 100% perfect). Следующие шаги — baseline через harness и ручной updater.

### Установлено локально

| Компонент | Путь/версия |
|---|---|
| Python runtime | `runtime/python-3.15.1` (3.15.1, GIL) |
| torch | 2.14.1+cu130 (CUDA 13.0, cuDNN 9.24) |
| transformers / tokenizers | 5.19.0 / 0.23.3 |
| numpy / xdis | 2.5.4 / 6.3.1.dev0 |
| PyLingual source | `vendor/pylingual` (submodule, upstream v0.1.0, commit `11a1516d`) |
| Toolchains | `toolchains/cpython-*` для Python 3.6–3.15 |
| Model packs | Python 3.6–3.15 (`models/hf-cache`, 10/10 complete) |
| Local runner | `src/pylingual_portable`; upstream source — `vendor/pylingual` (submodule) через `PYTHONPATH` (без training-зависимостей) |
| OpenCode harness | `.opencode/` (agent/skill/commands/MCP), `harness/`, `scripts/opencode_harness.py` |

GPU проверен на **NVIDIA GeForce RTX 5070 Ti**, compute capability 12.0: `torch.cuda.is_available() = True`, CUDA smoke прошёл. End-to-end decompile на тестовом файле дал **100% perfect для всех 10 версий Python 3.6–3.15**; Python 3.12 дополнительно проверен на CPU. `vendor/pylingual/test/Conditional.py` на 3.12 — 100% (43 code object-а). Проверен перенос всей сборки в другой каталог и запуск из другого `cwd` — работает без изменения путей.

Все 10 model packs проверены: `segmenter` и `statement` `model.safetensors` присутствуют, размеры совпадают, `.part`/`.incomplete` отсутствуют. В этом окружении `hf-xet` зависал на старых репозиториях; скрипты используют `HF_HUB_DISABLE_XET=1`.

### Upstream-компоненты (git submodules)

`vendor/pylingual` и `vendor/xdis-src` подключены как git submodules и
зафиксированы на точных upstream-коммитах. Версии, коммиты, лицензии и хэши
деревьев записаны в [`vendor/components.json`](vendor/components.json);
процедура обновления и политика патчей — в [`vendor/UPSTREAM.md`](vendor/UPSTREAM.md).

Клонирование вместе с подмодулями:

```powershell
git clone --recurse-submodules https://github.com/kser93/pylingual-portable.git
```

Если репозиторий уже склонирован без подмодулей:

```powershell
git submodule update --init --recursive
```

Архив GitHub «Download ZIP» не содержит содержимое подмодулей и не подходит
для запуска — используйте `git clone` с `--recurse-submodules`.

| Компонент | Версия | Pin | Лицензия | Локальные патчи |
|---|---|---|---|---|
| PyLingual | 0.1.0 | tag `v0.1.0`, commit `11a1516d...` | GPL-3.0-only | нет |
| xdis | 6.3.1.dev0 | commit `51e36c42...` | GPL-2.0-or-later | нет |

Интеграция с upstream сосредоточена в `src/pylingual_portable/upstream.py`: импорты, три runtime-замены (`load_models`, `compile_version`, `Decompiler.run_cflow_reconstruction`) и проверка контракта API. Третья замена обрабатывает hash-based `.pyc` без timestamp (`timestamp=None`), не меняя байткод. Исходники upstream не редактируются.

Проверка целостности, пинов и контракта:

```powershell
.\scripts\python.cmd .\scripts\check_vendor.py
.\scripts\python.cmd -m unittest tests.test_vendor_manifest
.\scripts\python.cmd -m unittest tests.test_timestamp_patch
.\scripts\python.cmd -m unittest tests.test_upstream_contract
```

`check_vendor.py` проверяет регистрацию в `.gitmodules`, HEAD каждого
подмодуля, gitlink в суперпроекте (если доступен Git), хэш содержимого и
наличие лицензий. Пины со стороны Git показывает
`git submodule status --recursive`.

Модели привязаны к конкретным HF-ревизиям через `models/model-links.json`; `models.py` загружает только snapshot с указанным SHA и не выбирает «самый свежий» файл из кэша.

### Локальный запуск

```powershell
.\pylingual.cmd doctor
.\pylingual.cmd decompile .\workspace\samples\simple.pyc -o .\workspace\samples\out.py --version 3.12
.\pylingual.cmd decompile .\workspace\samples\simple.pyc -o .\workspace\samples\out-cpu.py --version 3.12 --device cpu
.\pylingual.cmd decompile .\workspace\samples\simple36.pyc -o .\workspace\samples\out36.py --version 3.6
```

Все переменные (`PYTHONHOME`, `PYTHONPATH`, `HF_HOME`, `TMP`, `PATH`) задаются только внутри процесса/`scripts\*.cmd`; системные переменные и системный Python не используются.

`top_k` по умолчанию — **10**, как в upstream PyLingual: это бюджет альтернативных сегментаций statement-границ при исправлении code object-а. Для ускорения можно явно передать `--top-k 1`, но это может увеличить число модулей, требующих repair-loop.

### MCP-сервер и patch-loop

Запуск stdio (так OpenCode подключает сервер):

```powershell
.\pylingual.cmd mcp --stdio
```

Запуск Streamable HTTP (single-user, local-only):

```powershell
.\pylingual.cmd mcp --transport streamable-http --port 7331
# endpoint: http://127.0.0.1:7331/mcp
```

Готовый portable-конфиг OpenCode: [.opencode/opencode.jsonc](.opencode/opencode.jsonc); общий пример — [docs/opencode-mcp.jsonc](docs/opencode-mcp.jsonc). Подключение через CLI:

```powershell
opencode mcp add pylingual -- cmd.exe /c "D:\RnD\pylingual-portable\pylingual.cmd" mcp --stdio
opencode mcp list
```

Инструменты MCP:

- `decompile` — создать сессию и декомпилировать `.pyc`;
- `get_session`, `get_report`, `get_source`, `list_code_objects`, `get_code_object`;
- `get_report` поддерживает `detail: "summary" | "compact" | "full"` для экономии контекста;
- `verify_source` — dry-run exact verification;
- `apply_patch` — полноценный патч с компиляцией target-компилятором и сравнением bytecode; возвращает `fixed`/`regressed`/`remaining`/`progress`;
- `finalize` — записать `.py` рядом с исходным `.pyc` только при `status: "perfect"`; существующие исходники не перезаписываются, результат получает суффикс `_decompiled_{i}`;
- `revert`, `export`, `get_capabilities`, `doctor`, `cancel`.

Проверено:

- in-memory MCP client: 14 tools, decompile 3.12 → `perfect`;
- bad patch (`return a + b` → `return a - b`) → `semantic_error`, 1/2 code objects;
- good patch → `perfect`, revert → `perfect`;
- stdio через `pylingual.cmd mcp --stdio` — работает;
- Streamable HTTP через лаунчер на `127.0.0.1:7332` — работает.

HTTP в этой сборке не имеет многопользовательской авторизации и слушает только `127.0.0.1`.

### OpenCode harness

Готовый harness лежит в `.opencode/`:

- `.opencode/opencode.jsonc` — MCP-сервер `pylingual` (`codemode: false`, tool timeout 30 мин);
- `.opencode/agents/pylingual.md` — primary-оркестратор: принимает один/несколько `.pyc` или директорию, запускает **ровно одного** `pylingual-worker` за раз и ждёт завершения;
- `.opencode/agents/pylingual-worker.md` — subagent, который отвечает за **один** `.pyc`, одну сессию и цикл до `perfect`;
- `.opencode/commands/pylingual-*.md` — команды `/pylingual-run`, `/pylingual-decompile`, `/pylingual-repair`, `/pylingual-status`, `/pylingual-export`, `/pylingual-finalize`, `/pylingual-doctor`;
- `.opencode/skills/pylingual-repair/` — skill с triage, patch-loop, контекстной дисциплиной, repair patterns и target-version constraints.

Worker работает только через MCP tools: `pylingual_decompile`, `pylingual_get_report`, `pylingual_get_code_object`, `pylingual_apply_patch`, `pylingual_finalize` и т.д. Shell, edit, webfetch/websearch и вложенные subagents у worker-а запрещены; патчи принимаются только после exact verifier. После `perfect` worker вызывает `pylingual_finalize`; существующие `.py` не перезаписываются, результат получает суффикс `_decompiled_{i}`. **PyLingual — единственный разрешённый декомпилятор:** запрещено устанавливать, скачивать, запускать, сравнивать или даже проверять доступность `uncompyle6`, `decompyle3`, `pycdc`, `pycdas` и любых других bytecode-to-source инструментов. Это зафиксировано в агентах, skill, runner prompt; `check_opencode_harness.py` дополнительно падает, если такой пакет установлен или исполняемый файл найден в `PATH`. `opencode_harness.py` выполняет эту проверку автоматически перед запуском (`--no-policy-check` — только для разработки).

Evaluation harness:

```powershell
# собрать .pyc-фикстуры (3.12)
.\scripts\python.cmd .\scripts\build_harness_fixtures.py --version 3.12 --force

# проверить конфигурацию/задачи без OpenCode
.\scripts\python.cmd .\scripts\check_opencode_harness.py
.\scripts\python.cmd .\scripts\test_opencode_config_mcp.py
.\scripts\python.cmd .\scripts\opencode_harness.py --dry-run

# plumbing-тест без модели
.\scripts\python.cmd .\scripts\opencode_harness.py `
  --opencode .\harness\fake_opencode.cmd --only arithmetic --require-all

# реальный прогон OpenCode-агента
.\scripts\python.cmd .\scripts\opencode_harness.py `
  --model anthropic/claude-sonnet-5-5 `
  --agent pylingual `
  --repeat 1 `
  --require-all
```

Runner запускает `opencode run --standalone --agent pylingual --format json --auto`, независимо читает финальную сессию из `workspace/sessions/` и считает успехом только `status: perfect`. Результаты: `harness/results/<timestamp>/summary.md`, `summary.json` и каталоги задач с `final.py`, `report.json`, `session.json`, raw NDJSON.

В текущей среде `opencode` CLI отсутствует, поэтому реальный E2E с моделью не запускался. Проверены JSONC schema, точная команда из `.opencode/opencode.jsonc` через stdio, MCP tool catalog, fake-runner и scoring; для реального прогона нужен установленный OpenCode и выбранная модель.

Фикстуры и инструкции: [harness/README.md](harness/README.md). Есть `tasks.json` (3.12) и `tasks-multi-version.json` (3.6, 3.10, 3.12). Результат fake-прогона (без модели) — только проверка plumbing, не baseline.

### Загрузка моделей с прогрессом

Для одной версии:

```powershell
.\scripts\python.cmd .\scripts\download_model_version.py --version 3.6 --force
```

Скрипт печатает прогресс по каждому файлу (`segmenter/model.safetensors`, `statement/model.safetensors` и т.д.), пишет состояние в `downloads\progress\<version>.json` и итог в `models\download-status\<version>.json`.

Общий монитор прогресса:

```powershell
.\scripts\python.cmd .\scripts\show_download_progress.py --watch --interval 5
```

Он показывает таблицу по всем 10 версиям: текущая модель/файл, проценты, скорость, ETA. В OpenCode прогресс также виден в сессиях суб-агентов, которые запускают эти команды.

Для повторной загрузки всех моделей, включая 3.6:

```powershell
.\scripts\python.cmd .\scripts\download_model_version.py --version 3.6 --force
# или все версии последовательно:
.\scripts\python.cmd .\scripts\fetch_models.py --versions all --force
```

Проверка обновлений на Hugging Face (сравнение установленных commit SHA с текущим `main`):

```powershell
.\scripts\python.cmd .\scripts\check_model_updates.py
```

Результат сохраняется в `models\update-check.json`. Код возврата: `0` — обновлений нет, `2` — есть обновления, `1` — ошибка проверки.

### Известное ограничение

`transformers 5.19.0` в связке Python 3.15 + torch 2.14.1 падает с access violation внутри `from_pretrained` при загрузке этих моделей. Локальный загрузчик `src/pylingual_portable/models.py` обходит это: строит модель из `config.json`, загружает `model.safetensors` и вызывает `eval()`. Это также даёт детерминированный вывод (без dropout).

## Документы

- [Анализ предметной области и план R&D, v1.3](docs/pylingual-portable-rd-plan.md) — подробный план: архитектура, требования, MCP/OpenCode, patch-loop, update manager, roadmap, риски и лицензии.
- [Ссылки на все модели](docs/model-download-links.md) — 3.6–3.15, все репозитории, commit SHA и прямые ссылки на файлы.

## Кратко о предлагаемом продукте

- Полностью локальная сборка без установки, системного Python и сетевых зависимостей в runtime.
- Поддерживаемые платформы: **Windows x64 и Linux x64**; macOS/ARM вне scope.
- Декомпиляция `.pyc` Python 3.6–3.15 (все версии upstream) с точной проверкой (recompile + bytecode/CFG comparison).
- CPU и GPU ровно как в upstream: torch 2.14.1 + CUDA 13.0 (cu130), CPU/OOM fallback; без DirectML/CoreML/ROCm.
- Runtime Python 3.15.x; target-версии 3.6–3.15 — отдельные toolchain-ы.
- MCP-сервер (stdio/Streamable HTTP, single-user) с инструментами `decompile`, `get_report`, `get_code_object`, `apply_patch`, `revert`, `export`, `finalize`; готовые конфиги для OpenCode V2.
- Агент исправляет диагностированные ошибки и отправляет патч; сервер проверяет его тем же exact verifier-ом, что и веб-версия PyLingual.
- Обновление кода с GitHub и моделей с Hugging Face — **только вручную**: staging, smoke-тесты, атомарное переключение, rollback.
- Relocatable root: перенос сборки между каталогами/машинами/USB без перенастройки путей.

## Следующие шаги

1. Зафиксировать baseline по качеству/скорости на всех версиях 3.6–3.15, используя `opencode_harness.py` (реальный агент, несколько повторов).
2. Реализовать ручной update manager для GitHub/Hugging Face с rollback.
3. Подготовить Linux x64 (переносимость Windows-сборки уже проверена копированием в другой каталог и запуском из другого `cwd`).
4. Добавить HTTP-токен/ограничения для Streamable HTTP (сейчас local-only).

## Статус решений

- Проект личный, некоммерческий; сборка не передаётся третьим лицам; GPL-3.0 приемлема.
- Платформы: Windows x64 и Linux x64; Linux baseline — Ubuntu 22.04 (24.04 tested).
- MVP поддерживает все версии Python 3.6–3.15; размер поставки не ограничен.
- Runtime Python 3.15.x; пакеты и CUDA/torch — по upstream lock.
- GPU — ровно как upstream (torch 2.14.1 + CUDA 13.0/cu130, CPU/OOM fallback); Windows CUDA wheel подтверждён.
- MCP: stdio + Streamable HTTP, single-user; встроенный LLM не нужен.
- Обновления кода/моделей обязательны, только с ручным запуском.
- Переносимость между несколькими местами обязательна; переносятся только сборка и модели, sessions/workspace — локальные.
- Патч по умолчанию — полный исходник; diff/code-object — дополнительные режимы.

## Лицензия

Проект использует GPL-3.0-only ядро PyLingual. Для личного использования обязательства по распространению не возникают; сборка не передаётся третьим лицам. См. раздел «Лицензии и комплаенс» в плане.
