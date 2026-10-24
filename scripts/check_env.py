from __future__ import annotations

import os
import sys


def main() -> None:
    print("python:", sys.version.replace("\n", " "))
    print("executable:", sys.executable)
    print("prefix:", sys.prefix)
    for key in ("PYLINGUAL_HOME", "PYTHONHOME", "PYTHONPATH", "HF_HOME", "HF_HUB_CACHE", "TMP", "TEMP"):
        print(f"{key}: {os.environ.get(key)}")


if __name__ == "__main__":
    main()
