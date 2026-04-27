"""
Threads API：画像カルーセル（または1枚）＋本投稿、続けてツリー返信
"""

import os
import random
import time
import base64
import requests
from pathlib import Path
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()

THREADS_USER_ID = os.getenv("THREADS_USER_ID")
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")

IS_GITHUB_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"

THREADS_BASE_URL = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/contents"
REPO_ROOT = Path(__file__).parent

_SUPPORTED_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png")


def random_image_paths(image_folder: Path, max_count: int = 5) -> list[Path]:
    candidates = [
        p
        for p in image_folder.iterdir()
        if p.suffix.lower() in _SUPPORTED_IMAGE_SUFFIXES
    ]
    if not candidates:
        return []
    k = min(max_count, len(candidates))
    return random.sample(candidates, k)


def upload_image_to_github(image_path: Path) -> str | None:
    with open(image_path, "rb") as f:
        content = base64.b64encode(f.read()).decode()

    filename = f"uploads/{int(time.time())}_{image_path.name}"
    url = f"{GITHUB_API_URL}/{filename}"

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {
        "message": f"add image {image_path.name}",
        "content": content,
    }

    try:
        response = requests.put(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        raw_url = response.json()["content"]["download_url"]
        print(f"  GitHub アップロード完了: {image_path.name}")
        return raw_url
    except requests.RequestException as e:
        print(f"  GitHub アップロードエラー ({image_path.name}): {e}")
        return None


def github_raw_urls_for_paths(images: list[Path]) -> list[str]:
    urls = []
    for img in images:
        rel_path = img.relative_to(REPO_ROOT)
        encoded = "/".join(quote(part) for part in rel_path.parts)
        url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{encoded}"
        print(f"  使用する画像: {img.name}")
        urls.append(url)

    return urls


def upload_images(image_folder: Path) -> list[str]:
    images = random_image_paths(image_folder, max_count=5)

    if not images:
        print(f"  画像が見つかりません: {image_folder}")
        return []

    if IS_GITHUB_ACTIONS:
        print("  [GitHub Actions] リポジトリ内の画像URLを使用します")
        return github_raw_urls_for_paths(images)

    urls = []
    for img in images:
        url = upload_image_to_github(img)
        if url:
            urls.append(url)

    return urls


def create_carousel_container(image_urls: list[str]) -> list[str]:
    container_ids = []
    for url in image_urls:
        params = {
            "media_type": "IMAGE",
            "image_url": url,
            "is_carousel_item": "true",
            "access_token": THREADS_ACCESS_TOKEN,
        }
        try:
            r = requests.post(
                f"{THREADS_BASE_URL}/threads",
                params=params,
                timeout=15,
            )
            r.raise_for_status()
            container_ids.append(r.json()["id"])
            print(f"  画像コンテナ作成: {r.json()['id']}")
        except requests.RequestException as e:
            print(f"  画像コンテナ作成エラー: {e}")

    return container_ids


def create_single_image_container(image_url: str, text: str) -> str | None:
    params = {
        "media_type": "IMAGE",
        "image_url": image_url,
        "text": text,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    try:
        r = requests.post(f"{THREADS_BASE_URL}/threads", params=params, timeout=15)
        r.raise_for_status()
        return r.json()["id"]
    except requests.RequestException as e:
        print(f"  単体画像コンテナ作成エラー: {e}")
        return None


def create_carousel_post(image_urls: list[str], text: str) -> str | None:
    item_ids = create_carousel_container(image_urls)
    if not item_ids:
        return None

    print("  画像コンテナの処理を待機中（15秒）...")
    time.sleep(15)

    params = {
        "media_type": "CAROUSEL",
        "children": ",".join(item_ids),
        "text": text,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    try:
        r = requests.post(f"{THREADS_BASE_URL}/threads", params=params, timeout=15)
        r.raise_for_status()
        return r.json()["id"]
    except requests.RequestException as e:
        print(f"  カルーセルコンテナ作成エラー: {e}")
        return None


def publish_container(container_id: str) -> str | None:
    params = {
        "creation_id": container_id,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    try:
        r = requests.post(
            f"{THREADS_BASE_URL}/threads_publish",
            params=params,
            timeout=15,
        )
        r.raise_for_status()
        post_id = r.json()["id"]
        print(f"  投稿完了: post_id={post_id}")
        return post_id
    except requests.RequestException as e:
        print(f"  投稿エラー: {e}")
        return None


def post_reply(reply_to_id: str, text: str) -> str | None:
    params = {
        "media_type": "TEXT",
        "text": text,
        "reply_to_id": reply_to_id,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    try:
        r = requests.post(f"{THREADS_BASE_URL}/threads", params=params, timeout=15)
        r.raise_for_status()
        container_id = r.json()["id"]

        time.sleep(5)

        result = publish_container(container_id)
        print(f"  ツリー返信完了: {result}")
        return result
    except requests.RequestException as e:
        print(f"  ツリー返信エラー: {e}")
        return None


def post_product(main_text: str, reply_text: str, image_folder: Path) -> bool:
    """メイン投稿（画像付き）＋ツリー返信。"""
    print(f"\n[投稿開始] {image_folder.name}")

    print("画像をGitHubにアップロード中...")
    image_urls = upload_images(image_folder)

    if not image_urls:
        print("画像なしのため投稿スキップ")
        return False

    print("Threadsコンテナを作成中...")
    if len(image_urls) == 1:
        container_id = create_single_image_container(image_urls[0], main_text)
    else:
        container_id = create_carousel_post(image_urls, main_text)

    if not container_id:
        print("コンテナ作成失敗")
        return False

    print("30秒待機中...")
    time.sleep(30)

    post_id = publish_container(container_id)
    if not post_id:
        print("本投稿の公開失敗")
        return False

    print("ツリー返信を投稿中...")
    time.sleep(5)
    post_reply(post_id, reply_text)

    print(f"[完了] {image_folder.name}")
    return True
