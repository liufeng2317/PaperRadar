from __future__ import annotations

from pathlib import Path


ENV_PATH = Path(".env")


def main() -> int:
    values = _read_env(ENV_PATH)
    cleaned = {
        "HTTP_PROXY": values.get("HTTP_PROXY", ""),
        "HTTPS_PROXY": values.get("HTTPS_PROXY", ""),
        "http_proxy": values.get("http_proxy", values.get("HTTP_PROXY", "")),
        "https_proxy": values.get("https_proxy", values.get("HTTPS_PROXY", "")),
        "LLM_API_KEY": _first(values, "LLM_API_KEY", "OPENAI_API_KEY", "OPEN_API_KEY", "PJLAB_API_KEY"),
        "LLM_BASE_URL": _first(
            values,
            "LLM_BASE_URL",
            "OPENAI_BASE_URL",
            "PJLAB_API_BASE_URL",
            default="https://api.openai.com/v1",
        ),
        "LLM_MODEL": _first(values, "LLM_MODEL", "OPENAI_MODEL", "PJLAB_API_CHAT_MODEL", default="gpt-4o-mini"),
        "MINERU_API_BASE": values.get("MINERU_API_BASE", ""),
        "MINERU_API_KEY": _first(values, "MINERU_API_KEY", "MINERU_API_KEY_LF"),
        "MINERU_VLM_TABLE_ENABLE": values.get("MINERU_VLM_TABLE_ENABLE", ""),
    }

    sections = [
        ("Proxy settings for local arXiv / API access.", ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]),
        ("OpenAI-compatible LLM settings for paper summaries.", ["LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"]),
        ("MinerU settings for optional PDF to Markdown parsing.", ["MINERU_API_BASE", "MINERU_API_KEY", "MINERU_VLM_TABLE_ENABLE"]),
    ]

    lines = []
    for title, keys in sections:
        if lines:
            lines.append("")
        lines.append(f"# {title}")
        for key in keys:
            lines.append(f"{key}={cleaned.get(key, '')}")

    old_keys = set(values)
    kept_keys = set(cleaned)
    removed = sorted(old_keys - kept_keys)
    ENV_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    ENV_PATH.chmod(0o600)
    print("kept_keys=" + ",".join(k for _, keys in sections for k in keys))
    print("removed_keys=" + ",".join(removed))
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


def _first(values: dict[str, str], *keys: str, default: str = "") -> str:
    for key in keys:
        value = values.get(key, "")
        if value:
            return value
    return default


if __name__ == "__main__":
    raise SystemExit(main())

