from __future__ import annotations

import sys


MODULES = ["mineru", "loguru", "dotenv", "requests", "tqdm"]


def main() -> int:
    print(sys.executable)
    for module in MODULES:
        try:
            __import__(module)
        except Exception as exc:
            print(f"{module}=missing:{exc}")
        else:
            print(f"{module}=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

