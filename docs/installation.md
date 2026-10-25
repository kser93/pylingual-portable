# Установка PyLingual Portable

В этом документе описана установка PyLingual Portable из исходного
репозитория на Windows x64. После выполнения шагов все компоненты находятся
внутри каталога проекта; системный Python и переменные среды Windows не
изменяются.

При ручной установке выполняются следующие этапы:

1. клонирование репозитория вместе с submodules;
2. установка Python 3.15.1 и зависимостей runtime;
3. загрузка целевых интерпретаторов Python 3.6–3.15;
4. загрузка моделей;
5. проверка запуска.

Полный набор занимает около 17 ГБ. Во время установки требуется около 25 ГБ
свободного места для архивов и временных файлов.

## Поддерживаемые платформы

Поддерживается Windows 10/11 x64. Для распаковки архивов нужен `tar.exe`,
который входит в Windows 10 версии 1803 и новее.

Linux-установщик в репозитории отсутствует. macOS и ARM не поддерживаются.
Если требуется Linux, используйте [R&D-план](pylingual-portable-rd-plan.md)
как описание направления работ, а не как готовую инструкцию.

## Требования

| Компонент | Требование |
|---|---|
| ОС | Windows 10/11 x64 |
| PowerShell | Windows PowerShell 5.1 или PowerShell 7 |
| Git | 2.30 или новее |
| Свободное место | не менее 25 ГБ |
| Сеть | нужна на время установки |
| GPU | опционально; NVIDIA с CUDA 13.0 |
| Python | системный Python не требуется |

Проверьте версии перед началом:

```powershell
$PSVersionTable.PSVersion
git --version
tar --version
```

Если `git` не найден, установите Git for Windows и откройте новый терминал.
Если `tar` не найден, обновите Windows или используйте Windows 10 1803+.

## Быстрая установка

Основной способ установки — `install.ps1`. Он скачивает с GitHub исходный
репозиторий (если запущен в пустом каталоге), Python runtime, toolchain-ы и
модели с Hugging Face, проверяет MCP-сервер и печатает готовый конфиг
OpenCode.

### Чистая машина

Создайте пустой каталог и запустите установщик из временного файла:

```powershell
New-Item -ItemType Directory -Force D:\pylingual | Out-Null
Set-Location D:\pylingual

$installer = Join-Path $env:TEMP 'pylingual-install.ps1'
Invoke-WebRequest `
  -Uri 'https://github.com/kser93/pylingual-portable/releases/latest/download/install.ps1' `
  -OutFile $installer

powershell -NoProfile -ExecutionPolicy Bypass `
  -File $installer -InstallDir (Get-Location).Path
```

Не скачивайте `install.ps1` прямо в целевой каталог: скрипт должен видеть
пустой каталог, чтобы клонировать в него репозиторий.

### Уже склонированный репозиторий

```powershell
Set-Location D:\pylingual-portable
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

### Проверка и служебные режимы

```powershell
# проверить существующую установку без скачивания
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -CheckOnly

# показать план без изменений
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -DryRun

# склонировать только исходники, без runtime и моделей
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -SourceOnly
```

Параметры:

| Параметр | Назначение |
|---|---|
| `-InstallDir <path>` | целевой каталог; по умолчанию текущий |
| `-RepoUrl <url>` | Git URL источника; по умолчанию GitHub-репозиторий проекта |
| `-GitPath <path>` | явный путь к `git.exe`, если Git не в `PATH` |
| `-SkipModels` | не скачивать модели |
| `-SkipToolchains` | не устанавливать toolchain-ы |
| `-SkipMcpProbe` | не запускать проверку MCP |
| `-CheckOnly` | только проверить установку |
| `-DryRun` | показать план без изменений |
| `-SourceOnly` | только клонировать исходники и submodules |

