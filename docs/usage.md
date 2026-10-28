# Использование PyLingual Portable

В этом документе описаны локальный CLI, MCP-сервер и запуск через OpenCode.
Предполагается, что установка выполнена по
[инструкции](installation.md) и `pylingual.cmd doctor` завершается успешно.

## CLI

Все команды запускаются через `pylingual.cmd` из корня проекта:

```powershell
.\pylingual.cmd <команда> [параметры]
```

Лаунчер сам задаёт `PYTHONHOME`, `PYTHONPATH`, `HF_HOME` и временные каталоги
для своего процесса. Не запускайте `src\pylingual_portable` системным Python.

### `doctor`

Проверяет Python, torch, CUDA, toolchain-ы, HF-кэш и контракт upstream:

```powershell
.\pylingual.cmd doctor
```

Команда возвращает код `0`, если доступны runtime, torch, upstream contract,
все ожидаемые toolchain-ы и model packs. Отсутствие GPU не является ошибкой:
в выводе будет `CUDA available: False`. Для частичной установки используйте
`--skip-models` и/или `--skip-toolchains`.

### `decompile`

Синтаксис:

```text
pylingual decompile <файл.pyc> [-o <файл.py>] [--version <версия>]
                    [--top-k <N>] [--timeout <секунды>]
                    [--device auto|cpu|cuda:0]
```

Параметры:

| Параметр | По умолчанию | Описание |
|---|---:|---|
| `--version` | определяется по `.pyc` | целевая версия Python, например `3.12` |
| `--top-k` | `10` | число альтернативных сегментаций при исправлении |
| `--timeout` | `600` | тайм-аут в секундах |
| `--device` | `auto` | устройство инференса |
| `-o`, `--output` | нет | путь для сохранения исходника |

Если `-o` не указан, исходник печатается в stdout.

Примеры:

```powershell
.\pylingual.cmd decompile .\harness\fixtures\pyc\3.12\arithmetic.pyc `
  -o .\workspace\tmp\arithmetic.py --version 3.12

.\pylingual.cmd decompile .\harness\fixtures\pyc\3.6\arithmetic.pyc `
  -o .\workspace\tmp\arithmetic36.py --version 3.6

.\pylingual.cmd decompile .\harness\fixtures\pyc\3.12\arithmetic.pyc `
  -o .\workspace\tmp\arithmetic-cpu.py --version 3.12 --device cpu
```

`--top-k 1` ускоряет первичную декомпиляцию, но может увеличить число
code object-ов, требующих repair-loop. Значение `10` соответствует upstream
PyLingual.

Успешная проверка печатает `success rate: 100.00%` и `Success: Equal` для
каждого code object-а. Это означает совпадение байткода после повторной
компиляции, а не текстовое совпадение исходников.

### MCP-сервер

Запуск stdio-транспорта:

```powershell
.\pylingual.cmd mcp --stdio
```

Запуск Streamable HTTP:

```powershell
.\pylingual.cmd mcp --transport streamable-http --host 127.0.0.1 --port 7331
```

Endpoint: `http://127.0.0.1:7331/mcp`.

HTTP-сервер не имеет авторизации и предназначен для одного локального
пользователя. Не публикуйте его во внешней сети.

### Хранилище сессий

Каждая декомпиляция создаёт сессию в `workspace\sessions\<session_id>`.
Сессия хранит исходный `.pyc`, ревизии исходника, отчёты exact verifier-а и
диагностику. `workspace\` не коммитится в Git.

## MCP

MCP-сервер предоставляет 19 инструментов. Имена в OpenCode имеют префикс
`pylingual_`; в JSON-RPC и MCP-клиентах используются имена без префикса.

| Инструмент | Назначение |
|---|---|
| `decompile` | создать сессию и декомпилировать `.pyc` |
| `get_session` | метаданные и история ревизий |
| `get_report` | отчёт exact verifier-а |
| `get_source` | полный исходник ревизии |
| `list_code_objects` | список code object-ов и их статусов |
| `get_code_object` | исходный фрагмент и байткод одного code object-а |
| `verify_source` | проверить исходник без создания ревизии |
| `apply_patch` | применить полный исходник и проверить его |
| `revert` | вернуться к предыдущей ревизии |
| `export` | сохранить ревизию в `workspace\exports` |
| `finalize` | повторно проверить и записать `.py` при `perfect` |
| `get_capabilities` | версии, toolchain-ы, устройства и лимиты |
| `doctor` | краткая диагностика runtime |
| `cancel` | зарезервирован; текущая реализация синхронная |
| `get_agent_manifest` | роли агентов, skills, цикл и правила |
| `get_agent_spec` | контракт `orchestrator` или `worker` |
| `get_skill` | спецификация skill-а по имени |
| `get_patching_skill` | правила патчинга для целевой версии |
| `record_patching_rule` | добавить проверенное правило после perfect-сессии |

`get_patching_skill` возвращает dedicated-правила целевой версии, если они есть;
иначе `primary.rules` пуст, а `others` содержит правила других версий как
гипотезы.

### Спецификации агентов и skill-ов

Сервер отдаёт спецификации по трём каналам:

- **resources** для клиентов, которые их поддерживают:
  - `pylingual://manifest`
  - `pylingual://agents/orchestrator`
  - `pylingual://agents/worker`
  - `pylingual://skills/pylingual-repair`
  - `pylingual://skills/pylingual-rules`
  - `pylingual://skills/pylingual-patching-3.11`
- **prompts** для клиентов, которые умеют получать prompt-шаблоны:
  - `pylingual_worker_task(path, version)`
  - `pylingual_orchestrator_task(paths)`
  - `pylingual_repair_loop()`
