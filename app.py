# app.py
# LINE BOT + NOTION SEARCH (FINAL REAL VERSION)
# ใช้งานกับฐานข้อมูลของคุณโดยตรง

import os
import json
import requests
from flask import Flask, request

app = Flask(__name__)

# =========================
# ENV
# =========================
LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")   # PERSON TABLE

# =========================
# HEADER
# =========================
LINE_HEADERS = {
    "Authorization": f"Bearer {LINE_TOKEN}",
    "Content-Type": "application/json"
}

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# =========================
# BASIC
# =========================
@app.route("/", methods=["GET"])
def home():
    return "LINE BOT RUNNING"

# =========================
# LINE REPLY
# =========================
def reply(reply_token, text):
    url = "https://api.line.me/v2/bot/message/reply"
    data = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text[:4900]}]
    }
    requests.post(url, headers=LINE_HEADERS, json=data, timeout=20)

# =========================
# NOTION HELPERS
# =========================
def notion_post(url, payload):
    r = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=30)
    return r.json()

def notion_get(url):
    r = requests.get(url, headers=NOTION_HEADERS, timeout=30)
    return r.json()

# -------------------------
# text readers
# -------------------------
def rich(prop):
    try:
        return "".join([x["plain_text"] for x in prop.get("rich_text", [])]).strip()
    except:
        return ""

def title(prop):
    try:
        return "".join([x["plain_text"] for x in prop.get("title", [])]).strip()
    except:
        return ""

def selectv(prop):
    try:
        return prop["select"]["name"]
    except:
        return ""

def multiselect(prop):
    try:
        return ", ".join([x["name"] for x in prop["multi_select"]])
    except:
        return ""

def datev(prop):
    try:
        return prop["date"]["start"]
    except:
        return ""

def numberv(prop):
    try:
        n = prop["number"]
        if n is None:
            return ""
        return str(n)
    except:
        return ""

# -------------------------
# relation title
# -------------------------
def get_page_title(page_id):
    try:
        url = f"https://api.notion.com/v1/pages/{page_id}"
        data = notion_get(url)
        props = data["properties"]

        for k, v in props.items():
            if v["type"] == "title":
                return title(v)

        return page_id[:8]
    except:
        return ""

def relation(prop):
    try:
        arr = prop["relation"]
        if not arr:
            return ""

        names = []
        for r in arr:
            names.append(get_page_title(r["id"]))
        return ", ".join(names)
    except:
        return ""

# -------------------------
# rollup real reader
# -------------------------
def rollup(prop):
    try:
        ru = prop["rollup"]

        if ru["type"] == "array":
            vals = []
            for x in ru["array"]:
                t = x["type"]

                if t == "title":
                    vals.append(title(x))
                elif t == "rich_text":
                    vals.append(rich(x))
                elif t == "number":
                    vals.append(numberv(x))
                elif t == "select":
                    vals.append(selectv(x))
                elif t == "multi_select":
                    vals.append(multiselect(x))
                elif t == "relation":
                    vals.append(relation(x))
            return ", ".join([v for v in vals if v])

        if ru["type"] == "number":
            return str(ru["number"])

        return ""
    except:
        return ""

# -------------------------
# universal reader
# -------------------------
def val(props, name):
    if name not in props:
        return ""

    p = props[name]
    t = p["type"]

    if t == "title":
        return title(p)

    if t == "rich_text":
        return rich(p)

    if t == "number":
        return numberv(p)

    if t == "select":
        return selectv(p)

    if t == "multi_select":
        return multiselect(p)

    if t == "date":
        return datev(p)

    if t == "relation":
        return relation(p)

    if t == "rollup":
        return rollup(p)

    if t == "formula":
        try:
            f = p["formula"]
            if f["type"] == "string":
                return f["string"] or ""
            if f["type"] == "number":
                return str(f["number"])
        except:
            return ""

    return ""

