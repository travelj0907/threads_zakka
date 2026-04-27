"""
雑貨向け：本投稿＋ツリー返信（Amazon アフィリンク＋PR表記）
"""

import os
import random
import sys
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")

AMAZON_ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG", "").strip()

MAIN_OPENING_PREFIXES = [
    "こっそりだけど、マジで良かったから載せとく。\n\n知らない人が多すぎてもったいない。\n\n",
    "買って正解だったやつ。\n\nもう手放せない。\n\n",
    "部屋の質感が一段上がった。\n\nインテリア好きには刺さるやつ。\n\n",
    "ガチでリピ確定。\n\nこれない生活に戻れない。\n\n",
    "言い過ぎ注意だけど…\n\nマジでコスパ良すぎた。\n\n",
    "保存推奨。\n\n後で探せなくなるタイプ。\n\n",
]


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


MAIN_TEMPLATES = [
    """{hook}

{feature1}、{feature2}。
{feature3}。

{category_line}これ、名前当てたら強い。

商品名は、""",

    """{hook}

{feature1}。
{feature2}、{feature3}まで揃ってる。

{category_line}友達にも教えたくなるやつ。

答えは、""",

    """ちょっと待って。{category}でこれ知らない人多くない？

{feature1}。
{feature2}、{feature3}。

{category_line}買い逃し注意。

商品名、""",

    """{hook}

毎日使うからこそ、こだわりたい人向け。

{feature1}に{feature2}、
{feature3}まである。

{category_line}これ当てられたら通です。

名前は、""",

    """正直あんまり広めたくなかったんだけど。

{feature1}、{feature2}。
{feature3}まで体験できる。

{category_line}リンクはツリーに置いとく。""",
]

HOOK_TEMPLATES = [
    "{category}、これ当てられる？",
    "{category}沼の人、これ見て。",
    "これ買ってから{category}の基準変わった",
    "{category}で最近いちばん満足した買い物",
    "押し付けがましく言うけど、{category}好きなら見て",
]

REPLY_TEMPLATES = [
    """『{name}』です！

詳細・在庫はAmazonで確認してみて↓
{amazon_url}

※Amazonアソシエイト（PR）""",

    """答え合わせ『{name}』

気になる人はここからどうぞ↓
{amazon_url}

※Amazonアソシエイト（PR）""",

    """『{name}』/{category}

買うならリンクからどうぞ（同一商品の参考）
{amazon_url}

※Amazonアソシエイト（PR）""",
]


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
    features = [f.strip() for f in sell_point.split("・") if f.strip()]
    fallbacks = random.sample(FALLBACK_FEATURES, len(FALLBACK_FEATURES))
    fi = 0
    while len(features) < 3:
        features.append(fallbacks[fi % len(fallbacks)])
        fi += 1

    hook = random.choice(HOOK_TEMPLATES).format(category=category)
    template = random.choice(MAIN_TEMPLATES)

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

    main_text = random.choice(MAIN_OPENING_PREFIXES) + main_text

    amazon_url = to_amazon_affiliate_url(product_info.get("amazon_url", ""))
    reply_template = random.choice(REPLY_TEMPLATES)
    reply_text = reply_template.format(
        name=product_info.get("name", ""),
        category=category,
        amazon_url=amazon_url,
    )

    return {
        "main_text": main_text.strip(),
        "reply_text": reply_text.strip(),
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