- **tools** как универсальный fallback:
  - `get_agent_manifest()`
  - `get_agent_spec(role="worker"|"orchestrator")`
  - `get_skill(name=...)`
  - `get_patching_skill(version=...)`

Инструменты возвращают `content` (Markdown), `sha256` и `spec_version`.
Манифест содержит цикл `decompile -> get_report -> apply_patch -> repeat until
status == "perfect" -> finalize` и жёсткие правила: только PyLingual, без
исполнения `.pyc`, полный исходник вместо diff, `finalize` только при
`status: "perfect"`.

### `decompile`

```json
{
  "path": "C:\\work\\sample.pyc",
  "version": "3.12",
  "top_k": 10,
  "timeout": 900,
  "device": "auto"
}
```

`version` можно не указывать: сервер определит версию по `.pyc`. Путь может
быть абсолютным или относительным корня проекта.

Ответ содержит `session_id`, `status`, `summary`, `diagnostics` и
`next_actions`.

### `get_report`

```json
{"session_id": "ses_...", "detail": "compact"}
```

Значения `detail`:

- `summary` — только итоговая статистика;
- `compact` — итог и только падающие code object-ы;
- `full` — полный список code object-ов.

Для repair-loop используйте `compact`; `full` нужен только для диагностики.

### `apply_patch`

```json
{
  "session_id": "ses_...",
  "base_revision": 0,
  "source": "полный исходник Python",
  "description": "исправлена ветка условия"
}
```

Патч передаётся целиком, а не в виде diff. Сервер компилирует исходник целевым
toolchain-ом и сравнивает байткод с исходным `.pyc`. Ответ содержит `status`,
`revision`, `fixed`, `regressed`, `remaining` и `progress`.

`status: "perfect"` означает, что все code object-ы совпали. Только в этом
случае имеет смысл вызывать `finalize`.

### `finalize`

```json
{"session_id": "ses_..."}
```

Инструмент повторно запускает strict-verifier для текущего исходника, сверяет
`source_sha256` с report и только затем записывает `.py` рядом с исходным
`.pyc`. Если файл с таким именем уже существует, используется
`_decompiled_1.py`, `_decompiled_2.py` и так далее. Не-perfect сессия и сессия
с устаревшим report не финализируются.

### `verify_source`

Dry-run без создания ревизии. Используйте, когда нужно проверить кандидат
перед `apply_patch`. Для обычного repair-loop предпочтителен `apply_patch`:
он создаёт ревизию и сразу возвращает диагностику.

## OpenCode

Готовые агенты и MCP-конфигурация находятся в `.opencode/`:

- `opencode.jsonc` — локальный MCP-сервер `pylingual`;
- `agents/pylingual.md` — оркестратор;
- `agents/pylingual-worker.md` — worker для одного `.pyc`;
- `commands/pylingual-*.md` — команды `/pylingual-*`;
- `skills/pylingual-repair/` — правила repair-loop.

MCP-конфигурация должна быть project-local. Конкретный файл, абсолютные пути и
проверка описаны в [инструкции по установке](installation.md#opencode-mcp-на-уровне-проекта).

Оркестратор запускает ровно одного worker-а на один `.pyc` и ждёт завершения.
Worker не имеет доступа к shell, edit и web; он работает только с MCP и
принимает изменения только после exact verifier-а.

### Подключение MCP

OpenCode загружает `.opencode\opencode.jsonc` при открытии проекта. CLI не
требуется. Пример конфигурации для другой установки находится в
[`docs/opencode-mcp.jsonc`](opencode-mcp.jsonc).

### Команды

```text
/pylingual-run <файл.pyc | каталог>...
/pylingual-decompile <файл.pyc>
/pylingual-repair <файл.pyc | ses_...>
/pylingual-status
/pylingual-finalize
/pylingual-export
/pylingual-doctor
```

`/pylingual-run` обрабатывает файлы последовательно. Если worker сообщает
техническую ошибку, оркестратор запускает нового worker-а на том же файле, а
не пропускает его.

> **Известное ограничение 0.3.0:** command layer для `status`, `finalize` и
> `repair` ещё уточняется; для существующих сессий он может проходить через
> worker, контракт которого начинается с `decompile`. Авторитетный интерфейс —
> MCP tools `get_report`, `finalize`, `apply_patch`.

### Проверка MCP

CLI `opencode` не нужен. Проверьте сервер напрямую:

```powershell
.\scripts\python.cmd .\scripts\probe_mcp.py
.\scripts\python.cmd .\scripts\test_mcp_stdio.py
.\scripts\python.cmd .\scripts\test_mcp_inmemory.py
```

## Точная проверка

Exact verifier выполняет следующие шаги:

1. компилирует сгенерированный исходник целевым интерпретатором;
2. сравнивает байткод, управляющий граф, code-object metadata и типы констант
   с исходным `.pyc`;
3. присваивает каждому code object-у статус `perfect` или диагностику.

Успехом считается только `status: "perfect"`. Читаемый, но семантически
отличающийся исходник не принимается. Для hash-based `.pyc` без timestamp
используется заголовок `unknown (hash-based pyc)`; это не влияет на байткод.

## Переменные среды

Лаунчеры задают переменные только для своего процесса:

- `PYTHONHOME`, `PYTHONPATH` — локальный runtime;
- `HF_HOME`, `HF_HUB_CACHE` — локальный кэш моделей;
- `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE` — офлайн-режим;
- `TMP`, `TEMP` — `workspace\tmp`;
- `PATH` — runtime и библиотеки torch.

Не добавляйте эти пути в системные переменные Windows: это может сломать
другой Python и другие приложения.

## См. также

- [Установка](installation.md)
- [Ссылки на модели](model-download-links.md)
- [Фикстуры для smoke-проверок](../harness/README.md)
- [R&D-план](pylingual-portable-rd-plan.md)