Установщик печатает project-local конфиг OpenCode, но не перезаписывает
существующий `.opencode\opencode.jsonc`. Скопируйте или объедините секцию
`mcp.servers.pylingual` вручную. Подробности — в разделе
[«OpenCode: MCP на уровне проекта»](#opencode-mcp-на-уровне-проекта).

MCP stdio-сервер не оставляется работать в фоне: им управляет агентская
программа. Установщик запускает его на время probe, проверяет tools/resources/
prompts и завершает процесс. Для постоянного HTTP-сервера используйте
`pylingual.cmd mcp --transport streamable-http`.

## Ручная установка

Шаги ниже нужны, если установщик недоступен или требуется разобрать установку
по частям.

### Шаг 1. Клонирование репозитория

Исходный код PyLingual и xdis подключён как git submodules. Клонируйте
репозиторий с флагом `--recurse-submodules`:

```powershell
git clone --recurse-submodules https://github.com/kser93/pylingual-portable.git
Set-Location .\pylingual-portable
```

Проверьте, что submodules инициализированы:

```powershell
git submodule status --recursive
```

В выводе должны быть две строки с коммитами:

```text
 11a1516d84a6c2aa71ec23fbd11e4b99dc8c4a86 vendor/pylingual (v0.1.0)
 51e36c42a01a83d67f6530fdf7fbd42a0f387d86 vendor/xdis-src (6.3.0-44-g51e36c42)
```

Если репозиторий уже был склонирован без submodules, выполните:

```powershell
git submodule update --init --recursive
```

> **Примечание.** Архив GitHub «Download ZIP» не содержит содержимое
> submodules. Для установки нужен именно `git clone`.

### Шаг 2. Python runtime 3.15.1

Проект использует отдельный Python 3.15.1 из
[python-build-standalone](https://github.com/astral-sh/python-build-standalone).
Скачайте архив и распакуйте его в `runtime\python-3.15.1`:

```powershell
New-Item -ItemType Directory -Force .\downloads, .\runtime | Out-Null

$release = '20261021'
$url = "https://github.com/astral-sh/python-build-standalone/releases/download/$release/cpython-3.15.1%2B$release-x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
$archive = '.\downloads\cpython-3.15.1+20261021-win-x64-install_only_stripped.tar.gz'

Invoke-WebRequest -Uri $url -OutFile $archive
tar -xzf $archive -C .\runtime

if (Test-Path .\runtime\python) {
    Move-Item .\runtime\python .\runtime\python-3.15.1
}

Test-Path .\runtime\python-3.15.1\python.exe
```

Последняя команда должна вывести `True`. Не переименовывайте каталог
`runtime\python-3.15.1`: скрипты проекта используют этот путь.

Если `runtime\python-3.15.1` уже существует, шаг можно пропустить. Если
распаковка прервалась и остался каталог `runtime\python`, удалите его и
повторите распаковку.

### Шаг 3. Зависимости runtime

Скрипт `scripts\install_runtime.ps1` устанавливает CUDA-сборку PyTorch,
зависимости из `scripts\requirements-runtime.txt` и xdis из закреплённого
submodule:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_runtime.ps1
```

Скрипт выполняет следующие действия:

- устанавливает `torch==2.14.1+cu130` из индекса PyTorch;
- устанавливает PyYAML без C-расширения, чтобы не требовался MSVC;
- устанавливает `transformers`, `tokenizers`, `numpy`, `mcp` и другие
  закреплённые пакеты;
- устанавливает xdis из `vendor\xdis-src`;
- создаёт минимальные метаданные PyLingual, не устанавливая training-зависимости.

Установка занимает несколько гигабайт и требует сетевого доступа к PyPI и
`download.pytorch.org`.

> **Примечание.** Устанавливается CUDA-сборка PyTorch. На машине без NVIDIA
> GPU она работает в режиме CPU; это проверяется командой `doctor`. Отдельная
> CPU-only сборка не входит в проверенную конфигурацию.

Если PowerShell блокирует выполнение скриптов, параметр
`-ExecutionPolicy Bypass` применён только к текущему процессу. Системная
политика выполнения не изменяется.

### Шаг 4. Целевые интерпретаторы Python

Для проверки байткода нужны компиляторы целевых версий. Скрипт загружает
Python 3.8–3.15 из python-build-standalone и официальные embeddable-сборки
Python 3.6 и 3.7:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\fetch_all_toolchains.ps1
```

Скрипт создаёт каталоги `toolchains\cpython-*` и печатает установленные
версии. Повторный запуск пропускает уже установленные интерпретаторы.

Проверить результат можно так:

```powershell
Get-ChildItem .\toolchains -Directory | Select-Object Name
```

В списке должны быть каталоги от `cpython-3.6.8-win-x64` до
`cpython-3.15.1-win-x64`.

### Шаг 5. Модели

Модели не входят в репозиторий. Они скачиваются из Hugging Face и
привязываются к закреплённым commit SHA из `models\model-links.json`.

Для загрузки всех десяти наборов:

```powershell
.\scripts\python.cmd .\scripts\fetch_models.py --versions all
```

Для одной версии:

```powershell
.\scripts\python.cmd .\scripts\download_model_version.py --version 3.12
```

Команда `download_model_version.py` показывает прогресс по каждому файлу и
позволяет продолжить загрузку после обрыва. Для повторной загрузки добавьте
`--force`.

Во время загрузки можно открыть монитор в отдельном терминале:

```powershell
.\scripts\python.cmd .\scripts\show_download_progress.py --watch --interval 5
```

Файлы размещаются в `models\hf-cache\hub`. Скрипты отключают `hf-xet`, потому
что на части репозиториев он зависает; загрузка идёт по HTTP.

Если Hugging Face ограничивает скорость или требует токен, задайте его только
для текущего процесса:

```powershell
$env:HF_TOKEN = 'hf_...'
```

Не записывайте токен в файлы репозитория.

> **Лицензии моделей.** Веса моделей не распространяются вместе с проектом.
> Условия использования определяются карточками моделей на Hugging Face.
> Проверьте их перед распространением сборки или результатов декомпиляции.

После загрузки `models\installed.json` содержит пути к установленным
snapshot-ам. Не удаляйте этот файл вручную.

### Шаг 6. Проверка установки

Запустите диагностику:

```powershell
.\pylingual.cmd doctor
```

В выводе должны быть:

- путь к локальному Python 3.15.1;
- версия torch и строка `torch CUDA build: 13.0`;
- `CUDA available: True` на машине с NVIDIA GPU или `False` при работе на CPU;
- список toolchain-ов;
- путь к HF-кэшу и установленные модели;
- строка `Upstream contract: ok`.

Затем выполните пробную декомпиляцию:

```powershell
.\pylingual.cmd decompile `
  .\harness\fixtures\pyc\3.12\arithmetic.pyc `
  -o .\workspace\tmp\arithmetic.py `
  --version 3.12
```

Успешный результат выглядит так:

```text
success rate: 100.00%
<module>: Success: Equal
saved: ...\workspace\tmp\arithmetic.py
```

На машине без GPU используйте `--device cpu`:

```powershell
.\pylingual.cmd decompile `
  .\harness\fixtures\pyc\3.12\arithmetic.pyc `
  -o .\workspace\tmp\arithmetic-cpu.py `
  --version 3.12 --device cpu
```

`success rate: 100.00%` означает, что сгенерированный исходник компилируется
в байткод, совпадающий с исходным `.pyc`. Это не означает текстового
совпадения с оригинальным исходником: комментарии и форматирование не
восстанавливаются.

## OpenCode: MCP на уровне проекта

OpenCode не обязателен для работы PyLingual. Если он используется, MCP-сервер
подключается **только к текущему проекту**. Не добавляйте `pylingual` в
глобальный конфиг `C:\Users\<user>\.config\opencode\opencode.json`: тогда
сервер будет привязан к одному каталогу и станет доступен всем проектам
машины.

### Куда поместить конфигурацию

Файл проекта:

```text
<корень-проекта>\.opencode\opencode.jsonc
```

Для этой установки:

```text
D:\pylingual-portable\.opencode\opencode.jsonc
```

Если файл уже существует, добавьте в него только секцию `mcp.servers.pylingual`
и не заменяйте остальные настройки проекта.

### Содержимое файла

Замените `D:\\pylingual-portable` на фактический абсолютный путь к каталогу
установки:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "timeout": {
      "startup": 60000,
      "catalog": 60000,
      "execution": 1800000
    },
    "servers": {
      "pylingual": {
        "type": "local",
        "command": [
          "cmd.exe",
          "/c",
          "D:\\pylingual-portable\\pylingual.cmd",
          "mcp",
          "--stdio"
        ],
        "cwd": "D:\\pylingual-portable",
        "codemode": false,
        "protocol": "legacy",
        "timeout": {
          "startup": 60000,
          "catalog": 60000,
          "execution": 1800000
        }
      }
    }
  }
}
```

Поля:

- `type: "local"` — OpenCode запускает сервер как дочерний процесс;
- `command` — `cmd.exe`, потому что `pylingual.cmd` является batch-файлом;
- `cwd` — абсолютный каталог установки; не используйте `.`;
- `codemode: false` — инструменты доступны как `pylingual_<tool>`;
- `protocol: "legacy"` — режим, проверенный с текущей версией OpenCode;
- `timeout` — запуск, каталог инструментов и выполнение.

Если путь содержит пробелы, используйте его в JSON как обычную строку и
проверьте запуск через preflight ниже.

### Проверка

Из корня проекта:

```powershell
Set-Location D:\pylingual-portable
opencode mcp list
```

В списке должен быть `pylingual` со статусом `connected`. Если список пуст,
проверьте, что OpenCode открыт именно в этом каталоге и что файл лежит в
`.opencode\opencode.jsonc`, а не в глобальном конфиге.

После подключения новая сессия должна видеть инструменты с префиксом
`pylingual_`. Проверка через агента:

```text
Вызови pylingual_get_agent_manifest и покажи schema, spec_version и loop.
```

Ожидается `schema: "pylingual/agent-manifest/v1"` и цикл, заканчивающийся
`status == "perfect"` → `finalize`.

Если `opencode models` пуст или модель не авторизована, MCP-подключение всё
равно может быть исправным; настройте провайдера отдельно:

```powershell
opencode models
opencode auth login
```

### Нужны ли файлы агентов

Нет. MCP-сервер сам отдаёт манифест, роли и skill через tools/resources.
Каталоги `.opencode\agents` и `.opencode\skills` нужны только для
OpenCode-нативных агентов и команд `/pylingual-*`. Без них обычный
MCP-совместимый агент всё равно может получить инструкции через
`pylingual_get_agent_manifest`, `pylingual_get_agent_spec` и
`pylingual_get_skill`.

## Работа без сети

После установки runtime, toolchain-ов и моделей сеть не нужна. Лаунчер
`pylingual.cmd` устанавливает `HF_HUB_OFFLINE=1` и `TRANSFORMERS_OFFLINE=1`
только для своего процесса.

Проверка в офлайн-режиме:

```powershell
# Отключите сеть, затем выполните:
.\pylingual.cmd decompile `
  .\harness\fixtures\pyc\3.12\arithmetic.pyc `
  -o .\workspace\tmp\arithmetic-offline.py `
  --version 3.12
```

