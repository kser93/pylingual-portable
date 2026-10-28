from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__, health
from .paths import CONFIG, HF_HUB, ROOT
from .runner import decompile_file
from .upstream import assert_contract


def _doctor(skip_models: bool = False, skip_toolchains: bool = False) -> int:
    print("PYLINGUAL_HOME:", ROOT)
    print("Python:", sys.version.replace("\n", " "))
    print("Executable:", sys.executable)

    components_path = ROOT / "vendor" / "components.json"
    if components_path.exists():
        print("Embedded components:")
        try:
            components = json.loads(components_path.read_text(encoding="utf-8")).get("components", {})
        except json.JSONDecodeError as exc:
            print("  invalid vendor/components.json:", exc)
            return 1
        for name, spec in components.items():
            commit = str(spec.get("commit", "?"))[:12]
            patches = spec.get("patches", [])
            print(
                f"  {name}: {spec.get('version', '?')} @ {commit} "
                f"({spec.get('license', '?')}, patches={len(patches)})"
            )

    try:
        assert_contract()
    except Exception as exc:
        print("Upstream contract: FAILED", repr(exc))
        return 1
    print("Upstream contract: ok")

    try:
        import torch

        print("torch:", torch.__version__)
        print("torch CUDA build:", torch.version.cuda)
        print("CUDA available:", torch.cuda.is_available())
        if torch.cuda.is_available():
            print("CUDA device:", torch.cuda.get_device_name(0))
            print("CUDA capability:", ".".join(map(str, torch.cuda.get_device_capability(0))))
    except Exception as exc:
        print("torch check failed:", repr(exc))
        return 1

    report = health.installation_report(
        require_models=not skip_models,
        require_toolchains=not skip_toolchains,
    )
    print("HF cache:", HF_HUB)
    print("Complete model packs:")
    model_versions = report["models"]["models"]
    if model_versions:
        for version in model_versions:
            print(f"  {version}: ok")
    else:
        print("  none")
    for item in report["models"]["missing"]:
        print(
            f"  MISSING {item['version']}/{item['role']}: "
            f"{', '.join(str(value) for value in item['missing'])}"
        )
    for error in report["models"]["errors"]:
        print(f"  ERROR: {error}")

    print("Toolchains:")
    if report["toolchains"]["toolchains"]:
        for directory in report["toolchains"]["toolchains"]:
            print(f"  {directory}: ok")
    else:
        print("  none")
    if report["toolchains"]["missing"]:
        print("  MISSING:", ", ".join(report["toolchains"]["missing"]))

    print("Config:", CONFIG)
    return 0 if report["ok"] else 1


def _cmd_decompile(args: argparse.Namespace) -> int:
    if args.device:
        os.environ["PYLINGUAL_DEVICE"] = args.device
    result = decompile_file(
        Path(args.pyc),
        output=Path(args.output) if args.output else None,
        version=args.version,
        top_k=args.top_k,
        timeout=args.timeout,
    )
    rate = result.calculate_success_rate()
    print(f"success rate: {rate:.2%}")
    for test_result in result.equivalence_results:
        print(test_result)
    if args.output:
        print(f"saved: {Path(args.output).resolve()}")
    else:
        print()
        print(result.decompiled_source)
    return 0 if result.equivalence_results and rate == 1.0 else 1


def _cmd_mcp(args: argparse.Namespace) -> int:
    from .mcp_server import run_server

    transport = "stdio" if getattr(args, "stdio", False) else args.transport
    run_server(transport, args.host, args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local portable PyLingual")
    parser.add_argument("--version", action="version", version=f"pylingual-portable {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    decompile_parser = subparsers.add_parser("decompile", help="Decompile a .pyc file")
    decompile_parser.add_argument("pyc", help="Path to the .pyc file")
    decompile_parser.add_argument("-o", "--output", help="Output .py path")
    decompile_parser.add_argument("--version", dest="version", help="Target Python version, e.g. 3.12")
    decompile_parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="maximum alternative segmentations to consider (default: 10, upstream parity)",
    )
    decompile_parser.add_argument("--timeout", type=int, default=600)
    decompile_parser.add_argument("--device", choices=["auto", "cpu", "cuda:0"], default=None)
    decompile_parser.set_defaults(func=_cmd_decompile)

    doctor_parser = subparsers.add_parser("doctor", help="Check the local runtime")
    doctor_parser.add_argument("--skip-models", action="store_true", help="Do not require model packs")
    doctor_parser.add_argument("--skip-toolchains", action="store_true", help="Do not require target toolchains")
    doctor_parser.set_defaults(
        func=lambda args: _doctor(
            skip_models=args.skip_models,
            skip_toolchains=args.skip_toolchains,
        )
    )

    mcp_parser = subparsers.add_parser("mcp", help="Run the MCP server")
    mcp_parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    mcp_parser.add_argument("--stdio", action="store_true", help="Compatibility shortcut for --transport stdio")
    mcp_parser.add_argument("--host", default="127.0.0.1")
    mcp_parser.add_argument("--port", type=int, default=7331)
    mcp_parser.set_defaults(func=_cmd_mcp)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
