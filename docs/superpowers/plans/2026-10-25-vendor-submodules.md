# Vendor Dependencies as Git Submodules — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two vendored upstream source snapshots with pinned git submodules without losing offline integrity checks or the existing runtime contract.

**Architecture:** Keep `vendor/components.json` as the machine-readable pin manifest, add `.gitmodules` gitlinks for PyLingual and xdis, and extend `scripts/check_vendor.py` to validate submodule registration and HEAD in addition to its existing content hash. Documentation and the launcher explain recursive initialization.

**Tech Stack:** Git submodules, Python 3.15 portable runtime, `unittest`, Windows batch launchers.

**Spec:** `docs/superpowers/specs/2026-10-25-vendor-submodules-design.md`

## Global Constraints

- Git is not on `PATH`; use `C:\Program Files\Git\cmd\git.exe`.
- Pins: PyLingual `11a1516d84a6c2aa71ec23fbd11e4b99dc8c4a86` (`v0.1.0`), xdis `51e36c42a01a83d67f6530fdf7fbd42a0f387d86`.
- Upstream URLs: `https://github.com/syssec-utd/pylingual`, `https://github.com/rocky/python-xdis`.
- Do not edit upstream source inside `vendor/`.
- Use `.\scripts\python.cmd`; do not use system Python.
- No process-global environment variables.

## Review Focus

- Cloning without initialized submodules must produce an actionable message, not a bare `ModuleNotFoundError`.
- A GitHub ZIP download must be documented as insufficient because it omits submodule contents.
- A `.gitmodules` URL that differs from the manifest must fail the checker.
- A dirty or patched submodule must fail the content hash check.
- The checker must remain usable when the `git` executable is absent.

---

### Task 1: Convert vendor trees to submodules and extend the checker

**Files:**
- Create: `tests/test_vendor_manifest.py`
- Modify: `scripts/check_vendor.py`
- Modify: `vendor/components.json`
- Modify: `.gitattributes`
- Create: `.gitmodules` (via `git submodule add`)
- Replace: `vendor/pylingual`, `vendor/xdis-src` (tracked trees become gitlinks)

**Interfaces:**
- Produces: `check_vendor._submodule_head(root: Path) -> str | None`
- Produces: `check_vendor._submodule_urls(path: Path) -> dict[str, str]`
- Produces: `check_vendor.check_components(*, update: bool = False) -> dict[str, Any]` (existing signature, stricter result)
- Manifest gains `"kind": "git-submodule"` on both components.

- [ ] **Step 1: Write the failing tests**

Add `tests/test_vendor_manifest.py` with:

```python
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_vendor import (  # noqa: E402
    _is_excluded,
    _submodule_head,
    _submodule_urls,
    check_components,
)


class SubmoduleHelpersTest(unittest.TestCase):
    def test_git_file_is_excluded_from_tree_hash(self) -> None:
        self.assertTrue(_is_excluded(Path(".git"), {}))
        self.assertTrue(_is_excluded(Path("pkg/.git"), {}))

    def test_gitmodules_urls_are_read_by_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".gitmodules"
            path.write_text(
                '[submodule "vendor/pylingual"]\n'
                "\tpath = vendor/pylingual\n"
                "\turl = https://github.com/syssec-utd/pylingual\n",
                encoding="utf-8",
            )
            self.assertEqual(
                _submodule_urls(path),
                {"vendor/pylingual": "https://github.com/syssec-utd/pylingual"},
            )

    def test_submodule_head_reads_detached_and_ref_heads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vendor" / "pylingual"
            gitdir = Path(tmp) / ".git" / "modules" / "vendor" / "pylingual"
            root.mkdir(parents=True)
            gitdir.mkdir(parents=True)
            (root / ".git").write_text(
                "gitdir: ../../.git/modules/vendor/pylingual\n", encoding="utf-8"
            )
            commit = "11a1516d84a6c2aa71ec23fbd11e4b99dc8c4a86"
            (gitdir / "HEAD").write_text(commit + "\n", encoding="utf-8")
            self.assertEqual(_submodule_head(root), commit)
            (gitdir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            (gitdir / "refs" / "heads").mkdir(parents=True)
            (gitdir / "refs" / "heads" / "main").write_text(commit + "\n", encoding="utf-8")
            self.assertEqual(_submodule_head(root), commit)


class ComponentsManifestTest(unittest.TestCase):
    def test_components_pass_submodule_and_tree_checks(self) -> None:
        result = check_components()
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(
            {name: spec.get("kind") for name, spec in
             __import__("json").loads((ROOT / "vendor" / "components.json").read_text(encoding="utf-8"))["components"].items()},
            {"pylingual": "git-submodule", "xdis": "git-submodule"},
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.\scripts\python.cmd -m unittest tests.test_vendor_manifest -v`

