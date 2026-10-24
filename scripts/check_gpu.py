from __future__ import annotations

import platform
import sys


def main() -> int:
    print("Python:", sys.version.replace("\n", " "))
    print("Executable:", sys.executable)
    print("Prefix:", sys.prefix)
    print("Platform:", platform.platform())

    try:
        import torch
    except Exception as exc:  # pragma: no cover - diagnostic path
        print("torch import failed:", repr(exc))
        return 1

    print("torch:", torch.__version__)
    print("torch CUDA build:", torch.version.cuda)
    print("torch cuDNN:", torch.backends.cudnn.version())
    print("CUDA available:", torch.cuda.is_available())

    if torch.cuda.is_available():
        count = torch.cuda.device_count()
        print("CUDA device count:", count)
        for index in range(count):
            props = torch.cuda.get_device_properties(index)
            print(f"  [{index}] {torch.cuda.get_device_name(index)}")
            print(f"      capability: {props.major}.{props.minor}")
            print(f"      memory: {props.total_memory / (1024**3):.1f} GiB")
        tensor = torch.tensor([1.0, 2.0, 3.0], device="cuda")
        print("CUDA smoke:", (tensor * 2).cpu().tolist())

    try:
        import transformers
        import tokenizers
        import numpy
        import xdis

        print("transformers:", transformers.__version__)
        print("tokenizers:", tokenizers.__version__)
        print("numpy:", numpy.__version__)
        print("xdis:", getattr(xdis, "__version__", "unknown"))
    except Exception as exc:  # pragma: no cover - diagnostic path
        print("dependency import failed:", repr(exc))
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
