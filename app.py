# app.py
# FAST VERSION / RENDER FREE / LINE + NOTION
# เร็วจริง ใช้งานได้เลย

import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# =========================
# ENV
# =========================
LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

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
    return "BOT RUNNING"

# =========================
# LINE REPLY
# =========================
def reply_message(reply_token, text):
    url = "https://api.line.me/v2/bot/message/reply"

    payload = {
        "replyToken": reply_token,
        "messages": [
            {
                "type": "text",
                "text": text[:4900]
            }
        ]
    }

    requests.post(url, headers=LINE_HEADERS, json=payload, timeout=10)

# =========================
# NOTION HELPERS
# =========================
def notion_post(url, payload):
    r = requests.post(
        url,
        headers=NOTION_HEADERS,
        json=payload,
        timeout=15
    )
    return r.json()

def get_title(prop):
    try:
        return "".join([x["plain_text"] for x in prop["title"]]).strip()
    except:
        return ""

def get_rich(prop):
    try:
        return "".join([x["plain_text"] for x in prop["rich_text"]]).strip()
    except:
        return ""

def get_select(prop):
    try:
        return prop["select"]["name"]
    except:
        return ""

def get_relation_simple(prop):
    try:
        arr = prop["relation"]
        if len(arr) > 0:
            return arr[0]["id"][:8]
        return ""
    except:
        return ""

def get_value(props, key):

    if key not in props:
        return ""

    p = props[key]
    t = p["type"]

    if t == "title":
        return get_title(p)

    if t == "rich_text":
        return get_rich(p)

    if t == "select":
        return get_select(p)

    if t == "relation":
        return get_relation_simple(p)

    return ""

# =========================
# FAST SEARCH
# =========================
def search_person(keyword):

    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

    payload = {
        "page_size": 10,
        "filter": {
            "or": [

                {
                    "property": "เลขบัตรประชาชน",
                    "rich_text": {
                        "contains": keyword
                    }
                },

                {
                    "property": "ชื่อ",
                    "title": {
                        "contains": keyword
                    }
                },

                {
                    "property": "Case id",
                    "rich_text": {
                        "contains": keyword
                    }
                },

                {
                    "property": "ที่อยู่ตามบัตรประชาชน",
                    "rich_text": {
                        "contains": keyword
                    }
                }

            ]
        }
    }

    data = notion_post(url, payload)
    return data.get("results", [])

# =========================
# FORMAT RESULT
# =========================
def render(rows):

    if not rows:
        return (
            "❌ ไม่พบข้อมูล\n\n"
            "ค้นหาได้จาก:\n"
            "• เลขบัตรประชาชน\n"
            "• ชื่อ\n"
            "• Case ID\n"
            "• ที่อยู่"
        )

    msg = f"📊 พบ {len(rows)} รายการ\n\n"

    for i, row in enumerate(rows, start=1):

        p = row["properties"]

        cid = get_value(p, "เลขบัตรประชาชน")
        name = get_value(p, "ชื่อ")
        caseid = get_value(p, "Case id")
        addr = get_value(p, "ที่อยู่ตามบัตรประชาชน")
        status = get_value(p, "สถานะ")
        network = get_value(p, "เครือข่าย")
        province = get_value(p, "จังหวัด")
        role = get_value(p, "บทบาทในเครือข่าย")

        msg += (
            f"📌 รายการ {i}\n"
            f"👤 ชื่อ: {name}\n"
            f"🪪 เลขบัตร: {cid}\n"
            f"🌐 เครือข่าย: {network}\n"
            f"📁 Case ID: {caseid}\n"
            f"📍 จังหวัด: {province}\n"
            f"🏠 ที่อยู่: {addr}\n"
            f"🎯 สถานะ: {status}\n"
            f"🏷 บทบาท: {role}\n"
            f"\n-----------------\n\n"
        )

    msg += (
        "🔎 ค้นหาต่อได้จาก:\n"
        "• เลขบัตร\n"
        "• ชื่อ\n"
        "• Case ID\n"
        "• ที่อยู่"
    )

    return msg[:4900]

# =========================
# WEBHOOK
# =========================
@app.route("/webhook", methods=["POST"])
def webhook():

    body = request.get_json()

    try:
        events = body.get("events", [])

        for event in events:

            if event["type"] != "message":
                continue

            if event["message"]["type"] != "text":
                continue

            keyword = event["message"]["text"].strip()
            reply_token = event["replyToken"]

            rows = search_person(keyword)
            text = render(rows)

            reply_message(reply_token, text)

    except Exception as e:
        print("ERROR:", e)

    return jsonify({"status": "ok"})

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