Expected: FAIL because `_is_excluded`, `_submodule_head`, and `_submodule_urls` do not exist (or the manifest lacks `kind`).

- [ ] **Step 3: Implement the checker helpers**

In `scripts/check_vendor.py`:

- Add `import re` and `import shlex` only if needed; keep the parser simple.
- In `_is_excluded`, return `True` when `relative.name == ".git"` (covers the submodule `.git` file).
- Add `_normalize_url(url: str) -> str`: strip whitespace, trailing `/`, and a single trailing `.git`.
- Add `_submodule_urls(path: Path) -> dict[str, str]` parsing `.gitmodules` INI sections; key by the `path` value, value is the `url` value. Return `{}` when the file is absent.
- Add `_submodule_head(root: Path) -> str | None`:
  - read `root/.git`; accept a directory or a `gitdir: ...` file;
  - resolve the gitdir relative to `root`;
  - read `HEAD`; if it is `ref: X`, read `X` or the matching line in `packed-refs`;
  - return a 40-character lowercase hex SHA, else `None`.
- In `_check_component`, accept the parsed `.gitmodules` map (add a keyword parameter). When `spec.get("kind") == "git-submodule"`:
  - require the path to be registered in `.gitmodules` and require normalized URLs to match `spec["upstream"]`;
  - require `_submodule_head(root)` to exist, otherwise append:
    `"{name}: submodule is not initialized (run: git submodule update --init --recursive)"`;
  - compare HEAD with `spec["commit"]`;
  - on `update=True`, set `spec["commit"]` and `spec["verified_at"]` from the live submodule.
- Add `"head"` to the component summary.
- Keep `--update` writing the manifest, now including the refreshed commit.

- [ ] **Step 4: Convert the vendor trees**

Run, in order, from the repository root:

```powershell
$git = 'C:\Program Files\Git\cmd\git.exe'
& $git status --short
& $git rm -r --quiet vendor/pylingual vendor/xdis-src
& $git submodule add --name pylingual https://github.com/syssec-utd/pylingual vendor/pylingual
& $git -C vendor/pylingual checkout --detach 11a1516d84a6c2aa71ec23fbd11e4b99dc8c4a86
& $git submodule add --name xdis https://github.com/rocky/python-xdis vendor/xdis-src
& $git -C vendor/xdis-src checkout --detach 51e36c42a01a83d67f6530fdf7fbd42a0f387d86
& $git submodule status --recursive
```

Expected: both entries start with a space (clean, initialized) and show the pinned commits.

- [ ] **Step 5: Update the manifest and add the attribute**

Add `"kind": "git-submodule"` to both component objects in
`vendor/components.json`. Add `.gitmodules text eol=lf` to `.gitattributes`.

- [ ] **Step 6: Run the checker with update, then read-only**

```powershell
.\scripts\python.cmd .\scripts\check_vendor.py --update
.\scripts\python.cmd .\scripts\check_vendor.py
```

Expected: `"ok": true`, zero errors, file counts 150 and 1380, PyLingual tree hash
unchanged (`847072…`), xdis hash recomputed (`c2035c…`) because tracked `.pyc`
fixtures are now covered.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.\scripts\python.cmd -m unittest tests.test_vendor_manifest -v`

Expected: PASS (8 tests).

- [ ] **Step 8: Commit**

```powershell
$git = 'C:\Program Files\Git\cmd\git.exe'
& $git add .gitattributes .gitmodules scripts/check_vendor.py tests/test_vendor_manifest.py vendor/components.json vendor/pylingual vendor/xdis-src
& $git commit -m "Use git submodules for vendored upstream sources"
```

---

### Task 2: Document submodule checkout and fail clearly when absent

**Files:**
- Modify: `README.md`
- Modify: `vendor/UPSTREAM.md`
- Modify: `NOTICE`
- Modify: `scripts/pylingual.cmd`
- Modify: `docs/pylingual-portable-rd-plan.md` (two tree comments only)

**Interfaces:**
- Consumes: `.gitmodules`, `vendor/components.json`, and `check_vendor.py` from Task 1.

- [ ] **Step 1: Add the launcher guard**

In `scripts/pylingual.cmd`, before setting `PYTHONPATH`, add:

```bat
if not exist "%ROOT%\vendor\pylingual\pylingual\__init__.py" (
  echo [pylingual] Upstream submodules are not initialized. 1>&2
  echo [pylingual] Run: git submodule update --init --recursive 1>&2
  exit /b 1
)
```

- [ ] **Step 2: Update README**

Replace the "Встроенные upstream-компоненты" section with a "Upstream-компоненты (git submodules)" section that:

- states both paths are submodules pinned to the commits in the table;
- shows `git clone --recurse-submodules https://github.com/kser93/pylingual-portable-mcp.git`;
- shows `git submodule update --init --recursive` for an existing clone;
- warns that GitHub ZIP archives omit submodule contents;
- keeps the verification commands and mentions that the checker validates `.gitmodules`, HEAD, content hash, and licenses.

