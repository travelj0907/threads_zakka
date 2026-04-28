"""
URL.txt（URL + 画像フォルダ名）を読み、未投稿かつ画像ありの1件を Threads に投稿する。
画像は images/<フォルダ名>/ 内の jpg/png/webp を最大5枚ランダム選択。
投稿済みは post_state.json で管理。
画像ありの URL が全員このサイクルで投稿されたら、URL.txt の全行を FALSE に戻し次のサイクルへ。
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from generate_post import (
    AMAZON_ASSOCIATE_TAG,
    RAKUTEN_AFFILIATE_ID,
    detect_affiliate_program,
    generate_post,
)
from threads_post import post_product_from_paths

ROOT = Path(__file__).parent
URL_TXT = ROOT / "URL.txt"
IMAGES_DIR = ROOT / "images"
STATE_PATH = ROOT / "post_state.json"

_IMG_SUFFIX = (".jpg", ".jpeg", ".png", ".webp")


def _strip_comment_lines(text: str) -> str:
    out = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


def load_url_entries() -> list[dict]:
    """
    URL.txt を読む。
    空行でエントリ区切り。各エントリは先頭行が URL、2行目が images/ 直下のフォルダ名。
    """
    if not URL_TXT.exists():
        return []
    raw = URL_TXT.read_text(encoding="utf-8-sig")
    body = _strip_comment_lines(raw)
    blocks = [b.strip() for b in re.split(r"\n\s*\n+", body) if b.strip()]
    entries: list[dict] = []
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        url = lines[0]
        folder = Path(lines[1]).name  # パス成分は捨て、フォルダ名のみ
        if not folder:
            continue
        entries.append({"url": url, "folder": folder})
    return entries


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"posted": {}}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"posted": {}}
    if "posted" not in data or not isinstance(data["posted"], dict):
        data = {"posted": {}}
    return data


def save_state(state: dict) -> None:
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def merge_new_urls(entries: list[dict], state: dict) -> None:
    for e in entries:
        u = e["url"]
        if u not in state["posted"]:
            state["posted"][u] = "FALSE"


def posted_flag(url: str, state: dict) -> str:
    return str(state["posted"].get(url, "FALSE"))


def postable_entries(entries: list[dict]) -> list[dict]:
    """画像が1枚以上あるエントリ（1サイクルで各1回ずつ投稿対象）。"""
    return [e for e in entries if all_images_exist(e)]


def all_postable_were_posted(entries: list[dict], state: dict) -> bool:
    """画像ありが1件以上あり、かつその全員がこのサイクルで投稿済み（FALSE でない）。"""
    pe = postable_entries(entries)
    if not pe:
        return False
    return all(posted_flag(e["url"], state).upper() != "FALSE" for e in pe)


def reset_cycle(entries: list[dict], state: dict) -> None:
    """URL.txt の全 URL を未投稿（FALSE）に戻し、次のサイクルを開始する。"""
    for e in entries:
        state["posted"][e["url"]] = "FALSE"


def maybe_reset_completed_cycle(entries: list[dict], state: dict) -> bool:
    """
    画像ありが全員投稿済みなら全行 FALSE に戻す。
    戻したら True（post_state を保存する必要あり）。
    """
    if not all_postable_were_posted(entries, state):
        return False
    reset_cycle(entries, state)
    return True


def _folder_image_candidates(entry: dict) -> list[Path]:
    folder = IMAGES_DIR / entry["folder"]
    if not folder.is_dir():
        return []
    return [
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in _IMG_SUFFIX
    ]


def image_paths_for_entry(entry: dict) -> list[Path]:
    cands = _folder_image_candidates(entry)
    if not cands:
        return []
    k = min(5, len(cands))
    return random.sample(cands, k)


def all_images_exist(entry: dict) -> bool:
    return len(_folder_image_candidates(entry)) > 0


def print_affiliate_env_warnings(entries: list[dict]) -> None:
    has_amazon = any(detect_affiliate_program(e["url"]) == "amazon" for e in entries)
    has_rakuten = any(detect_affiliate_program(e["url"]) == "rakuten" for e in entries)
    if has_amazon and not AMAZON_ASSOCIATE_TAG:
        print(
            "[警告] AMAZON_ASSOCIATE_TAG が .env に未設定です。"
            " Amazon の行は tag なし URL のまま掲載されます。"
        )
    if has_rakuten and not RAKUTEN_AFFILIATE_ID:
        print(
            "[警告] RAKUTEN_AFFILIATE_ID が .env に未設定です。"
            " 楽天 URL は hb.afl ラップなしのまま掲載されます（成果が付かない可能性があります）。"
        )


def build_candidates(
    entries: list[dict], state: dict
) -> tuple[list[dict], list[dict], list[dict]]:
    pending = [e for e in entries if posted_flag(e["url"], state).upper() == "FALSE"]
    with_img = [e for e in pending if all_images_exist(e)]
    missing = [e for e in pending if not all_images_exist(e)]
    return pending, with_img, missing


def run_check() -> int:
    entries = load_url_entries()
    if not entries:
        print("=== 投稿診断 ===\n")
        print("→ URL.txt に有効なエントリがありません（URL の次行に images/ 内のフォルダ名が必要）。")
        return 1

    state = load_state()
    merge_new_urls(entries, state)
    maybe_reset_completed_cycle(entries, state)
    save_state(state)

    print_affiliate_env_warnings(entries)
    pending, with_img, missing = build_candidates(entries, state)
    print("=== 投稿診断（URL.txt × images/ × post_state.json）===\n")
    for e in entries:
        url = e["url"]
        st = posted_flag(url, state)
        ok_img = all_images_exist(e)
        if st.upper() == "FALSE":
            ok = "投稿候補" if ok_img else "画像フォルダ不足"
        else:
            ok = "—（このサイクルで投稿済）"
        print(f"  [{ok}] {url[:60]}{'...' if len(url) > 60 else ''}")
        print(f"         フォルダ: images/{e['folder']}/  投稿済み={st}")
    print()
    if with_img:
        print(f"→ いま投稿できる件数: {len(with_img)}")
        return 0
    if pending and missing:
        print("→ 未投稿がありますが、images/<フォルダ>/ に jpg/png/webp がありません。")
        return 1
    if not pending:
        print("→ 未投稿の FALSE がありません。")
        return 1


def main(auto_mode: bool = False):
    entries = load_url_entries()
    if not entries:
        print("URL.txt が空か、URL+フォルダ名のペアがありません。")
        sys.exit(1 if auto_mode else 0)

    print_affiliate_env_warnings(entries)

    state = load_state()
    merge_new_urls(entries, state)
    maybe_reset_completed_cycle(entries, state)
    save_state(state)

    pending, pending_with_images, pending_missing = build_candidates(entries, state)

    if not pending_with_images:
        if pending_missing:
            print("未投稿の行はありますが、images/ に画像がありません。")
            for e in pending_missing[:10]:
                print(f"  {e['url'][:70]} → images/{e['folder']}/")
            if auto_mode:
                sys.exit(1)
        else:
            print("投稿できるエントリがありません。URL.txt と images/ を確認してください。")
            sys.exit(1 if auto_mode else 0)

    target = random.choice(pending_with_images)
    url = target["url"]
    paths = image_paths_for_entry(target)

    print(f"対象URL: {url}")
    print(f"フォルダ: images/{target['folder']}/  使用画像: {', '.join(p.name for p in paths)}")

    product_info = {"name": "", "product_url": url, "amazon_url": url}
    print("投稿文を生成中...")
    post_texts = generate_post(product_info=product_info)

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

    success = post_product_from_paths(
        main_text=post_texts["main_text"],
        reply_text=post_texts["reply_text"],
        image_paths=paths,
    )

    if success:
        state["posted"][url] = "TRUE"
        if maybe_reset_completed_cycle(entries, state):
            print("\n画像ありの URL はこのサイクルで全件投稿済みのため、全行を FALSE に戻しました（次からまたランダム）。")
        save_state(state)
        print("\n投稿済みを更新しました。")
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
