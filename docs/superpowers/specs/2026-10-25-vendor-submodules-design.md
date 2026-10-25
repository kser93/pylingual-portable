# Vendor Dependencies as Git Submodules — Design

**Date:** 2026-10-25
**Status:** approved by the repository owner

## Intent

Formalize the project's external source dependencies as git submodules so the
main repository contains links to the exact upstream commits instead of
duplicated source snapshots.

## Goals

- Replace `vendor/pylingual` and `vendor/xdis-src` snapshots with git submodules.
- Pin each submodule to the commit currently recorded in
  `vendor/components.json`.
- Keep the offline integrity check meaningful: `.gitmodules` URL, submodule
  HEAD commit, license presence, and a hash of the checked-out tree.
- Make a clone without initialized submodules fail with a clear instruction.
- Keep `runtime/`, `toolchains/`, and `models/` as local binary artifacts;
  they are not git repositories and cannot be submodules.

## Non-goals

- No forks or local patches.
- No change to model or toolchain download logic.
- No new CI service or automatic upstream updates.

## Approaches Considered

1. **Direct upstream submodules (chosen).** `.gitmodules` points at
   `syssec-utd/pylingual` and `rocky/python-xdis`; gitlinks pin the existing
   commits. Simple and matches the zero-patch policy.
2. **Forks under `kser93`.** Useful only if local patches become necessary;
   adds fork maintenance for no current benefit.
3. **Keep snapshots.** Rejected: does not satisfy the submodule requirement.

## Design

- `.gitmodules` registers both components with their canonical upstream URLs.
- `vendor/components.json` gains `kind: "git-submodule"` and remains the
  machine-readable source of versions, commits, licenses, and tree hashes.
- `scripts/check_vendor.py` checks:
  - the `.gitmodules` path/URL pair;
  - the submodule HEAD from its `.git` file (no git executable required);
  - the content tree hash, excluding the submodule `.git` file;
  - the license file.
- `scripts/check_vendor.py --update` refreshes the commit, tree hash, and
  verification date after a reviewed submodule checkout.
- `scripts/pylingual.cmd` prints an initialization hint when the PyLingual
  submodule is absent.
- README, `vendor/UPSTREAM.md`, and `NOTICE` document recursive clone,
  verification, update, and patch policy.

## Verification

- `scripts/python.cmd -m unittest tests.test_vendor_manifest`
- `scripts/python.cmd scripts/check_vendor.py`
- `scripts/python.cmd -m unittest tests.test_upstream_contract`
- `scripts/python.cmd scripts/check_opencode_harness.py`
- A fresh clone with `--recurse-submodules` launches and passes the checker.

## Risks

- **Clone without submodules:** the launcher and checker print the exact
  `git submodule update --init --recursive` command.
- **GitHub ZIP:** does not include submodule contents; README states this.
- **Upstream tag removal:** the gitlink uses a full commit SHA; if upstream
  disappears, the project must switch to a maintained fork.
- **Local edits in a submodule:** the tree hash fails; policy is to use a fork,
  never edit `vendor/` in place.
