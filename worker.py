"""
worker.py - 薬剤師国試 法律適合性チェッカー v12

【処理フロー】
  Step 0 : 問題文から関連法令を特定（略称マッピング → LLMフォールバック）
  Step 1 : ChromaDB ベクトル検索で関連条文を抽出
           → claude-haiku-4-5-20251001 で初回判定
  Step 2 : claude-sonnet-4-6 が初回判定を批判的検証 → 最終判定

【v10との違い】法令検索方法のみ異なる
  v10: 法令全文をチャンク分割してAIに渡す
  v12: ChromaDBベクトル検索で関連条文のみを抽出してAIに渡す
"""
import os
import re
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
import anthropic
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

import database as db

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

COLLECTION_NAME  = "law_articles"
CHROMA_DIR       = Path(__file__).parent / "chroma_db"
EMBED_MODEL      = os.getenv("EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")

MODEL_STAGE1     = "claude-haiku-4-5-20251001"
MODEL_STAGE2     = "claude-sonnet-4-6"
LABEL_STAGE1     = "Haiku 初回判定"
LABEL_STAGE2     = "Sonnet 最終検証"

INTERVAL_SEC     = 6
RETRY_WAIT_SEC   = 65
MAX_RETRIES      = 5
TOP_K_PER_LAW    = 5
MAX_LAWS         = 4
STAGE1_MAX_CHARS = 4000


# ══════════════════════════════════════════════════════════
#  法令略称マッピング
# ══════════════════════════════════════════════════════════

LAW_ABBREV = {
    "薬機法":          "医薬品医療機器等法（薬機法）",
    "薬事法":          "医薬品医療機器等法（薬機法）",
    "麻向法":          "麻薬及び向精神薬取締法",
    "麻薬取締法":      "麻薬及び向精神薬取締法",
    "覚醒剤法":        "覚醒剤取締法",
    "毒劇法":          "毒物及び劇物取締法",
    "大麻法":          "大麻草の栽培の規制に関する法律",
    "あへん法":        "あへん法",
    "感染症法":        "感染症法",
    "個人情報保護法":  "個人情報の保護に関する法律",
    "介護保険":        "介護保険法",
    "健康保険":        "健康保険法",
    "国民健康保険":    "国民健康保険法",
    "精神保健福祉法":  "精神保健及び精神障害者福祉に関する法律",
    "難病法":          "難病の患者に対する医療等に関する法律",
    "臨床研究法":      "臨床研究法",
    "再生医療法":      "再生医療等の安全性の確保等に関する法律",
}


# ══════════════════════════════════════════════════════════
#  Step 0: 関連法令の特定
# ══════════════════════════════════════════════════════════

def get_available_laws() -> list:
    laws = db.get_all_laws()
    return [l for l in laws if not l["error"] and l["text"]]


def identify_laws_from_text(question: str, all_law_names: list) -> list:
    matched = []
    for abbrev, full_name in LAW_ABBREV.items():
        if abbrev in question and full_name in all_law_names and full_name not in matched:
            matched.append(full_name)
    for name in all_law_names:
        if name not in matched and (
            name in question or any(
                part in question for part in name.split("の") if len(part) >= 4
            )
        ):
            matched.append(name)
    return matched[:MAX_LAWS]


def identify_laws_by_llm(question: str, all_law_names: list) -> list:
    """Haikuを使ったLLMフォールバック"""
    law_list_str = "\n".join(f"・{n}" for n in all_law_names)
    prompt = (
        "以下の薬剤師国家試験の問題を読み、判定に必要な法令を下記リストから最大3つ選んでください。\n"
        "法令名のみをカンマ区切りで1行で出力してください（説明不要）。\n\n"
        f"【法令リスト】\n{law_list_str}\n\n"
        f"【問題文（先頭のみ）】\n{question[:600]}\n\n"
        "関連法令（法令名のみカンマ区切り）："
    )
    try:
        response = call_api(prompt, MODEL_STAGE1, max_tokens=128)
        candidates = [c.strip().strip("・") for c in re.split(r"[,、，\n]", response)]
        matched = []
        for cand in candidates:
            for name in all_law_names:
                if cand and (cand == name or cand in name or name in cand):
                    if name not in matched:
                        matched.append(name)
                    break
        return matched[:MAX_LAWS]
    except Exception:
        return []


