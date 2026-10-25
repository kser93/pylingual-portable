# Upstream components (git submodules)

`vendor/pylingual` and `vendor/xdis-src` are git submodules registered in the
repository root `.gitmodules`. They are **not** authored by this project and
must not be edited in place.

## Checkout

Clone the superproject together with its submodules:

```powershell
git clone --recurse-submodules https://github.com/kser93/pylingual-portable.git
```

For an existing clone that has no submodule contents:

```powershell
git submodule update --init --recursive
```

A GitHub "Download ZIP" archive does not contain submodule contents and cannot
be initialized with Git. Use a Git clone instead.

## Pins

| Component | Version | Upstream pin | License | Local patches |
|---|---|---|---|---|
| PyLingual | 0.1.0 | tag `v0.1.0`, commit `11a1516d84a6c2aa71ec23fbd11e4b99dc8c4a86` | GPL-3.0-only | none |
| xdis | 6.3.1.dev0 | commit `51e36c42a01a83d67f6530fdf7fbd42a0f387d86` | GPL-2.0-or-later | none |

Machine-readable pins, URLs, licenses, and tree hashes live in
[`components.json`](components.json). The Git gitlink is the authoritative
checkout pin; `components.json` duplicates it for tooling and integrity
checking.

## Verification

```powershell
.\scripts\python.cmd .\scripts\check_vendor.py
```

The checker is fully offline. It validates:

- that both component paths are registered in `.gitmodules` with the expected
  upstream URL;
- that each submodule is initialized and its checked-out HEAD matches the
  pinned commit (read from the submodule `.git` file, without requiring a
  `git` executable);
- that every tracked file under the component matches `tree_sha256` in
  `components.json` (the submodule `.git` marker is excluded);
- that the license file exists and every declared patch is present.

When a Git executable is available (on `PATH`, via `PYLINGUAL_GIT`, or via
`--git`), the checker also verifies that the superproject gitlink matches the
submodule HEAD and, for `--update`, that the submodule working tree is clean.

For the Git view of the same pins:

```powershell
git submodule status --recursive
```

## Updating a component

Updates are manual. There is no background check and no automatic apply.

1. Fetch the upstream repository and check out the exact tag or commit:

   ```powershell
   $git = 'C:\Program Files\Git\cmd\git.exe'
   & $git -C vendor/pylingual fetch origin --tags
   & $git -C vendor/pylingual checkout --detach <commit>
   ```

2. Review the diff against the currently pinned tree.
3. Stage the new gitlink and refresh the manifest:

   ```powershell
   $git = 'C:\Program Files\Git\cmd\git.exe'
   & $git add vendor/pylingual
   .\scripts\python.cmd .\scripts\check_vendor.py --update
   ```

   `--update` records the live submodule commit, tree hash, file count, and
   verification date. It refuses to write when checks fail or when the
   submodule working tree is dirty; `--force` is an explicit override. Update
   `version` and `tag` in `components.json` by hand when they change.

4. Run the tests:

   ```powershell
   .\scripts\python.cmd -m unittest tests.test_vendor_manifest
   .\scripts\python.cmd -m unittest tests.test_upstream_contract
   ```

5. Run a smoke decompilation for at least one affected Python version, with
   exact verification, for example:

   ```powershell
   .\pylingual.cmd decompile .\harness\fixtures\pyc\3.12\arithmetic.pyc `
     -o .\workspace\tmp\arithmetic.py --version 3.12
   ```

6. Update this file, `README.md`, and `NOTICE` if the version, commit, URL, or
   license changed.
7. Stage and commit the gitlink, `.gitmodules` (when the URL changed), the
   relative `components.json` change, and the documentation together:

   ```powershell
   $git = 'C:\Program Files\Git\cmd\git.exe'
   & $git add .gitmodules vendor/pylingual vendor/xdis-src vendor/components.json
   & $git commit -m "Update upstream submodule pins"
   ```

## Patch policy

The preferred state is **zero patches**. The portable wrapper integrates with
upstream through `src/pylingual_portable/upstream.py`, which replaces only two
functions at runtime:

- `pylingual.decompiler.load_models` — local safetensors snapshots instead of
  `transformers.from_pretrained`;
- `pylingual.decompiler.compile_version` — local toolchains instead of
  `uv`/`pyenv`.

Do not edit files inside a submodule. A dirty submodule makes the content hash
fail and leaves the gitlink pointing at upstream, so the change would not be
reproducible. If a source patch becomes unavoidable:

1. Put it in a maintained fork.
2. Point the `.gitmodules` URL at the fork and update `upstream` in
   `components.json`.
3. Pin the fork commit with `git submodule set-url` / `git add`, then run
   `check_vendor.py --update`.
4. Document the reason in this file and `NOTICE`.
5. If patches grow beyond a few files, keep using the fork rather than
   accumulating local edits in `vendor/`.

The `patches` list in `components.json` remains part of the schema and is
currently empty.

## Licenses

- PyLingual is GPL-3.0-only; see `vendor/pylingual/LICENSE`.
- xdis is GPL-2.0-or-later; see `vendor/xdis-src/COPYING`.
- The portable wrapper is distributed under GPL-3.0 as a combined work; see the
  repository root `LICENSE` and `NOTICE`.

Model weights are separate artifacts. They are not part of this repository;
their repositories and revisions are pinned in `models/model-links.json`.