Все переменные `PYTHONHOME`, `PYTHONPATH`, `HF_HOME`, `TMP` и `PATH`
задаются внутри `scripts\*.cmd`. Системные переменные Windows не изменяются.

## Перенос установки

Каталог можно перенести на другой диск или машину целиком. Скрипты вычисляют
пути относительно `pylingual.cmd`, поэтому абсолютные пути не сохраняются.

Переносите весь каталог, включая `runtime`, `toolchains`, `models` и
`vendor`. Каталог `workspace` содержит локальные сессии и временные файлы; его
можно не переносить.

После переноса проверьте:

```powershell
.\pylingual.cmd doctor
```

На другой машине может отличаться версия драйвера NVIDIA; при отсутствии GPU
проект продолжит работать на CPU.

## Обновление

Обновление исходного кода и submodules выполняется вручную:

```powershell
git pull --ff-only
git submodule update --init --recursive
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_runtime.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\fetch_all_toolchains.ps1
.\scripts\python.cmd .\scripts\fetch_models.py --versions all
.\scripts\python.cmd .\scripts\check_model_updates.py
```

`check_model_updates.py` сравнивает установленные commit SHA с текущими
ревизиями Hugging Face. Код возврата `2` означает, что доступны обновления;
обновление моделей не выполняется автоматически.

