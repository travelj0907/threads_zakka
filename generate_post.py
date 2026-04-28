"""
雑貨向け：本投稿は sample.txt からランダム、ツリーは商品 URL ＋ PR。
Amazon → tag 付与、楽天市場等 → hb.afl ラップ（.env の ID 使用）。
楽天はクエリ・フラグメント（広告・計測用など）を除いてからラップする。
"""

from __future__ import annotations

import os
import random
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")

AMAZON_ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG", "").strip()
RAKUTEN_AFFILIATE_ID = os.getenv("RAKUTEN_AFFILIATE_ID", "").strip()

SAMPLE_PATH = Path(__file__).parent / "sample.txt"

# Threads 本投稿の目安（長すぎると弾かれることがあるため）
_MAIN_MAX_CHARS = 480

# ツリー返信：商品名の直後にランダムで1行入れる
_REPLY_EXCLAMATIONS = [
    "こちらです！！",
    "これこれ！！",
    "か、可愛い！！！",
    "発想が可愛すぎる…！！！",
    "最高すぎる…！！",
]

# 商品ページの ASIN をパスから抜き出す（検索・スポンサー用の長い URL を短くする）
_ASIN_IN_PATH = re.compile(
    r"(?:/dp/|/gp/product/|/d/|/gp/aw/d/)([A-Z0-9]{10})(?:/|$|\?|#)",
    re.IGNORECASE,
)


def canonical_amazon_url(product_url: str) -> str:
    """
    Amazon の商品 URL を https://ホスト/dp/ASIN の最短形に揃える。
    ASIN がパスから取れない場合は元の文字列を返す。
    """
    if not (product_url or "").strip():
        return ""
    raw = product_url.strip()
    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower()
    if not host or "amazon." not in host:
        return raw
    path = parsed.path or ""
    m = _ASIN_IN_PATH.search(path)
    if not m:
        return raw
    asin = m.group(1).upper()
    scheme = (parsed.scheme or "https").lower()
    if scheme not in ("http", "https"):
        scheme = "https"
    return urlunparse((scheme, host, f"/dp/{asin}", "", "", ""))


def canonical_rakuten_product_url(product_url: str) -> str:
    """
    楽天ドメインの URL からクエリ・フラグメントを除いた最短形に揃える。
    （scid, gclid, icm_* など計測・広告パラメータを落としてから hb.afl に載せる）
    hb.afl は第三者のアフィ形式なのでそのまま返す。
    """
    if not (product_url or "").strip():
        return ""
    raw = product_url.strip()
    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower()
    if not host:
        return raw
    if host == "hb.afl.rakuten.co.jp" or host.endswith(".afl.rakuten.co.jp"):
        return raw
    if "rakuten.co.jp" not in host:
        return raw
    scheme = (parsed.scheme or "https").lower()
    if scheme not in ("http", "https"):
        scheme = "https"
    path = parsed.path or ""
    return urlunparse((scheme, host, path, "", "", ""))


def canonical_product_url(product_url: str) -> str:
    """
    Amazon → ASIN の最短 URL、楽天 → クエリ除去、hb.afl はそのまま、その他はトリムのみ。
    URL.txt の整形や投稿直前の正規化に使う。
    """
    if not (product_url or "").strip():
        return ""
    raw = product_url.strip()
    kind = detect_affiliate_program(raw)
    if kind == "amazon":
        return canonical_amazon_url(raw)
    if kind == "rakuten":
        return canonical_rakuten_product_url(raw)
    return raw


def detect_affiliate_program(product_url: str) -> str:
    """商品 URL の種別: amazon / rakuten / other"""
    if not (product_url or "").strip():
        return "other"
    parsed = urlparse(product_url.strip())
    host = (parsed.netloc or "").lower()
    if not host:
        return "other"
    if host == "hb.afl.rakuten.co.jp" or host.endswith(".afl.rakuten.co.jp"):
        return "rakuten"
    if "amazon." in host:
        return "amazon"
    if "rakuten.co.jp" in host:
        return "rakuten"
    return "other"


def to_amazon_affiliate_url(product_url: str) -> str:
    if not product_url:
        return ""
    base = canonical_amazon_url(product_url.strip())
    if not AMAZON_ASSOCIATE_TAG:
        return base
    parsed = urlparse(base)
    if not parsed.netloc:
        return base
    qs = {"tag": AMAZON_ASSOCIATE_TAG}
    new_query = urlencode(qs)
    return urlunparse(
        (parsed.scheme or "https", parsed.netloc, parsed.path, parsed.params, new_query, "")
    )


