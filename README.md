# PyLingual Portable

Переносимая сборка [PyLingual](https://github.com/syssec-utd/pylingual) для
Windows x64. Декомпилирует `.pyc` Python 3.6–3.15 и принимает результат только
после точного сравнения байткода с исходным файлом.

Проект не является форком PyLingual. Исходный код upstream подключён как
git submodule и не изменяется; переносимая обвязка находится в
`src/pylingual_portable`.

## Возможности

- Декомпиляция `.pyc` для Python 3.6–3.15.
- Точная проверка: исходник компилируется целевым интерпретатором, затем
  сравниваются байткод и управляющий граф.
- Локальный Python 3.15.1; системный Python не требуется.
- Отдельные toolchain-ы для каждой целевой версии Python.
- CPU и NVIDIA GPU; при отсутствии GPU используется CPU.
- CLI, MCP-сервер (stdio и Streamable HTTP) и интеграция с OpenCode.
- Работа без сети после установки runtime, toolchain-ов и моделей.
- Перенос каталога без изменения абсолютных путей.

## Платформы

Текущая сборка и скрипты установки рассчитаны на **Windows 10/11 x64**.
Linux-установщик пока не входит в репозиторий; macOS и ARM не поддерживаются.

## Требования

| Компонент | Требование |
|---|---|
| ОС | Windows 10/11 x64 (для `tar.exe` нужен Windows 10 1803 или новее) |
| PowerShell | Windows PowerShell 5.1 или PowerShell 7 |
| Git | 2.30 или новее, с поддержкой submodules |
| Свободное место | не менее 25 ГБ на время установки |
| Сеть | нужна для клонирования, загрузки runtime, toolchain-ов и моделей |
| GPU | опционально: NVIDIA с CUDA 13.0; без GPU работает CPU |
| Python | системный Python не нужен |

Runtime, toolchain-ы и модели занимают около 17 ГБ; остальное место нужно для
архивов, кэша и временных файлов.

## Установка

Подробная инструкция с объяснениями, проверками и устранением неполадок:
[`docs/installation.md`](docs/installation.md).

Краткая установка в пустой каталог:

```powershell
New-Item -ItemType Directory -Force D:\pylingual | Out-Null
Set-Location D:\pylingual

$installer = Join-Path $env:TEMP 'pylingual-install.ps1'
Invoke-WebRequest `
  -Uri 'https://raw.githubusercontent.com/kser93/pylingual-portable/main/install.ps1' `
  -OutFile $installer

powershell -NoProfile -ExecutionPolicy Bypass `
  -File $installer -InstallDir (Get-Location).Path
```

Скрипт клонирует репозиторий с submodules, устанавливает Python 3.15.1,
зависимости, toolchain-ы 3.6–3.15, скачивает модели с Hugging Face, проверяет
MCP-сервер и печатает готовый project-local конфиг OpenCode.

Если репозиторий уже склонирован:

```powershell
Set-Location .\pylingual-portable
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

Проверка уже установленной сборки без скачивания:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -CheckOnly
```

Не используйте GitHub «Download ZIP»: архив не содержит содержимое
submodules.

## Быстрый старт

```powershell
.\pylingual.cmd doctor

.\pylingual.cmd decompile `
  .\harness\fixtures\pyc\3.12\arithmetic.pyc `
  -o .\workspace\tmp\arithmetic.py `
  --version 3.12
```

Для декомпиляции на CPU:

```powershell
.\pylingual.cmd decompile `
  .\harness\fixtures\pyc\3.12\arithmetic.pyc `
  -o .\workspace\tmp\arithmetic-cpu.py `
  --version 3.12 --device cpu
```

Успешная проверка печатает `success rate: 100.00%` и строки `Success: Equal`
для всех code object-ов. Параметр `--top-k` задаёт число альтернативных
сегментаций при исправлении; значение по умолчанию — `10`, как в upstream
PyLingual.

## MCP

Запуск stdio-сервера:

```powershell
.\pylingual.cmd mcp --stdio
```

Запуск Streamable HTTP:

```powershell
.\pylingual.cmd mcp --transport streamable-http --port 7331
# endpoint: http://127.0.0.1:7331/mcp
```

MCP-инструменты: `decompile`, `get_session`, `get_report`, `get_source`,
`list_code_objects`, `get_code_object`, `verify_source`, `apply_patch`,
`revert`, `export`, `finalize`, `get_capabilities`, `doctor`, `cancel`,
`get_agent_manifest`, `get_agent_spec`, `get_skill`.
Инструмент `finalize` записывает `.py` только при `status: "perfect"` и не
перезаписывает существующие файлы.

Сервер также отдаёт спецификацию агентов и skill-ов. Клиенты, поддерживающие
MCP resources, читают `pylingual://manifest`, `pylingual://agents/orchestrator`,
`pylingual://agents/worker` и `pylingual://skills/pylingual-repair`.
Универсальный fallback для остальных клиентов — инструменты
`get_agent_manifest`, `get_agent_spec` и `get_skill`.

Подробное описание CLI и MCP: [`docs/usage.md`](docs/usage.md).

HTTP-сервер не имеет многопользовательской авторизации. По умолчанию он
слушает `127.0.0.1`; не открывайте его во внешнюю сеть.

## OpenCode

Готовая конфигурация находится в `.opencode/`:

- `.opencode/opencode.jsonc` — MCP-сервер `pylingual` (project-local);
- `.opencode/agents/pylingual.md` — оркестратор;
- `.opencode/agents/pylingual-worker.md` — worker для одного `.pyc`;
- `.opencode/commands/pylingual-*.md` — команды `/pylingual-*`;
- `.opencode/skills/pylingual-repair/` — правила repair-loop.

MCP-подключение должно быть проектным: не добавляйте `pylingual` в глобальный
конфиг `~/.config/opencode/opencode.json`. Точный конфиг и проверка описаны в
[инструкции по установке](docs/installation.md#opencode-mcp-на-уровне-проекта).

Worker работает только через MCP. Оркестратор запускает ровно одного worker-а
на один `.pyc` и не принимает частичный результат: успехом считается только
`status: "perfect"` от exact verifier-а.

Подключение MCP к OpenCode описано в
[`docs/usage.md`](docs/usage.md#opencode). Для проверки конфигурации без модели:

```powershell
.\scripts\python.cmd .\scripts\check_opencode_harness.py
.\scripts\python.cmd .\scripts\opencode_harness.py --dry-run
```

## Структура репозитория

```text
src/pylingual_portable/   обвязка: CLI, MCP, сессии, toolchain, модели
vendor/                   git submodules PyLingual и xdis
scripts/                  установка, загрузка моделей, проверки
harness/                  фикстуры и evaluation harness
docs/                     документация
toolchains/               целевые CPython (создаётся при установке)
models/                   локальный HF-кэш и манифесты (создаётся при установке)
runtime/                  Python 3.15.1 (создаётся при установке)
workspace/                временные файлы и сессии (локально, не коммитится)
pylingual.cmd             лаунчер CLI
```

Каталоги `runtime/`, `toolchains/`, `models/` и `workspace/` исключены из Git.
Содержимое `vendor/` приходит из submodules и не редактируется вручную.

## Проверка целостности

```powershell
.\scripts\python.cmd .\scripts\check_vendor.py
.\scripts\python.cmd -m unittest tests.test_vendor_manifest
.\scripts\python.cmd -m unittest tests.test_timestamp_patch
.\scripts\python.cmd -m unittest tests.test_mcp_agent_specs
.\scripts\python.cmd -m unittest tests.test_upstream_contract
```

`check_vendor.py` проверяет `.gitmodules`, HEAD submodule-ов, gitlink (если
доступен Git), хэши файлов и лицензии. Проверки не используют сеть.

## Безопасность

- Скачанный `.pyc` и декомпилированный исходник считаются недоверенными
  данными. Не запускайте их.
- Декомпилятор не выполняет входной `.pyc`. Exact verifier компилирует
  сгенерированный исходник целевым интерпретатором и сравнивает байткод.
- MCP Streamable HTTP предназначен для одиночного локального пользователя.
- Модели и runtime не входят в репозиторий; не публикуйте локальный кэш
  моделей и не включайте его в коммиты.

## Документация

- [Установка](docs/installation.md)
- [Использование: CLI и MCP](docs/usage.md)
- [Ссылки на модели](docs/model-download-links.md)
- [Upstream-компоненты и обновление submodules](vendor/UPSTREAM.md)
- [OpenCode harness](harness/README.md)
- [R&D-план](docs/pylingual-portable-rd-plan.md) — исторический документ,
  не инструкция по установке.

## Лицензия

Проект распространяется по GPL-3.0. PyLingual распространяется по
GPL-3.0-only, xdis — по GPL-2.0-or-later. Тексты лицензий и сведения об
upstream-компонентах находятся в [`LICENSE`](LICENSE),
[`NOTICE`](NOTICE) и [`vendor/UPSTREAM.md`](vendor/UPSTREAM.md).

Веса моделей не входят в репозиторий и не распространяются вместе с проектом.
Они загружаются пользователем из Hugging Face; условия использования
определяются карточками моделей. Перед распространением сборки или результатов
декомпиляции проверьте лицензии моделей.
