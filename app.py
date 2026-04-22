# app.py
# FINAL REAL VERSION - LINE + NOTION FAST SEARCH
# ใช้งานกับ Render ได้ทันที

import os
import requests
from flask import Flask, request

app = Flask(__name__)

# =========================
# ENV
# =========================
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "").strip()
DATABASE_ID = os.getenv("DATABASE_ID", "").strip()
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()

NOTION_VERSION = "2022-06-28"

# =========================
# ROOT
# =========================
@app.route("/", methods=["GET"])
def home():
    return "BPP414 DrugNetwork Bot Running"

# =========================
# WEBHOOK
# =========================
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

            user_text = event["message"]["text"].strip()
            reply_token = event["replyToken"]

            print("SEARCH:", user_text)

            result = search_notion(user_text)

            reply_message(reply_token, result)

        return "OK", 200

    except Exception as e:
        print("WEBHOOK ERROR:", str(e))
        return "ERROR", 200


# =========================
# SEARCH NOTION
# =========================
def search_notion(keyword):

    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }

    payload = {
        "page_size": 15
    }

    r = requests.post(url, headers=headers, json=payload, timeout=30)

    if r.status_code != 200:
        print("NOTION ERROR:", r.text)
        return "❌ ดึงข้อมูล Notion ไม่สำเร็จ"

    data = r.json()
    rows = data.get("results", [])

    found = []

    keyword_lower = keyword.lower()

    for row in rows:
        props = row.get("properties", {})
        text_blob = flatten_properties(props).lower()

        if keyword_lower in text_blob:
            found.append(format_result(props))

    if not found:
        return f"❌ ไม่พบข้อมูล: {keyword}"

    return f"📊 พบ {len(found)} รายการ\n\n" + "\n\n------------------\n\n".join(found[:10])


# =========================
# READ ALL PROPERTY TYPES
# =========================
def flatten_properties(props):
    values = []

    for k, v in props.items():
        values.append(read_property(v))

    return " ".join(values)


def read_property(p):
    t = p.get("type")

    try:
        if t == "title":
            return "".join([x["plain_text"] for x in p["title"]])

        if t == "rich_text":
            return "".join([x["plain_text"] for x in p["rich_text"]])

        if t == "number":
            return str(p["number"] or "")

        if t == "select":
            return p["select"]["name"] if p["select"] else ""

        if t == "multi_select":
            return " ".join([x["name"] for x in p["multi_select"]])

        if t == "status":
            return p["status"]["name"] if p["status"] else ""

        if t == "date":
            return p["date"]["start"] if p["date"] else ""

        if t == "checkbox":
            return "true" if p["checkbox"] else "false"

        if t == "phone_number":
            return p["phone_number"] or ""

        if t == "email":
            return p["email"] or ""

        if t == "url":
            return p["url"] or ""

        if t == "relation":
            ids = p["relation"]
            return " ".join([x["id"] for x in ids])

        if t == "rollup":
            ru = p["rollup"]

            if ru["type"] == "number":
                return str(ru["number"])

            if ru["type"] == "date":
                return str(ru["date"])

            if ru["type"] == "array":
                arr = ru["array"]
                vals = []

                for item in arr:
                    vals.append(read_property(item))

                return " ".join(vals)

        if t == "formula":
            f = p["formula"]

            if f["type"] == "string":
                return f["string"] or ""

            if f["type"] == "number":
                return str(f["number"] or "")

            if f["type"] == "boolean":
                return str(f["boolean"])

        return ""

    except:
        return ""


# =========================
# FORMAT RESULT
# =========================
def format_result(props):

    def val(name):
        if name in props:
            return read_property(props[name])
        return ""

    msg = []

    msg.append(f"👤 ชื่อ: {val('ชื่อ')}")
    msg.append(f"🆔 เลขบัตร: {val('เลขบัตรประชาชน')}")
    msg.append(f"🌐 เครือข่าย: {val('เครือข่าย(Auto)') or val('เครือข่าย')}")
    msg.append(f"📁 Case ID: {val('Case id')}")
    msg.append(f"📍 จังหวัด: {val('จังหวัด')}")
    msg.append(f"🏠 ที่อยู่: {val('ที่อยู่ตามบัตรประชาชน')}")
    msg.append(f"🎯 สถานะ: {val('สถานะ')}")
    msg.append(f"👮 หน่วยรับผิดชอบ: {val('หน่วย(Auto)') or val('หน่วย(เชื่อมจริง)')}")
    msg.append(f"📮 ไปรษณีย์: {val('ที่อยู่ไปรษณีย์(Auto)')}")
    msg.append(f"📅 วันที่ส่ง: {val('วันที่ส่ง')}")

    return "\n".join(msg)


# =========================
# REPLY LINE
# =========================
def reply_message(reply_token, text):

    headers = {
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    body = {
        "replyToken": reply_token,
        "messages": [
            {
                "type": "text",
                "text": text[:4900]
            }
        ]
    }

    r = requests.post(
        "https://api.line.me/v2/bot/message/reply",
        headers=headers,
        json=body,
        timeout=20
    )

    print("LINE REPLY:", r.status_code, r.text)


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
