"""
extract_judge() のテスト
このセッションで実際に発生したバグをもとに作成。

実行方法:
    python -m pytest test_worker.py -v
"""
import sys
sys.path.insert(0, '.')
from worker import extract_judge


# ──────────────────────────────────────────
# 【バグ1】見出し行に判定値が書かれるケース
# 例: ## 最終判定：**不適合**
# 修正前: group(1)（見出し後の本文）だけ検索 → 見出し行を読み飛ばして "ok" を返していた
# ──────────────────────────────────────────

def test_ng_in_heading_bold():
    """## 最終判定：**不適合** → ng"""
    text = "## 最終判定：**不適合**\n\n## 初回判定の評価\n初回判定を支持"
    assert extract_judge(text) == "ng"

def test_ok_in_heading():
    """## 最終判定：OK → ok"""
    text = "## 最終判定：OK\n\n## 初回判定の評価\n初回判定を支持"
    assert extract_judge(text) == "ok"

def test_warn_in_heading():
    """## 最終判定：要注意 → warn"""
    text = "## 最終判定：要注意\n\n## 初回判定の評価\n初回判定を支持"
    assert extract_judge(text) == "warn"


# ──────────────────────────────────────────
# 【バグ2】選択肢リストの誤検出
# 例: ## 最終判定（OK／要注意／不適合）の「要注意」「不適合」を判定値と誤認
# 修正前: group(0)で見出し行ごと検索 → 選択肢リストを誤検出して "ng" や "warn" を返していた
# ──────────────────────────────────────────

def test_ok_with_options_list():
    """選択肢リスト付き見出し＋OK → ok（リスト内の「要注意」「不適合」を誤検出しない）"""
    text = "## 最終判定（OK／要注意／不適合）\nOK\n\n## 初回判定の評価\n初回判定を支持"
    assert extract_judge(text) == "ok"

def test_ng_with_options_list():
    """選択肢リスト付き見出し＋不適合 → ng"""
    text = "## 最終判定（OK／要注意／不適合）\n不適合\n\n## 初回判定の評価\n初回判定を支持"
    assert extract_judge(text) == "ng"

def test_warn_with_options_list():
    """選択肢リスト付き見出し＋要注意 → warn"""
    text = "## 最終判定（OK／要注意／不適合）\n要注意\n\n## 初回判定の評価\n初回判定を支持"
    assert extract_judge(text) == "warn"


# ──────────────────────────────────────────
# 【バグ3】本文中のキーワード誤検出
# 例: Stage2が「Stage1は要注意でしたが覆してOKとする」と書いた場合
# 修正前: 本文全体を検索 → 説明文中の「要注意」「不適合」を誤検出
# ──────────────────────────────────────────

def test_no_false_warn_from_body():
    """本文中に「要注意」が出てきても、判定がOKなら ok を返す"""
    text = (
        "## 最終判定（OK／要注意／不適合）\n"
        "OK\n\n"
        "## 初回判定の評価\n"
        "初回判定は要注意でしたが、条文を精査した結果OKと判断します。"
    )
    assert extract_judge(text) == "ok"

def test_no_false_ng_from_body():
    """本文中に「不適合」が出てきても、判定がOKなら ok を返す"""
    text = (
        "## 最終判定（OK／要注意／不適合）\n"
        "OK\n\n"
        "## 修正・補足事項\n"
        "初回の不適合判定は誤りでした。正しくはOKです。"
    )
    assert extract_judge(text) == "ok"


# ──────────────────────────────────────────
# 判定値が2行目・3行目に来るケース
# ──────────────────────────────────────────

def test_ng_on_second_line():
    """判定値が見出しの2行目 → ng"""
    text = "## 最終判定\n不適合\n\n## 補足\nなし"
    assert extract_judge(text) == "ng"

def test_ok_on_second_line():
    """判定値が見出しの2行目 → ok"""
    text = "## 最終判定\nOK\n\n## 補足\nなし"
    assert extract_judge(text) == "ok"


# ──────────────────────────────────────────
# 見出しが複数ある場合は最後の判定を採用
# ──────────────────────────────────────────

def test_last_judgment_wins():
    """複数の判定見出しがある場合、最後のものを採用する"""
    text = (
        "## 判定（仮）\n"
        "不適合\n\n"
        "## 最終判定（OK／要注意／不適合）\n"
        "OK\n"
    )
    assert extract_judge(text) == "ok"