# =========================
# SEARCH
# =========================
def search_notion(keyword):

    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

    all_rows = []
    cursor = None

    while True:

        payload = {
            "page_size": 100
        }

        if cursor:
            payload["start_cursor"] = cursor

        data = notion_post(url, payload)

        rows = data.get("results", [])
        all_rows.extend(rows)

        if data.get("has_more"):
            cursor = data.get("next_cursor")
        else:
            break

    # keyword filter
    found = []

    kw = keyword.strip().lower()

    for row in all_rows:
        props = row["properties"]

        text_pool = [
            val(props, "เลขบัตรประชาชน"),
            val(props, "ชื่อ"),
            val(props, "เครือข่าย"),
            val(props, "Case id"),
            val(props, "จังหวัด"),
            val(props, "จังหวัดตามบัตร"),
            val(props, "สถานะ"),
            val(props, "บทบาทในเครือข่าย"),
            val(props, "ชื่อเครือข่ายหลัก"),
            val(props, "หน่วย(Auto)"),
            val(props, "หน่วย(เชื่อมจริง)")
        ]

        big = " | ".join(text_pool).lower()

        if kw in big:
            found.append(row)

    return found

# =========================
# FORMAT
# =========================
def render(rows):

    if not rows:
        return (
            "❌ ไม่พบข้อมูล\n\n"
            "ค้นหาได้จาก:\n"
            "• เลขบัตร\n"
            "• ชื่อ\n"
            "• จังหวัด\n"
            "• สถานะ\n"
            "• Case ID\n"
            "• เครือข่าย"
        )

    msg = f"📊 พบ {len(rows)} รายการ\n\n"

    for i, row in enumerate(rows[:30], start=1):

        p = row["properties"]

        cid = val(p, "เลขบัตรประชาชน")
        name = val(p, "ชื่อ")
        network = val(p, "ชื่อเครือข่ายหลัก")
        if not network:
            network = val(p, "เครือข่าย")

        network_code = val(p, "เครือข่าย")

        caseid = val(p, "Case id")

        province = val(p, "จังหวัด")
        if not province:
            province = val(p, "จังหวัดตามบัตร")

        addr = val(p, "ที่อยู่ตามบัตรประชาชน")

        status = val(p, "สถานะ")

        role = val(p, "บทบาทในเครือข่าย")

        unit = val(p, "หน่วย(เชื่อมจริง)")
        if not unit:
            unit = val(p, "หน่วย(Auto)")

        post = val(p, "ที่อยู่ไปรษณีย์(Auto)")

        sent = val(p, "สถานะการส่ง")

        send_date = val(p, "วันที่ส่ง")

        msg += (
            f"📌 รายการ {i}\n"
            f"👤 ชื่อ: {name}\n"
            f"🪪 เลขบัตร: {cid}\n"
            f"🌐 เครือข่ายหลัก: {network}\n"
            f"🧩 เครือข่าย: {network_code}\n"
            f"📁 Case ID: {caseid}\n"
            f"📍 จังหวัด: {province}\n"
            f"🏠 ที่อยู่: {addr}\n"
            f"🎯 สถานะ: {status}\n"
            f"🏷 บทบาท: {role}\n"
            f"👮 หน่วยรับผิดชอบ: {unit}\n"
            f"📮 ไปรษณีย์: {post}\n"
            f"🚚 สถานะการส่ง: {sent}\n"
            f"📅 วันที่ส่ง: {send_date}\n"
            f"\n--------------------\n\n"
        )

    msg += (
        "🔎 ค้นหาต่อได้จาก:\n"
        "• เลขบัตร\n"
        "• ชื่อ\n"
        "• จังหวัด\n"
        "• สถานะ\n"
        "• Case ID\n"
        "• เครือข่าย"
    )

    return msg[:4900]

# =========================
# WEBHOOK
# =========================
@app.route("/webhook", methods=["POST"])
def webhook():

    body = request.get_json()

    try:
        events = body["events"]

        for e in events:

            if e["type"] != "message":
                continue

            if e["message"]["type"] != "text":
                continue

            text = e["message"]["text"].strip()
            reply_token = e["replyToken"]

            rows = search_notion(text)
            msg = render(rows)

            reply(reply_token, msg)

    except Exception as ex:
        print(ex)

    return "OK"

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