def identify_relevant_laws(question: str, available_laws: list) -> list:
    all_law_names = [l["name"] for l in available_laws]
    if not all_law_names:
        return []
    matched = identify_laws_from_text(question, all_law_names)
    if matched:
        return matched
    matched = identify_laws_by_llm(question, all_law_names)
    if matched:
        return matched
    sorted_laws = sorted(available_laws, key=lambda l: -(l.get("char_count") or 0))
    return [l["name"] for l in sorted_laws[:2]]


# ══════════════════════════════════════════════════════════
#  ChromaDB ベクトル検索
# ══════════════════════════════════════════════════════════

def search_articles(collection, embedding_fn, question: str, law_names: list) -> list:
    q_emb    = embedding_fn([question[:600]])[0]
    articles = []
    for law_name in law_names:
        try:
            results = collection.query(
                query_embeddings=[q_emb],
                n_results=TOP_K_PER_LAW,
                where={"law_name": {"$eq": law_name}},
                include=["documents", "metadatas", "distances"],
            )
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                articles.append({
                    "law_name": meta["law_name"],
                    "article":  meta["article"],
                    "text":     doc,
                    "score":    round(1 - dist, 4),
                })
        except Exception as e:
            print(f"[worker] {law_name} 検索エラー: {e}")
    return sorted(articles, key=lambda x: -x["score"])


# ══════════════════════════════════════════════════════════
#  プロンプト構築
# ══════════════════════════════════════════════════════════

def build_stage1_prompt(question: str, dict_date: str, articles: list) -> str:
    law_context = "\n\n".join(a["text"] for a in articles) if articles else "（該当条文なし）"
    return f"""【重要指示】
・必ず日本語のみで回答してください。
・「具体的な記述がない」「記述が不明確」などの形式的な指摘は行わないでください。
・判定（OK/要注意/不適合）は法令との整合性のみで行ってください。

【法令条文（{dict_date}時点）】
{law_context}

【問題・正解・解説】
{question}

━━━━━━━━━━━━━━━━━━━━━━━━
薬事法規の専門家として、上記の法令条文と照らし合わせて分析してください。

### 1. 問題のポイント
（この問題が問う法的論点を1〜2文で説明）

### 2. 選択肢の検討
各選択肢について、根拠条文番号を明記した上で正誤を判定してください。
（例: 選択肢1: 誤り。第○条第○項により〜）

### 3. 実務への応用・補足
（関連する規定、混同しやすい他の条文、記憶のポイント等）

## 判定（OK／要注意／不適合）
（OKは問題と解説が法令と整合している場合。明らかな法的誤りがある場合のみ「不適合」とし、その根拠条文を示すこと）
"""


def build_stage2_prompt(question: str, dict_date: str,
                        result1: str, law_names: list) -> str:
    stage1_text = result1 if len(result1) <= STAGE1_MAX_CHARS else result1[:STAGE1_MAX_CHARS] + "\n\n[... 省略 ...]"
    laws_used   = "、".join(law_names)
    return f"""【重要指示】
・必ず日本語のみで回答してください。
・「具体的な記述がない」「記述が不明確」などの形式的な指摘は行わないでください。
・判定（OK/要注意/不適合）は法令との整合性のみで行ってください。
・初回判定の各選択肢の正誤判断・条文番号引用が正確かどうかを確認してください。

【参照法令】{laws_used}（辞書基準日: {dict_date}）

【1回目の分析（{LABEL_STAGE1}）】
{stage1_text}

【問題・正解・解説】
{question}

━━━━━━━━━━━━━━━━━━━━━━━━
上記の初回分析を批判的に検証してください。

### 検証のポイント
- 引用された条文番号は正確か
- 各選択肢の正誤判断に誤りはないか
- 法的に重要な見落としはないか

## 最終判定（OK／要注意／不適合）
（法令との整合性のみで判定。明らかな法的誤りがある場合のみ「不適合」）

## 初回判定の評価
（条文番号・正誤判断の正確性を確認。問題なければ「初回判定を支持」）

## 修正・補足事項
（法的に重要な追記があれば記載。なければ「なし」）
"""


# ══════════════════════════════════════════════════════════
#  API呼び出し・判定抽出
# ══════════════════════════════════════════════════════════

def call_api(prompt: str, model: str, max_tokens: int = 1024) -> str:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except anthropic.RateLimitError:
            if attempt == MAX_RETRIES:
                raise
            print(f"[worker] 429 レート制限 → {RETRY_WAIT_SEC}秒待機 ({attempt}/{MAX_RETRIES})")
            time.sleep(RETRY_WAIT_SEC)
        except Exception as e:
            if attempt == MAX_RETRIES:
                raise
            print(f"[worker] エラー: {e} → 5秒待機 ({attempt}/{MAX_RETRIES})")
            time.sleep(5)


