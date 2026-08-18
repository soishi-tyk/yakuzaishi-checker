"""
main.py
FastAPIサーバー。フロントエンドとworker.pyの橋渡しをする。
"""
import csv
import io
import json
import os
import re
import asyncio
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import aiohttp
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database as db

load_dotenv()
db.init_db()

app = FastAPI(title="薬剤師国試 法律適合性チェッカー")

FRONTEND_DIR = Path(__file__).parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


def get_today_jp():
    now = datetime.now()
    return f"{now.year}年{now.month}月{now.day}日"


@app.get("/")
def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


E_GOV_LIST_URL = "https://laws.e-gov.go.jp/api/1/lawlists/1"
E_GOV_DATA_URL = "https://laws.e-gov.go.jp/api/1/lawdata/{}"

LAW_LIST = [
    {"name": "薬剤師法",                    "search_name": "薬剤師法"},
    {"name": "医薬品医療機器等法（薬機法）", "search_name": "医薬品、医療機器等の品質、有効性及び安全性の確保等に関する法律"},
    {"name": "毒物及び劇物取締法",           "search_name": "毒物及び劇物取締法"},
    {"name": "麻薬及び向精神薬取締法",       "search_name": "麻薬及び向精神薬取締法"},
    {"name": "覚醒剤取締法",                "search_name": "覚醒剤取締法"},
    {"name": "大麻草の栽培の規制に関する法律","search_name": "大麻草の栽培の規制に関する法律"},
    {"name": "あへん法",                    "search_name": "あへん法"},
    {"name": "医療法",                      "search_name": "医療法"},
    {"name": "医師法",                      "search_name": "医師法"},
    {"name": "保健師助産師看護師法",          "search_name": "保健師助産師看護師法"},
    {"name": "歯科医師法",                  "search_name": "歯科医師法"},
    {"name": "健康保険法",                  "search_name": "健康保険法"},
    {"name": "国民健康保険法",              "search_name": "国民健康保険法"},
    {"name": "高齢者の医療の確保に関する法律","search_name": "高齢者の医療の確保に関する法律"},
    {"name": "介護保険法",                  "search_name": "介護保険法"},
    {"name": "感染症法",                    "search_name": "感染症の予防及び感染症の患者に対する医療に関する法律"},
    {"name": "食品衛生法",                  "search_name": "食品衛生法"},
    {"name": "食品安全基本法",              "search_name": "食品安全基本法"},
    {"name": "健康増進法",                  "search_name": "健康増進法"},
    {"name": "臓器の移植に関する法律",       "search_name": "臓器の移植に関する法律"},
    {"name": "安全な血液製剤の安定供給の確保等に関する法律", "search_name": "安全な血液製剤の安定供給の確保等に関する法律"},
    {"name": "再生医療等の安全性の確保等に関する法律", "search_name": "再生医療等の安全性の確保等に関する法律"},
    {"name": "地域保健法",                  "search_name": "地域保健法"},
    {"name": "精神保健及び精神障害者福祉に関する法律", "search_name": "精神保健及び精神障害者福祉に関する法律"},
    {"name": "難病の患者に対する医療等に関する法律", "search_name": "難病の患者に対する医療等に関する法律"},
    {"name": "検疫法",                      "search_name": "検疫法"},
    {"name": "予防接種法",                  "search_name": "予防接種法"},
    {"name": "がん対策基本法",              "search_name": "がん対策基本法"},
    {"name": "肝炎対策基本法",              "search_name": "肝炎対策基本法"},
    {"name": "アレルギー疾患対策基本法",     "search_name": "アレルギー疾患対策基本法"},
    {"name": "救急救命士法",               "search_name": "救急救命士法"},
    {"name": "臨床研究法",                 "search_name": "臨床研究法"},
    {"name": "死体解剖保存法",             "search_name": "死体解剖保存法"},
    {"name": "個人情報の保護に関する法律",   "search_name": "個人情報の保護に関する法律"},
    {"name": "学校保健安全法",             "search_name": "学校保健安全法"},
    {"name": "労働安全衛生法",             "search_name": "労働安全衛生法"},
    {"name": "労働基準法",                 "search_name": "労働基準法"},
    {"name": "生活保護法",                 "search_name": "生活保護法"},
    {"name": "児童福祉法",                 "search_name": "児童福祉法"},
    {"name": "母子保健法",                 "search_name": "母子保健法"},
    {"name": "母体保護法",                 "search_name": "母体保護法"},
    {"name": "診療放射線技師法",            "search_name": "診療放射線技師法"},
    {"name": "放射性同位元素等の規制に関する法律", "search_name": "放射性同位元素等の規制に関する法律"},
    {"name": "消防法",                     "search_name": "消防法"},
    {"name": "新型インフルエンザ等対策特別措置法", "search_name": "新型インフルエンザ等対策特別措置法"},
    {"name": "学校教育法",                 "search_name": "学校教育法"},
    {"name": "石綿による健康被害の救済に関する法律", "search_name": "石綿による健康被害の救済に関する法律"},
    {"name": "高齢者虐待防止法",            "search_name": "高齢者虐待の防止、高齢者の養護者に対する支援等に関する法律"},
    {"name": "国民健康保険法施行法",         "search_name": "国民健康保険法施行法"},
    {"name": "再生医療を国民が迅速かつ安全に受けられるようにするための施策の総合的な推進に関する法律", "search_name": "再生医療を国民が迅速かつ安全に受けられるようにするための施策の総合的な推進に関する法律"},
    {"name": "社会保険診療報酬支払基金法",   "search_name": "社会保険診療報酬支払基金法"},
    {"name": "水道法",                     "search_name": "水道法"},
    {"name": "地域における医療及び介護の総合的な確保の促進に関する法律", "search_name": "地域における医療及び介護の総合的な確保の促進に関する法律"},
    {"name": "特定B型肝炎ウイルス感染者給付金等の支給に関する特別措置法", "search_name": "特定Ｂ型肝炎ウイルス感染者給付金等の支給に関する特別措置法"},
    {"name": "独立行政法人医薬品医療機器総合機構法", "search_name": "独立行政法人医薬品医療機器総合機構法"},
    {"name": "独立行政法人国立病院機構法",   "search_name": "独立行政法人国立病院機構法"},
    {"name": "刑法",                       "search_name": "刑法"},
    {"name": "民法",                       "search_name": "民法"},
    {"name": "国家公務員共済組合法",         "search_name": "国家公務員共済組合法"},
    {"name": "遺伝子組換え生物等の使用等の規制による生物の多様性の確保に関する法律", "search_name": "遺伝子組換え生物等の使用等の規制による生物の多様性の確保に関する法律"},
]