Не выполняйте `git submodule update --remote` без проверки: submodules
закреплены на конкретных коммитах, и обновление должно сопровождаться
проверкой `check_vendor.py` и тестами.

## Удаление

Удалите каталог проекта:

```powershell
Remove-Item -Recurse -Force .\pylingual-portable
```

Проект не создаёт служб, задач планировщика и записей в реестре. Если вы
вручную задавали `HF_TOKEN` или меняли политику выполнения PowerShell, эти
изменения нужно отменить отдельно.

## Проверка целостности

После установки и перед обновлением можно проверить submodules и контракт
upstream:

```powershell
.\scripts\python.cmd .\scripts\check_vendor.py
.\scripts\python.cmd -m unittest tests.test_vendor_manifest
.\scripts\python.cmd -m unittest tests.test_timestamp_patch
.\scripts\python.cmd -m unittest tests.test_upstream_contract
```

`check_vendor.py` не использует сеть. При наличии Git он дополнительно
проверяет gitlink суперпроекта; без Git проверяются `.gitmodules`, HEAD
submodule-ов и хэши файлов.

## Типовые ошибки

### `Upstream submodules are not initialized`

Submodules не склонированы или не инициализированы. Выполните:

```powershell
git submodule update --init --recursive
```

### `Portable Python not found`