def extract_judge(text: str) -> str:
    # 最後の「判定」見出しを探す
    matches = list(re.finditer(r"##\s*(?:最終)?判定[^\n]*", text))
    if matches:
        last = matches[-1]
        # 見出し行からカッコ内の選択肢リスト（OK／要注意／不適合）を除去
        heading_clean = re.sub(r'[（(][^）)]*[）)]', '', last.group(0))
        # 見出し直後の最初の非空行を取得（改行後に判定値が来るケース）
        rest = text[last.end():]
        first_line = ''
        for line in rest.split('\n'):
            s = line.strip()
            if s and not s.startswith('#'):
                first_line = s
                break
        # 判定対象：見出し行（選択肢除去済み）＋直後の1行のみ
        judge_text = heading_clean + ' ' + first_line
    else:
        # 見出しなし：末尾500文字で判定
        judge_text = text[-500:]

    if "不適合" in judge_text:
        return "ng"
    if "要注意" in judge_text:
        return "warn"
    return "ok"


def extract_summary(text: str) -> str:
    lines = [l for l in text.split("\n") if l.strip() and not l.startswith("#")]
    return lines[0][:100] if lines else ""


# ══════════════════════════════════════════════════════════
#  メインループ
# ══════════════════════════════════════════════════════════

def run():
    db.init_db()

    if not CHROMA_DIR.exists():
        print("[worker] ChromaDBが見つかりません。先に preprocess_laws.py を実行してください。")
        sys.exit(1)

    print(f"[worker] 埋め込みモデル読み込み中: {EMBED_MODEL} ...")
    embedding_fn = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    chroma       = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection   = chroma.get_collection(COLLECTION_NAME)
    print(f"[worker] ChromaDB: {collection.count()}件の条文ベクトル読み込み済み")
    print(f"[worker] 起動（Step0:法令特定 → Step1:{MODEL_STAGE1} → Step2:{MODEL_STAGE2}）")

    while True:
        jobs = db.get_pending_jobs(limit=1)
        if not jobs:
            time.sleep(2)
            continue

        job    = jobs[0]
        job_id = job["id"]
        print(f"[worker] ジョブ#{job_id} 開始")
        db.update_job(job_id, status="processing")

        try:
            question  = job["question"]
            dict_date = job.get("dict_date") or ""

            # ── Step 0: 関連法令の特定 ────────────────────
            available_laws = get_available_laws()
            law_names      = identify_relevant_laws(question, available_laws)
            print(f"[worker] ジョブ#{job_id} 特定された法令: {law_names}")

            # ── ベクトル検索 ──────────────────────────────
            print(f"[worker] ジョブ#{job_id} 条文検索中...", end="", flush=True)
            articles = search_articles(collection, embedding_fn, question, law_names) if law_names else []
            print(f" {len(articles)}件取得")

            # ── Step 1: Haiku 初回判定 ────────────────────
            print(f"[worker] ジョブ#{job_id} Step1({MODEL_STAGE1})...", end="", flush=True)
            result1 = call_api(
                build_stage1_prompt(question, dict_date, articles),
                MODEL_STAGE1, max_tokens=2048
            )
            judge1 = extract_judge(result1)
            print(f" [{judge1}]")

            # ── Step 2: Sonnet 最終検証 ───────────────────
            print(f"[worker] ジョブ#{job_id} Step2({MODEL_STAGE2})...", end="", flush=True)
            result2 = call_api(
                build_stage2_prompt(question, dict_date, result1, law_names),
                MODEL_STAGE2, max_tokens=2048
            )
            judge2 = extract_judge(result2)
            print(f" [{judge2}]")

            # ── 結果保存 ──────────────────────────────────
            laws_used = "、".join(law_names)
            arts_used = ", ".join(f"{a['law_name']} {a['article']}" for a in articles[:5])
            final_result = (
                f"## 【参照法令】{laws_used}\n\n"
                f"## 【参照条文】{arts_used}\n\n"
                f"## 【1回目：{LABEL_STAGE1}】\n\n{result1}\n\n"
                "---\n\n"
                f"## 【2回目：{LABEL_STAGE2}】\n\n{result2}"
            )
            db.update_job(job_id, status="done", judge=judge2,
                          result=final_result, summary=extract_summary(result2))
            print(f"[worker] ジョブ#{job_id} 完了 [{judge2}]")

        except Exception as e:
            db.update_job(job_id, status="error", result=str(e), summary="エラー")
            print(f"[worker] ジョブ#{job_id} エラー: {e}")

        time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    run()
