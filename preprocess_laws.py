"""
preprocess_laws.py - checker.db の法令テキストを条文単位に分割して ChromaDB に登録する。

使い方:
    python preprocess_laws.py          # 全法令を処理（既存のChromaDBは削除して再作成）
    python preprocess_laws.py --check  # 登録済み件数の確認のみ

前提:
    - e-Gov から法令辞書を取得済み（checker.db に法令テキストが保存されている）
    - Ollamaは不要（sentence-transformers を使用）
    - 初回実行時に埋め込みモデルを自動ダウンロード（約420MB）
"""
import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

import database as db

load_dotenv()

EMBED_MODEL     = os.getenv("EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
COLLECTION_NAME = "law_articles"
CHROMA_DIR      = Path(__file__).parent / "chroma_db"
BATCH_SIZE      = 50


def split_into_articles(law_name: str, text: str) -> list:
    """法令テキストを条文単位に分割する"""
    pattern = re.compile(r'(?=第\s*\d+\s*条(?:の\d+)?)', re.MULTILINE)
    parts   = pattern.split(text)
    articles = []

    # 前文
    if parts[0].strip():
        articles.append({
            "law_name": law_name,
            "article":  "前文",
            "text":     f"【{law_name}】前文\n{parts[0].strip()[:1500]}"
        })

    for part in parts[1:]:
        if not part.strip():
            continue
        m           = re.match(r'(第\s*\d+\s*条(?:の\d+)?)', part)
        article_num = m.group(1).replace(" ", "") if m else "不明"
        articles.append({
            "law_name": law_name,
            "article":  article_num,
            "text":     f"【{law_name}】{article_num}\n{part.strip()[:1500]}"
        })

    return articles


def main():
    # --check オプション
    if "--check" in sys.argv:
        if not CHROMA_DIR.exists():
            print("ChromaDBが見つかりません。preprocess_laws.py を実行してください。")
            return
        embedding_fn = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
        chroma       = chromadb.PersistentClient(path=str(CHROMA_DIR))
        collection   = chroma.get_collection(COLLECTION_NAME)
        print(f"ChromaDB 登録済み条文数: {collection.count()}件")
        return

    db.init_db()
    laws = [l for l in db.get_all_laws() if not l["error"] and l["text"]]

    if not laws:
        print("法令辞書が取得されていません。先にブラウザから「e-Govから最新法令を取得」を実行してください。")
        sys.exit(1)

    print(f"法令数: {len(laws)}件")
    print(f"埋め込みモデル: {EMBED_MODEL}")
    print("（初回実行時はモデルを自動ダウンロードします。約420MB）\n")

    # 埋め込み関数の初期化（初回はモデルをダウンロード）
    print("埋め込みモデル読み込み中...", end="", flush=True)
    embedding_fn = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    print(" 完了\n")

    # ChromaDB 初期化（既存は削除して再作成）
    CHROMA_DIR.mkdir(exist_ok=True)
    chroma = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        chroma.delete_collection(COLLECTION_NAME)
        print("既存のChromaDBコレクションを削除しました")
    except Exception:
        pass
    collection = chroma.create_collection(
        COLLECTION_NAME,
        embedding_function=embedding_fn
    )

    total_articles = 0

    for law in laws:
        law_name = law["name"]
        chars    = law.get("char_count", 0) or 0
        articles = split_into_articles(law_name, law["text"])
        print(f"処理中: {law_name} ({chars:,}文字 → {len(articles)}条文)", flush=True)

        # バッチ登録
        for i in range(0, len(articles), BATCH_SIZE):
            batch = articles[i:i + BATCH_SIZE]
            collection.add(
                ids=[f"{law_name}_{a['article']}_{i+j}" for j, a in enumerate(batch)],
                documents=[a["text"] for a in batch],
                metadatas=[{"law_name": a["law_name"], "article": a["article"]} for a in batch]
            )

        total_articles += len(articles)

    print(f"\n全法令処理完了: {total_articles}条文を ChromaDB に登録しました")
    print(f"保存先: {CHROMA_DIR}")
    print("\n次: python worker.py")


if __name__ == "__main__":
    main()
