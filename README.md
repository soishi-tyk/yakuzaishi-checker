# 薬剤師国試 法律適合性チェッカー v12

> **{ここに論文タイトル（日本語）を入れる}**  
> **{著者名をここに入れる}**, **{共著者名をここに入れる}**  
> Tokyo University of Pharmacy and Life Sciences  
> *JMIR* **{巻号・年・DOIをここに入れる}**

---

## 概要

薬剤師国家試験の法規・倫理・制度分野の問題文が、関連法令に適合しているかを  
**2段階AIチェック（Haiku → Sonnet）** で自動検証するWebアプリケーションです。

### 主な特徴

- **ChromaDB ベクトル検索**により、60以上の法令から関連条文のみを自動抽出
- **2段階チェック**: Stage 1（Haiku）で初回判定 → Stage 2（Sonnet）で批判的検証・最終判定
- 介護保険法など長大な法律（40万字超）にも対応
- CSVファイルをアップロードして複数問題を一括チェック可能
- 法令テキストはe-Gov APIから自動取得（インターネット接続が必要）

### v10との違い（法令検索方法のみ異なる）

| | v10 | v12（本リポジトリ） |
|---|---|---|
| 法令検索 | 全文チャンク分割 | ChromaDB ベクトル検索 |
| API呼び出し回数 | 法令長さにより3〜5回 | 常に3回（固定） |
| 長大な法律への対応 | チャンク分割（最大5チャンク） | 関連条文のみ抽出 |

---

## システム構成

```
問題文CSV
    ↓
Step 0: Haiku — 関連法令を特定（e-Gov DBから）
    ↓
ChromaDB — 意味的類似度で関連条文を抽出（各法令上位5条文）
    ↓
Step 1: claude-haiku-4-5-20251001 — 初回判定
    ↓
Step 2: claude-sonnet-4-6 — 批判的検証・最終判定
    ↓
結果CSV出力（OK / 要注意 / 不適合）
```

---

## ファイル構成

```
yakuzaishi-checker/
├── main.py              ← FastAPIサーバー
├── worker.py            ← バックグラウンドAIチェック（2段階）
├── preprocess_laws.py   ← ChromaDB構築スクリプト（初回のみ実行）
├── database.py          ← SQLiteデータベース管理
├── frontend/
│   └── index.html       ← ブラウザUI
├── .env.example         ← 環境変数テンプレート（.envにコピーして使用）
├── requirements.txt
├── LICENSE
└── README.md
```

---

## セットアップ

### 動作環境

- Python 3.10 以上
- インターネット接続（e-Gov API / Anthropic API / モデルダウンロード用）
- Anthropic APIキー（Tier 2 以上推奨）

### 手順

**1. リポジトリをクローン**

```bash
git clone https://github.com/**{GitHubユーザー名をここに入れる}**/yakuzaishi-checker.git
cd yakuzaishi-checker
```

**2. 環境変数を設定**

```bash
cp .env.example .env
```

`.env` をテキストエディタで開き、Anthropic APIキーを入力：

```
ANTHROPIC_API_KEY=sk-ant-あなたのキー
```

**3. ライブラリをインストール**

```bash
pip install -r requirements.txt
```

初回は `sentence-transformers` モデル（約420MB）が自動ダウンロードされます。Ollamaは不要です。

**4. サーバーを起動してブラウザから法令辞書を取得**

```bash
python -m uvicorn main:app --reload
```

ブラウザで `http://127.0.0.1:8000` を開き、「e-Govから最新法令を取得」を実行。

**5. ChromaDBを構築（法令取得後に1回だけ実行）**

```bash
python preprocess_laws.py
```

---

## 使い方

**毎回の起動**（PowerShellを2つ開く）

```bash
# ターミナル1
python -m uvicorn main:app --reload

# ターミナル2
python worker.py
```

1. ブラウザで `http://127.0.0.1:8000` を開く
2. 問題文CSVをアップロード（列構成: 問題文, 問題ID）
3. チェック完了後、「結果CSVダウンロード」で取得

---

## 使用モデル

| ステップ | モデル | 用途 |
|---|---|---|
| Step 0 | claude-haiku-4-5-20251001 | 関連法令の特定 |
| Step 1 | claude-haiku-4-5-20251001 | 初回判定 |
| Step 2 | claude-sonnet-4-6 | 批判的検証・最終判定 |
| 埋め込み | paraphrase-multilingual-MiniLM-L12-v2 | ChromaDBベクトル検索 |

---

## 注意事項

- `.env` ファイルは **絶対にGitHubに公開しないでください**（APIキー漏洩防止）
- Anthropic API の Tier 2 以上を推奨します（Tier 1 では429エラーが発生しやすい）
- 法令辞書を再取得した場合は `preprocess_laws.py` を再実行してください

