from __future__ import annotations

import os
from pathlib import Path


SOURCE_ENV = Path(os.environ.get("PAPERRADAR_SOURCE_ENV", ""))
TARGET_ENV = Path(".env")
ALLOWED_PREFIXES = ("MINERU_", "PJLAB_", "OPENAI_", "OPEN_")
ALLOWED_EXACT = {"PROXY_KEY", "PROXY_USER", "PROXY_URL"}


def main() -> int:
    if not str(SOURCE_ENV):
        print("Set PAPERRADAR_SOURCE_ENV=/path/to/source.env to import selected keys.")
        return 0
    source = _read_env(SOURCE_ENV)
    existing_keys = _existing_keys(TARGET_ENV)
    imported = []
    lines = TARGET_ENV.read_text(encoding="utf-8").splitlines() if TARGET_ENV.exists() else []

    for key, value in source.items():
        if not _should_import(key) or key in existing_keys:
            continue
        imported.append(key)
        if imported == [key]:
            if lines and lines[-1].strip():
                lines.append("")
            lines.append("# Imported for MinerU / LLM parsing.")
        lines.append(f"{key}={value}")

    TARGET_ENV.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    TARGET_ENV.chmod(0o600)
    print("imported_keys=" + ",".join(imported))
    return 0


def _read_env(path: Path) -> dict[str, str]:
    values = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _existing_keys(path: Path) -> set[str]:
    return set(_read_env(path))


def _should_import(key: str) -> bool:
    return key.startswith(ALLOWED_PREFIXES) or key in ALLOWED_EXACT


if __name__ == "__main__":
    raise SystemExit(main())
