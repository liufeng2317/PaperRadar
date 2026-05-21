from __future__ import annotations

import os
import sys
import urllib.request


URLS = [
    "https://arxiv.org/list/physics.geo-ph/recent",
    (
        "https://export.arxiv.org/api/query?"
        "search_query=cat:physics.geo-ph&start=0&max_results=3"
        "&sortBy=submittedDate&sortOrder=descending"
    ),
]


def main() -> int:
    proxy_url = sys.stdin.readline().strip()
    if not proxy_url:
        print("missing proxy URL on stdin", file=sys.stderr)
        return 2

    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        os.environ[key] = proxy_url

    for url in URLS:
        print(url)
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "PaperRadar/0.1 contact: local-test"}
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                sample = response.read(500)
                status = response.status
        except Exception as exc:
            print(f"ERROR {type(exc).__name__}: {exc}")
            continue

        text = sample.decode("utf-8", errors="replace").replace("\n", " ")
        print(f"OK status={status} sample={text[:260]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