---

## ライセンス

MIT License — 詳細は [LICENSE](LICENSE) を参照。

---

## 引用

本ソフトウェアを研究に利用する場合は以下を引用してください：

```
**{著者名をここに入れる}** (**{出版年をここに入れる}**). **{論文タイトル（英語）をここに入れる}**. *JMIR* **{巻号・DOIをここに入れる}**
```

---

---

# Pharmacist National Exam Law Compliance Checker v12

> **{Insert paper title (English) here}**  
> **{Insert author name(s) here}**  
> Tokyo University of Pharmacy and Life Sciences  
> *JMIR* **{Insert volume/issue/year/DOI here}**

---

## Overview

A web application that automatically verifies whether questions from the Japanese Pharmacist National Examination (law, ethics, and regulations domain) comply with relevant laws and regulations, using a **two-stage AI check (Haiku → Sonnet)**.

### Key Features

- **ChromaDB vector search** automatically extracts relevant articles from 60+ laws
- **Two-stage checking**: Stage 1 (Haiku) for initial judgment → Stage 2 (Sonnet) for critical verification and final judgment
- Handles lengthy laws such as the Long-Term Care Insurance Act (400,000+ characters)
- Batch processing via CSV upload
- Law texts retrieved automatically via the e-Gov API

### Difference from v10 (law retrieval method only)

| | v10 | v12 (this repository) |
|---|---|---|
| Law retrieval | Full-text chunk splitting | ChromaDB vector search |
| API calls per question | 3–5 (depends on law length) | Always 3 (fixed) |
| Long law handling | Chunk splitting (max 5 chunks) | Extract relevant articles only |

---

## System Architecture

```
Question CSV
    ↓
Step 0: Haiku — Identify relevant laws (from e-Gov DB)
    ↓
ChromaDB — Extract relevant articles by semantic similarity (top 5 per law)
    ↓
Step 1: claude-haiku-4-5-20251001 — Initial judgment
    ↓
Step 2: claude-sonnet-4-6 — Critical verification & final judgment
    ↓
Result CSV (OK / Caution / Non-compliant)
```

---

## File Structure

```
yakuzaishi-checker/
├── main.py              ← FastAPI server
├── worker.py            ← Background AI checking (two-stage)
├── preprocess_laws.py   ← ChromaDB builder (run once after law retrieval)
├── database.py          ← SQLite database management
├── frontend/
│   └── index.html       ← Browser UI
├── .env.example         ← Environment variable template
├── requirements.txt
├── LICENSE
└── README.md
```

---

## Setup

### Requirements

- Python 3.10+
- Internet connection (e-Gov API / Anthropic API / model download)
- Anthropic API key (Tier 2 or higher recommended)

### Steps

**1. Clone the repository**

```bash
git clone https://github.com/**{Insert GitHub username here}**/yakuzaishi-checker.git
cd yakuzaishi-checker
```

**2. Configure environment variables**

```bash
cp .env.example .env
```

Open `.env` and enter your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

The `sentence-transformers` model (~420 MB) will be downloaded automatically on first run. Ollama is **not required**.

**4. Start the server and retrieve law data**

```bash
python -m uvicorn main:app --reload
```

Open `http://127.0.0.1:8000` in your browser and click "Retrieve latest laws from e-Gov".

**5. Build ChromaDB (run once after law retrieval)**

```bash
python preprocess_laws.py
```

---

## Usage

**Start every session** (open two terminals):

```bash
# Terminal 1
python -m uvicorn main:app --reload

# Terminal 2
python worker.py
```

1. Open `http://127.0.0.1:8000`
2. Upload a question CSV (columns: question text, question ID)
3. Download the result CSV after processing

---

## Models Used

| Step | Model | Purpose |
|---|---|---|
| Step 0 | claude-haiku-4-5-20251001 | Identify relevant laws |
| Step 1 | claude-haiku-4-5-20251001 | Initial judgment |
| Step 2 | claude-sonnet-4-6 | Critical verification & final judgment |
| Embedding | paraphrase-multilingual-MiniLM-L12-v2 | ChromaDB vector search |

---

## Notes

- **Never commit your `.env` file** to GitHub (API key leak prevention)
- Anthropic API Tier 2 or higher is recommended (Tier 1 may cause 429 rate limit errors)
- Re-run `preprocess_laws.py` if you refresh the law database

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Citation

If you use this software in your research, please cite:

```
**{Insert author name(s) here}** (**{Insert publication year here}**). **{Insert paper title (English) here}**. *JMIR* **{Insert volume/issue/DOI here}**
```