Also add "(submodule)" to the PyLingual row in the "Установлено локально" table.

- [ ] **Step 3: Rewrite `vendor/UPSTREAM.md`**

Keep the pins table and licenses. Replace the "embedded snapshots" wording with:

- checkout instructions;
- a description of the `.gitmodules`/gitlink/HEAD checks;
- an update procedure using `git -C vendor/<component> fetch`, `checkout --detach <commit>`, `git add vendor/<component>`, then `check_vendor.py --update`;
- a patch policy that forbids editing inside a submodule and requires a maintained fork plus `.gitmodules` URL update if patches become necessary.

- [ ] **Step 4: Update `NOTICE` and the R&D plan comments**

In `NOTICE`, say the repository references unmodified upstream source through
git submodules and list `.gitmodules` alongside `vendor/components.json`.
In `docs/pylingual-portable-rd-plan.md`, change the two
`vendor/pylingual/  # upstream snapshot` comments to
`vendor/pylingual/  # git submodule (pinned)`.

- [ ] **Step 5: Verify the missing-submodule message**

Temporarily rename the submodule directory, run the launcher, then restore it:

```powershell
Rename-Item vendor\pylingual vendor\pylingual.hidden
try { .\pylingual.cmd --version; $code = $LASTEXITCODE } finally { Rename-Item vendor\pylingual.hidden vendor\pylingual }
if ($code -ne 1) { throw "expected exit code 1, got $code" }
```

Expected: the two-line initialization hint and exit code 1; no Python traceback.

- [ ] **Step 6: Commit**

```powershell
$git = 'C:\Program Files\Git\cmd\git.exe'
& $git add README.md NOTICE vendor/UPSTREAM.md scripts/pylingual.cmd docs/pylingual-portable-rd-plan.md
& $git commit -m "Document upstream submodule workflow"
```

---

### Task 3: Verify, fresh-clone, and push

**Files:** none (verification only)

- [ ] **Step 1: Run the full local checks**

```powershell
.\scripts\python.cmd .\scripts\check_vendor.py
.\scripts\python.cmd -m unittest tests.test_vendor_manifest -v
.\scripts\python.cmd -m unittest tests.test_upstream_contract -v
.\scripts\python.cmd .\scripts\probe_mcp.py
```

Expected: all exit 0; `check_vendor` reports `"ok": true`.

- [ ] **Step 2: Verify a fresh clone initializes both submodules**

```powershell
$git = 'C:\Program Files\Git\cmd\git.exe'
$tmp = Join-Path $env:TEMP ('pylingual-submodules-' + [guid]::NewGuid())
& $git clone --recurse-submodules file:///C:/pylingual-portable $tmp
& $git -C $tmp submodule status --recursive
.\scripts\python.cmd -c "import sys; sys.path.insert(0, r'$tmp\scripts'); from check_vendor import check_components; assert check_components()['ok']"
Remove-Item -Recurse -Force $tmp
```

Expected: clone succeeds, both submodules show the pinned commits, and the checker
passes against the clone.

- [ ] **Step 3: Confirm the worktree is clean**

```powershell
$git = 'C:\Program Files\Git\cmd\git.exe'
& $git status --short
& $git log --oneline -4
```

Expected: no output from `status`; the two new commits are on top.

- [ ] **Step 4: Push**

```powershell
$git = 'C:\Program Files\Git\cmd\git.exe'
& $git push origin main
& $git ls-remote origin refs/heads/main
```

Expected: push succeeds and the remote SHA equals `git rev-parse HEAD`.

---

## Post-review corrections

A fresh-context review found that the initial checker excluded tracked xdis
`.pyc` fixtures and that `--update` could bless a missing or dirty submodule.
The implemented corrections are:

- all tracked files are hashed (xdis: 1380 files; no `.pyc`/`.pyo` exclusions);
- `--update` writes only when checks pass and refuses a dirty submodule unless
  `--force` is explicit;
- the superproject gitlink is checked when a Git executable is available;
- regression tests cover tracked `.pyc` changes, gitlink parsing, packed refs,
  and fail-closed updates (8 tests).
