# app.py
# FINAL WORKING VERSION (ใช้ ENV เดิมของคุณ)
# DATABASE_ID
# NOTION_TOKEN
# LINE_TOKEN

import os
import requests
from flask import Flask, request

app = Flask(__name__)

# ===============================
# ENV (ตรงกับ Render ของคุณ)
# ===============================
DATABASE_ID = os.getenv("DATABASE_ID", "").strip()
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "").strip()
LINE_TOKEN = os.getenv("LINE_TOKEN", "").strip()

NOTION_VERSION = "2022-06-28"

# ===============================
# HOME
# ===============================
@app.route("/", methods=["GET"])
def home():
    return "BPP414 BOT RUNNING", 200


# ===============================
# WEBHOOK
# ===============================
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        body = request.get_json(force=True)
        print("WEBHOOK:", body)

        events = body.get("events", [])

        for event in events:

            if event.get("type") != "message":
                continue

            if event["message"]["type"] != "text":
                continue

            keyword = event["message"]["text"].strip()
            reply_token = event["replyToken"]

            print("SEARCH:", keyword)

            result = search_notion(keyword)

            reply_line(reply_token, result)

        return "OK", 200

    except Exception as e:
        print("WEBHOOK ERROR:", str(e))
        return "OK", 200


# ===============================
# SEARCH NOTION
# ===============================
def search_notion(keyword):

    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }

    payload = {
        "page_size": 30
    }

    r = requests.post(url, headers=headers, json=payload, timeout=30)

    if r.status_code != 200:
        print("NOTION ERROR:", r.text)
        return "❌ เชื่อม Notion ไม่สำเร็จ"

    data = r.json()
    rows = data.get("results", [])

    found = []

    for row in rows:
        props = row.get("properties", {})
        text_all = all_text(props).lower()

        if keyword.lower() in text_all:
            found.append(format_row(props))

    if not found:
        return f"❌ ไม่พบข้อมูล {keyword}"

    return f"📊 พบ {len(found)} รายการ\n\n" + "\n\n------------------\n\n".join(found[:10])


# ===============================
# รวมข้อความทุกคอลัมน์
# ===============================
def all_text(props):
    arr = []

    for k, v in props.items():
        arr.append(read_prop(v))

    return " ".join(arr)


# ===============================
# อ่าน property ทุกชนิด
# ===============================
def read_prop(p):

    try:
        t = p["type"]

        if t == "title":
            return "".join(x["plain_text"] for x in p["title"])

        if t == "rich_text":
            return "".join(x["plain_text"] for x in p["rich_text"])

        if t == "number":
            return str(p["number"] or "")

        if t == "select":
            return p["select"]["name"] if p["select"] else ""

        if t == "multi_select":
            return " ".join(x["name"] for x in p["multi_select"])

        if t == "status":
            return p["status"]["name"] if p["status"] else ""

        if t == "date":
            return p["date"]["start"] if p["date"] else ""

        if t == "relation":
            return " ".join(x["id"] for x in p["relation"])

        if t == "formula":
            f = p["formula"]

            if f["type"] == "string":
                return f["string"] or ""

            if f["type"] == "number":
                return str(f["number"] or "")

        if t == "rollup":
            ru = p["rollup"]

            if ru["type"] == "number":
                return str(ru["number"] or "")

            if ru["type"] == "array":
                vals = []
                for x in ru["array"]:
                    vals.append(read_prop(x))
                return " ".join(vals)

        return ""

    except:
        return ""


# ===============================
# จัดข้อความแสดงผล
# ===============================
def format_row(props):

    def val(name):
        if name in props:
            return read_prop(props[name])
        return ""

    lines = []

    lines.append(f"👤 ชื่อ: {val('ชื่อ')}")
    lines.append(f"🆔 เลขบัตร: {val('เลขบัตรประชาชน')}")
    lines.append(f"🌐 เครือข่าย: {val('เครือข่าย(Auto)') or val('เครือข่าย')}")
    lines.append(f"📁 Case ID: {val('Case id')}")
    lines.append(f"📍 จังหวัด: {val('จังหวัด')}")
    lines.append(f"🏠 ที่อยู่: {val('ที่อยู่ตามบัตรประชาชน')}")
    lines.append(f"🎯 สถานะ: {val('สถานะ')}")
    lines.append(f"👮 หน่วย: {val('หน่วย(Auto)') or val('หน่วย(เชื่อมจริง)')}")
    lines.append(f"📮 ไปรษณีย์: {val('ที่อยู่ไปรษณีย์(Auto)')}")
    lines.append(f"📅 วันที่ส่ง: {val('วันที่ส่ง')}")

    return "\n".join(lines)


# ===============================
# REPLY LINE
# ===============================
def reply_line(reply_token, text):

    url = "https://api.line.me/v2/bot/message/reply"

    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "replyToken": reply_token,
        "messages": [
            {
                "type": "text",
                "text": text[:4900]
            }
        ]
    }

    r = requests.post(url, headers=headers, json=payload, timeout=15)

    print("LINE REPLY:", r.status_code, r.text)


# ===============================
# MAIN
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
