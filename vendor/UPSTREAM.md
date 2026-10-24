# Embedded upstream components

`vendor/` contains third-party source snapshots used by the portable wrapper.
They are **not** authored by this project and must not be edited in place.

## Pins

| Component | Version | Upstream pin | License | Local patches |
|---|---|---|---|---|
| PyLingual | 0.1.0 | tag `v0.1.0`, commit `11a1516d84a6c2aa71ec23fbd11e4b99dc8c4a86` | GPL-3.0-only | none |
| xdis | 6.3.1.dev0 | commit `51e36c42a01a83d67f6530fdf7fbd42a0f387d86` | GPL-2.0-or-later | none |

Machine-readable pins, licenses and tree hashes live in
[`components.json`](components.json).

## Verification

```powershell
.\scripts\python.cmd .\scripts\check_vendor.py
```

The checker hashes every file under each component (relative path + normalized
LF content) and compares the result with `tree_sha256` in `components.json`.
It also checks that the license file exists and that every declared patch is
present. It is fully offline.

The current snapshot was verified on 2026-10-24 against upstream checkouts:

- `vendor/pylingual`: 150 files, byte-identical to PyLingual tag `v0.1.0`
  (commit `11a1516d84a6c2aa71ec23fbd11e4b99dc8c4a86`).
- `vendor/xdis-src`: 318 files (excluding `build/`, `dist/` and `*.egg-info`),
  byte-identical to xdis commit
  `51e36c42a01a83d67f6530fdf7fbd42a0f387d86`.
- The `xdis` package installed into the portable runtime matches
  `vendor/xdis-src/xdis` (apart from upstream `.gitignore` files).

## Updating a component

Updates are manual. There is no background check and no automatic apply.

1. Fetch the upstream repository into a temporary directory.
2. Check out the exact tag or commit to adopt.
3. Compare it with the current `vendor/` tree and review the diff.
4. Replace the vendored tree.
5. Run `.\scripts\python.cmd .\scripts\check_vendor.py --update` to record the
   new tree hash and date.
6. Run the upstream contract test:

   ```powershell
   .\scripts\python.cmd -m unittest tests.test_upstream_contract
   ```

7. Run a smoke decompilation for at least one affected Python version, with
   exact verification, for example:

   ```powershell
   .\pylingual.cmd decompile .\harness\fixtures\pyc\3.12\arithmetic.pyc `
     -o .\workspace\tmp\arithmetic.py --version 3.12
   ```

8. Update this file and `NOTICE` if the version, commit or license changed.
9. Commit the vendor change and the updated manifest together.

## Patch policy

The preferred state is **zero patches**. The portable wrapper integrates with
upstream through `src/pylingual_portable/upstream.py`, which replaces only two
functions at runtime:

- `pylingual.decompiler.load_models` — local safetensors snapshots instead of
  `transformers.from_pretrained`;
- `pylingual.decompiler.compile_version` — local toolchains instead of
  `uv`/`pyenv`.

If a source patch becomes unavoidable:

1. Put it under `patches/<component>/0001-short-description.patch`.
2. Record the path in `components.json` under the component's `patches` list.
3. Apply it only in the build/sync step, not by hand-editing `vendor/`.
4. Recompute the tree hash and document the reason in this file.
5. If patches grow beyond a few files, switch to a maintained fork instead of
   accumulating patches in the portable repository.

## Licenses

- PyLingual is GPL-3.0-only; see `vendor/pylingual/LICENSE`.
- xdis is GPL-2.0-or-later; see `vendor/xdis-src/COPYING`.
- The portable wrapper is distributed under GPL-3.0 as a combined work; see the
  repository root `LICENSE` and `NOTICE`.

Model weights are separate artifacts. They are not part of this repository;
their repositories and revisions are pinned in `models/model-links.json`.
