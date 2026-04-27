"""
products.csv を読み、未投稿かつ画像ありの商品を1件 Threads に投稿する。
"""

import copy
import csv
import random
import sys
import argparse
from pathlib import Path

ROTATION_INTERVAL = 20

sys.stdout.reconfigure(encoding="utf-8")

from generate_post import generate_post, AMAZON_ASSOCIATE_TAG
from threads_post import post_product

PRODUCTS_CSV = Path(__file__).parent / "products.csv"
IMAGES_DIR = Path(__file__).parent / "images"


def load_products() -> list[dict]:
    with open(PRODUCTS_CSV, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def save_products(rows: list[dict]) -> None:
    fieldnames = rows[0].keys()
    with open(PRODUCTS_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def latest_post_serial(rows: list[dict]) -> int:
    m = 0
    for row in rows:
        val = str(row.get("投稿済み", "0"))
        if val.upper() == "TRUE":
            m = max(m, 1)
        elif val.isdigit():
            m = max(m, int(val))
    return m


def revive_for_rotation(rows: list[dict]) -> bool:
    pending = [r for r in rows if str(r.get("投稿済み", "FALSE")).upper() == "FALSE"]
    if pending:
        return False

    latest_serial = latest_post_serial(rows)
    revived = False
    for row in rows:
        val = str(row.get("投稿済み", "0"))
        posted_at = 0
        if val.upper() == "TRUE":
            posted_at = 1
        elif val.isdigit():
            posted_at = int(val)

        if posted_at > 0 and (latest_serial - posted_at) >= ROTATION_INTERVAL:
            row["投稿済み"] = "FALSE"
            revived = True
    return revived


def find_next_product(rows: list[dict]) -> dict | None:
    pending = [r for r in rows if str(r.get("投稿済み", "FALSE")).upper() == "FALSE"]
    if pending:
        return random.choice(pending)

    if revive_for_rotation(rows):
        pending = [r for r in rows if str(r.get("投稿済み", "FALSE")).upper() == "FALSE"]
        if pending:
            print(f"（{ROTATION_INTERVAL}投稿経過した商品を復活させました）")
            return random.choice(pending)

    return None


def has_images(folder_key: str) -> bool:
    folder = IMAGES_DIR / folder_key
    if not folder.exists():
        return False
    supported = [".jpg", ".jpeg", ".png"]
    return any(f.suffix.lower() in supported for f in folder.iterdir())


def build_candidates(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    pending = [r for r in rows if str(r.get("投稿済み", "FALSE")).upper() == "FALSE"]
    with_img = [r for r in pending if has_images(r["商品名"])]
    missing = [r for r in pending if not has_images(r["商品名"])]
    return pending, with_img, missing


def run_check() -> int:
    rows = load_products()
    pending, with_img, missing = build_candidates(rows)
    print("=== 投稿診断（products.csv × images/）===\n")
    for r in rows:
        name = r["商品名"]
        st = r.get("投稿済み", "")
        img = has_images(name)
        if str(st).upper() == "FALSE":
            ok = "投稿候補" if img else "画像なし（要フォルダ）"
        else:
            ok = "—（投稿済/通算管理）"
        print(f"  [{ok}] {name}  投稿済み={st}  画像={'あり' if img else 'なし'}")
    print()
    if with_img:
        print(f"→ いま投稿できる件数: {len(with_img)}（FALSE かつ images/ に jpg/png あり）")
        return 0
    if pending and missing:
        print("→ 未投稿（FALSE）はありますが、画像フォルダが空か未作成です。")
        print("→ この状態で --auto を実行しても投稿されません。")
        return 1
    if not pending:
        preview = copy.deepcopy(rows)
        if revive_for_rotation(preview):
            p2, w2, m2 = build_candidates(preview)
            if w2:
                print(
                    f"→ CSV 上は FALSE がありませんが、{ROTATION_INTERVAL} 投稿以上経過した行は "
                    f"--auto 実行時に FALSE に戻ります。"
                )
                print(f"→ 復活後に投稿できる件数: {len(w2)}")
                return 0
            if p2 and m2:
                print("→ ローテーション後も画像なしのみです。")
                return 1
        print("→ 未投稿の FALSE がありません。")
        return 1


def main(auto_mode: bool = False):
    if not AMAZON_ASSOCIATE_TAG:
        print(
            "[警告] AMAZON_ASSOCIATE_TAG が .env に未設定です。"
            " ツリーには商品URLがそのまま載ります（報酬トラッキングされません）。"
        )

    rows = load_products()
    pending, pending_with_images, pending_missing_images = build_candidates(rows)

    if not pending_with_images:
        if pending_missing_images:
            print("未投稿の商品はありますが、画像が準備できていません。")
            for r in pending_missing_images[:10]:
                print(f"  images/{r['商品名']}/")
            if auto_mode:
                print("\n[エラー] FALSE かつ画像ありの商品がありません。")
                sys.exit(1)
        else:
            find_next_product(rows)
            save_products(rows)
            pending_with_images = [
                r
                for r in rows
                if str(r.get("投稿済み", "FALSE")).upper() == "FALSE" and has_images(r["商品名"])
            ]
            if not pending_with_images:
                print("投稿できる商品がありません。画像を準備してください。")
                sys.exit(1 if auto_mode else 0)

    if not pending_with_images:
        sys.exit(1 if auto_mode else 0)

    target = random.choice(pending_with_images)
    name = target["商品名"]
    category = target["カテゴリ"]
    price = target["価格帯"]
    sell = target["売り文句"]
    amazon_url = target["Amazon商品URL"]

    print(f"対象商品: {name}")
    image_folder = IMAGES_DIR / name

    product_info = {
        "name": name,
        "amazon_url": amazon_url,
    }

    print("投稿文を生成中...")
    post_texts = generate_post(
        product_info=product_info,
        sell_point=sell,
        category=category,
        price_band=price,
    )

    print("\n=== 生成された投稿文 ===")
    print("【本投稿】")
    print(post_texts["main_text"])
    print(f"（{len(post_texts['main_text'])}文字）")
    print("\n【ツリー返信】")
    print(post_texts["reply_text"])

    if not auto_mode:
        confirm = input("\nこの内容でThreadsに投稿しますか？ [y/N]: ").strip().lower()
        if confirm != "y":
            print("投稿をキャンセルしました。")
            sys.exit(0)
    else:
        print("\n[自動モード] 確認をスキップして投稿します。")

    success = post_product(
        main_text=post_texts["main_text"],
        reply_text=post_texts["reply_text"],
        image_folder=image_folder,
    )

    if success:
        new_serial = latest_post_serial(rows) + 1
        for row in rows:
            if row["商品名"] == name:
                row["投稿済み"] = str(new_serial)
                break
        save_products(rows)
        print(f"\n投稿済みを更新: {name}（通算{new_serial}投稿目）")
    else:
        print("\n投稿に失敗しました。ログを確認してください。")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true", help="確認なしで投稿")
    parser.add_argument("--check", action="store_true", help="診断のみ")
    args = parser.parse_args()
    if args.check:
        sys.exit(run_check())
    main(auto_mode=args.auto)