@app.get("/api/dict")
def get_dict():
    laws = db.get_all_laws()
    meta = db.get_dict_meta()
    return {
        "laws": laws,
        "meta": meta,
        "total": len(laws),
        "fetched": sum(1 for l in laws if not l["error"])
    }


@app.post("/api/dict/fetch")
async def fetch_dict():
    today = get_today_jp()

    async with aiohttp.ClientSession() as session:
        async with session.get(E_GOV_LIST_URL) as resp:
            xml_text = await resp.text()

        root = ET.fromstring(xml_text)
        id_map = {}
        for info in root.findall(".//LawNameListInfo"):
            name_el = info.find("LawName")
            id_el   = info.find("LawId")
            if name_el is not None and id_el is not None:
                id_map[name_el.text] = id_el.text

        db.clear_laws()
        db.set_dict_meta(today)

        results = []
        for law in LAW_LIST:
            law_id = id_map.get(law["search_name"])
            if not law_id:
                law_id = next(
                    (id_map[k] for k in id_map if law["search_name"] in k or k in law["search_name"]),
                    None
                )
            if not law_id:
                db.upsert_law(law["name"], law["search_name"], "", today, error=True,
                              error_msg="法令一覧に見つかりません: " + law["search_name"])
                results.append({"name": law["name"], "ok": False})
                continue

            try:
                url = E_GOV_DATA_URL.format(law_id)
                async with session.get(url) as resp:
                    law_xml = await resp.text()

                law_root = ET.fromstring(law_xml)
                sentences = law_root.findall(".//Sentence")
                if sentences:
                    text = "\n".join(s.text or "" for s in sentences)
                else:
                    text = law_root.findtext(".//LawFullText") or ""

                db.upsert_law(law["name"], law["search_name"], text.strip(), today)
                results.append({"name": law["name"], "ok": True, "chars": len(text)})
            except Exception as e:
                db.upsert_law(law["name"], law["search_name"], "", today,
                              error=True, error_msg=str(e))
                results.append({"name": law["name"], "ok": False, "error": str(e)})

            await asyncio.sleep(0.3)

    return {"dict_date": today, "results": results}