Не найден `runtime\python-3.15.1\python.exe`. Проверьте путь и повторите
шаг 2. Каталог должен называться именно `python-3.15.1`.

### Ошибка установки torch или transformers

Проверьте сетевое подключение, прокси и свободное место. Повторите шаг 3.
Если установка прервалась, запустите `install_runtime.ps1` ещё раз: pip
проверит уже установленные пакеты.

### `CUDA available: False`

Это не ошибка. Проект работает на CPU, но медленнее. Проверьте драйвер NVIDIA
и версию CUDA, если GPU должен быть доступен. Для принудительного CPU-режима
используйте `--device cpu`.

### Модель не найдена или `doctor` не показывает версию

Повторите загрузку модели:

```powershell
.\scripts\python.cmd .\scripts\download_model_version.py --version 3.12
```

Проверьте, что `models\hf-cache` существует и в `models\installed.json` есть
запись для нужной версии. Убедитесь, что на диске достаточно места.

### Ошибка доступа или слишком длинный путь

HF-кэш содержит длинные пути. Включите поддержку длинных путей Windows или
разместите проект в коротком каталоге, например `D:\pylingual`.

### MCP-сервер не подключается

Проверьте запуск вручную:

```powershell
.\pylingual.cmd mcp --stdio
```

Сервер должен запуститься и ждать JSON-RPC на stdin. Затем проверьте
конфигурацию OpenCode и переподключите MCP. Если сервер ранее завершился с
ошибкой, обновите проект и повторите `doctor`; состояние подключения
сбрасывается перезапуском MCP.

### `pylingual.cmd` завершается с кодом 1 без вывода

Проверьте `runtime\python-3.15.1\python.exe` и выполните:

```powershell
.\scripts\python.cmd -c "import sys; print(sys.version)"
```

Если Python не запускается, повторите шаг 2 и шаг 3.

## Почему установка не через wheel

Пакет `wheel`/`setuptools` здесь не заменяет установщик:

- runtime, 10 toolchain-ов и model packs занимают около 17 ГБ и не являются
  Python-пакетами;
- `pip install` раскладывает файлы в `site-packages`, а проекту нужен
  самодостаточный переносимый каталог;
- модели распространяются отдельно от кода и имеют собственные условия
  использования;
- wheel может быть полезен только для разработки самой обвязки
  `pylingual_portable`, но не для конечной установки.

Поэтому конечная установка выполняется через `install.ps1`, а не через
`pip install`.

## См. также

- [Использование CLI и MCP](usage.md)
- [Ссылки на модели](model-download-links.md)
- [Upstream-компоненты и обновление submodules](../vendor/UPSTREAM.md)
- [R&D-план](pylingual-portable-rd-plan.md)