def to_rakuten_affiliate_url(product_url: str) -> str:
    """
    楽天アフィリエイトのリダイレクト URL（公式形式）に変換する。
    https://hb.afl.rakuten.co.jp/hgc/<アフィリエイトID>/?pc=<URLエンコード>&m=同一
    """
    if not product_url:
        return ""
    raw = canonical_rakuten_product_url(product_url)
    if not raw:
        return ""
    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower()
    if host == "hb.afl.rakuten.co.jp" or host.endswith(".afl.rakuten.co.jp"):
        return raw
    if "rakuten.co.jp" not in host:
        return raw
    if not RAKUTEN_AFFILIATE_ID:
        return raw
    aid = RAKUTEN_AFFILIATE_ID.strip().strip("/")
    enc = quote(raw, safe="")
    return f"https://hb.afl.rakuten.co.jp/hgc/{aid}/?pc={enc}&m={enc}"


def to_affiliate_product_url(product_url: str) -> str:
    kind = detect_affiliate_program(product_url)
    if kind == "amazon":
        return to_amazon_affiliate_url(product_url)
    if kind == "rakuten":
        return to_rakuten_affiliate_url(product_url)
    return (product_url or "").strip()


def _strip_comment_lines(text: str) -> str:
    """行頭が # の行をコメントとして除く（# のみ・# の後にスペース可）。"""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


def load_sample_main_texts() -> list[str]:
    """
    sample.txt を読む。
    - 1行の改行 → そのまま1本の投稿内の改行
    - 空行（連続改行含む）→ 次の投稿文の区切り
    """
    if not SAMPLE_PATH.exists():
        return [
            "sample.txt を同じフォルダに作成し、投稿文を書いてください。\n"
            "（空行で投稿と投稿を区切ります）"
        ]
    try:
        raw = SAMPLE_PATH.read_text(encoding="utf-8-sig")
    except OSError:
        return ["sample.txt を読めませんでした。"]

    body = _strip_comment_lines(raw)
    blocks = [b.strip() for b in re.split(r"\n\s*\n+", body) if b.strip()]
    return blocks if blocks else ["sample.txt に投稿文がありません（空行で区切ってください）。"]


def _trim_main(text: str, max_len: int = _MAIN_MAX_CHARS) -> str:
    if len(text) <= max_len:
        return text
    for ch in ["\n", "。", "、"]:
        idx = text.rfind(ch, 0, max_len)
        if idx > max_len // 2:
            return text[: idx + 1].rstrip()
    return text[: max_len - 1] + "…"


def generate_post(
    product_info: dict,
    sell_point: str = "",
    category: str = "",
    price_band: str = "",
) -> dict:
    """
    本投稿: sample.txt から1つランダム（sell_point / price_band は未使用）。
    ツリー: 決まり文句（5種ランダム）+ アフィリエイト付き URL + ※PR（商品名は出さない）
    """
    _ = sell_point, price_band, category  # 互換のため引数は残す

    candidates = load_sample_main_texts()
    main_text = random.choice(candidates)
    main_text = _trim_main(main_text)

    raw_url = (product_info.get("product_url") or product_info.get("amazon_url") or "").strip()
    out_url = to_affiliate_product_url(raw_url)
    hook = random.choice(_REPLY_EXCLAMATIONS)
    reply_text = f"{hook}\n{out_url}\n※PR"

    return {
        "main_text": main_text.strip(),
        "reply_text": reply_text.strip(),
    }


if __name__ == "__main__":
    demo = generate_post(
        product_info={
            "name": "サンプル商品",
            "product_url": "https://www.amazon.co.jp/dp/B0XXXXXXX",
        },
        category="キッチン雑貨",
    )
    print("=== 本投稿 ===")
    print(demo["main_text"])
    print("\n=== ツリー（Amazon 例）===")
    print(demo["reply_text"])
    demo2 = generate_post(
        product_info={
            "product_url": "https://item.rakuten.co.jp/example/abc/",
        },
    )
    print("\n=== ツリー（楽天 例・ID 未設定なら生 URL）===")
    print(demo2["reply_text"])
    print(f"\n（候補数: {len(load_sample_main_texts())}）")