@app.post("/api/dict/manual")
async def upload_manual_law(file: UploadFile = File(...)):
    text = (await file.read()).decode("utf-8", errors="replace")
    name = Path(file.filename).stem
    date_str = get_today_jp()
    db.upsert_law(name, name, text, date_str)
    meta = db.get_dict_meta()
    if not meta.get("dict_date"):
        db.set_dict_meta(date_str)
    return {"name": name, "chars": len(text)}


@app.delete("/api/dict")
def delete_dict():
    db.clear_laws()
    return {"ok": True}


class CheckRequest(BaseModel):
    question: str


@app.post("/api/check")
def create_check(req: CheckRequest):
    meta = db.get_dict_meta()
    dict_date = meta.get("dict_date", "")
    formatted = format_text(req.question)
    job_id = db.create_job(req.question, formatted, dict_date)
    return {"job_id": job_id}


@app.get("/api/check/{job_id}")
def get_check(job_id: int):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    return job


@app.post("/api/batch")
async def batch_check(file: UploadFile = File(...)):
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except Exception:
        text = raw.decode("shift_jis", errors="replace")

    questions = parse_csv(text)
    if not questions:
        raise HTTPException(status_code=400, detail="有効な問題が見つかりません")

    meta = db.get_dict_meta()
    dict_date = meta.get("dict_date", "")
    rows = [(q, format_text(q)) for q in questions]
    job_ids = db.create_jobs_bulk(rows, dict_date)
    return {"job_ids": job_ids, "total": len(job_ids)}


@app.get("/api/batch/status")
def batch_status(ids: str):
    id_list = [int(i) for i in ids.split(",") if i.strip()]
    jobs = db.get_jobs_by_ids(id_list)
    done  = sum(1 for j in jobs if j["status"] == "done")
    error = sum(1 for j in jobs if j["status"] == "error")
    return {
        "jobs": jobs,
        "total": len(jobs),
        "done": done,
        "error": error,
        "pending": len(jobs) - done - error
    }


@app.get("/api/batch/download")
def batch_download(ids: str):
    id_list = [int(i) for i in ids.split(",") if i.strip()]
    jobs = db.get_jobs_by_ids(id_list)
    judge_label = {"ok": "問題なし", "warn": "要注意", "ng": "不適合"}
    header = ["問題番号", "元の問題内容", "整形済み問題内容", "判定", "AIチェック結果", "法令辞書基準日"]
    rows = []
    for i, j in enumerate(jobs, 1):
        rows.append([
            i,
            j["question"],
            j["formatted"] or "",
            judge_label.get(j["judge"] or "", j["status"]),
            j["result"] or "",
            j["dict_date"] or ""
        ])
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(header)
    writer.writerows(rows)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=check_result.csv"}
    )


def format_text(text: str) -> str:
    text = text.replace("\\n", "\n")
    text = re.sub(r"\*\*(.+?)\*\*", r"【\1】", text)
    text = re.sub(r"\*(.+?)\*",     r"《\1》", text)
    return text


def parse_csv(text: str) -> list:
    questions = []
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if not row:
            continue
        cell = row[0].strip()
        if not cell or cell in ("Completion result", "text"):
            continue
        try:
            parsed = json.loads(cell)
            if isinstance(parsed, dict) and "text" in parsed:
                cell = parsed["text"]
        except Exception:
            pass
        cell = cell.replace("\\n", "\n").strip()
        if cell:
            questions.append(cell)
    return questions
