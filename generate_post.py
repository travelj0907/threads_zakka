"""
雑貨向け：本投稿＋ツリー返信（Amazon アフィリンク＋PR表記）
文面の大半は post_copy.txt で編集可能。
"""

from __future__ import annotations

import os
import random
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")

AMAZON_ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG", "").strip()

_COPY_PATH = Path(__file__).parent / "post_copy.txt"

# post_copy.txt が無い／空のときのフォールバック（最低限）
_FALLBACK_MAIN_OPENINGS = [
    "こっそりだけど、マジで良かったから載せとく。\n\n知らない人が多すぎてもったいない。\n\n",
]
_FALLBACK_HOOKS = ["{category}、これ当てられる？"]
_FALLBACK_MAIN_BODIES = [
    """{hook}

{feature1}、{feature2}。
{feature3}。

{category_line}商品名は、"""
]
_FALLBACK_REPLIES = [
    """『{name}』です！

Amazonはここからどうぞ↓
{amazon_url}

※Amazonアソシエイト（PR）"""
]


def _parse_copy_file(text: str) -> dict[str, list[str]]:
    """[section] 見出しと --- 区切りでブロックを読む。"""
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            continue
        lines.append(line)

    cleaned = "\n".join(lines)
    parts = re.split(r"(?m)^\[([a-zA-Z0-9_]+)\]\s*$", cleaned)
    out: dict[str, list[str]] = {}
    if not parts:
        return out
    # parts[0] は先頭のゴミ（通常空）
    for i in range(1, len(parts), 2):
        if i + 1 >= len(parts):
            break
        section = parts[i].lower()
        body = parts[i + 1].strip()
        blocks = [b.strip() for b in re.split(r"(?m)^---\s*$", body) if b.strip()]
        if blocks:
            out[section] = blocks
    return out


def _load_copy_lists() -> tuple[list[str], list[str], list[str], list[str]]:
    if not _COPY_PATH.exists():
        return (
            _FALLBACK_MAIN_OPENINGS,
            _FALLBACK_HOOKS,
            _FALLBACK_MAIN_BODIES,
            _FALLBACK_REPLIES,
        )
    try:
        raw = _COPY_PATH.read_text(encoding="utf-8-sig")
    except OSError:
        return (
            _FALLBACK_MAIN_OPENINGS,
            _FALLBACK_HOOKS,
            _FALLBACK_MAIN_BODIES,
            _FALLBACK_REPLIES,
        )
    data = _parse_copy_file(raw)

    openings = data.get("main_openings") or _FALLBACK_MAIN_OPENINGS
    hooks = data.get("hooks") or _FALLBACK_HOOKS
    bodies = data.get("main_bodies") or _FALLBACK_MAIN_BODIES
    replies = data.get("replies") or _FALLBACK_REPLIES
    return openings, hooks, bodies, replies


MAIN_OPENING_PREFIXES, HOOK_TEMPLATES, MAIN_TEMPLATES, REPLY_TEMPLATES = _load_copy_lists()


def to_amazon_affiliate_url(product_url: str) -> str:
    """
    Amazon 商品URLに associate tag を付与する（既に tag がある場合は上書き）。
    短縮URL（amzn.to 等）はリダイレクト後のURLでの利用が安全な場合あり。
    """
    if not product_url or not AMAZON_ASSOCIATE_TAG:
        return product_url
    parsed = urlparse(product_url.strip())
    if not parsed.netloc:
        return product_url
    qs = dict(parse_qsl(parsed.query, keep_blank_values=True))
    qs["tag"] = AMAZON_ASSOCIATE_TAG
    new_query = urlencode(qs)
    rebuilt = urlunparse(
        (parsed.scheme or "https", parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
    )
    return rebuilt


FALLBACK_FEATURES = [
    "見た目が想像以上に可愛い",
    "写真映えしすぎる",
    "触り心地が最高",
    "収納・整理がラクになる",
    "ギフトにもそのまま使える",
    "レビュー評価が安定して高い",
    "毎日のルーティンがちょっと幸せになる",
    "サイズ感がちょうどいい",
]


def _trim_at_boundary(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    for ch in ["\n", "。", "、"]:
        idx = text.rfind(ch, 0, max_len)
        if idx > max_len // 2:
            return text[: idx + 1].rstrip()
    return text[:max_len] + "…"


def _collapse_blank_lines(text: str) -> str:
    """連続改行（空行）を1行の改行にまとめる。"""
    text = text.strip()
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def generate_post(
    product_info: dict,
    sell_point: str,
    category: str,
    price_band: str = "",
) -> dict:
    """
    product_info: name, amazon_url（生URLでOK。tagは to_amazon で付与）
    返り値: {"main_text": str, "reply_text": str}
    """
    openings, hooks, bodies, replies = _load_copy_lists()

    features = [f.strip() for f in sell_point.split("・") if f.strip()]
    fallbacks = random.sample(FALLBACK_FEATURES, len(FALLBACK_FEATURES))
    fi = 0
    while len(features) < 3:
        features.append(fallbacks[fi % len(fallbacks)])
        fi += 1

    hook = random.choice(hooks).format(category=category)
    template = random.choice(bodies)

    price_sentence = ""
    if price_band and "要" not in price_band:
        price_sentence = f"{price_band}くらいで狙える。"

    category_sentence = f"{category}好きには刺さる。" if category else ""
    if price_sentence and category_sentence:
        category_line = f"{price_sentence}{category_sentence}\n"
    elif price_sentence:
        category_line = f"{price_sentence}\n"
    elif category_sentence:
        category_line = f"{category_sentence}\n"
    else:
        category_line = ""

    main_text = template.format(
        hook=hook,
        category=category,
        feature1=features[0],
        feature2=features[1],
        feature3=features[2],
        category_line=category_line,
    )

    if len(main_text) > 210:
        main_text = _trim_at_boundary(main_text, 207)

    opening = random.choice(openings).strip()
    main_text = _collapse_blank_lines(opening + "\n" + main_text)

    amazon_url = to_amazon_affiliate_url(product_info.get("amazon_url", ""))
    reply_template = random.choice(replies)
    reply_text = reply_template.format(
        name=product_info.get("name", ""),
        category=category,
        amazon_url=amazon_url,
    )
    reply_text = _collapse_blank_lines(reply_text)

    return {
        "main_text": main_text,
        "reply_text": reply_text,
    }


if __name__ == "__main__":
    demo = generate_post(
        product_info={
            "name": "サンプル ステンレスボトル",
            "amazon_url": "https://www.amazon.co.jp/dp/B0XXXXXXX",
        },
        sell_point="保温が強い・口径が広くて洗いやすい・持ち手つき",
        category="キッチン雑貨",
        price_band="3千円台",
    )
    print("=== 本投稿 ===\n", demo["main_text"])
    print("\n=== ツリー ===\n", demo["reply_text"])
