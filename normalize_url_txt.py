"""
URL.txt 内の http(s) 行を canonical_product_url で短縮する（再実行用）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from generate_post import canonical_product_url

ROOT = Path(__file__).parent
URL_TXT = ROOT / "URL.txt"


def main() -> None:
    raw = URL_TXT.read_text(encoding="utf-8-sig")
    lines = raw.splitlines()
    out: list[str] = []
    changed = 0
    for line in lines:
        s = line.strip()
        if s.startswith("http://") or s.startswith("https://"):
            new_u = canonical_product_url(s)
            out.append(new_u)
            if new_u != s:
                changed += 1
        else:
            out.append(line.rstrip("\r"))
    text = "\n".join(out) + ("\n" if raw.endswith("\n") else "")
    URL_TXT.write_text(text, encoding="utf-8")
    print(f"URL.txt 更新完了（変更した URL 行: {changed}）")


if __name__ == "__main__":
    main()
