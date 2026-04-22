# app.py
# ==========================================
# LINE BOT + NOTION (ULTIMATE FINAL)
# เร็ว / เสถียร / ดึง Relation จริง / Rollup จริง / ใช้งาน Render ได้เลย
# ==========================================

import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==========================================
# ENV
# ==========================================
LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

# ==========================================
# HEADERS
# ==========================================
LINE_HEADERS = {
    "Authorization": f"Bearer {LINE_TOKEN}",
    "Content-Type": "application/json"
}

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# ==========================================
# CACHE
# ==========================================
PAGE_CACHE = {}

# ==========================================
# HOME
# ==========================================
@app.route("/", methods=["GET"])
def home():
    return "BOT RUNNING OK"

# ==========================================
# LINE REPLY
# ==========================================
def reply(reply_token, text):
    try:
        payload = {
            "replyToken": reply_token,
            "messages": [{
                "type": "text",
                "text": text[:4900]
            }]
        }

        requests.post(
            "https://api.line.me/v2/bot/message/reply",
            headers=LINE_HEADERS,
            json=payload,
            timeout=4
        )
    except Exception as e:
        print("LINE ERROR:", e)

# ==========================================
# NOTION API
# ==========================================
def notion_post(url, payload):
    try:
        r = requests.post(
            url,
            headers=NOTION_HEADERS,
            json=payload,
            timeout=7
        )
        return r.json()
    except:
        return {}

def notion_get(url):
    try:
        r = requests.get(
            url,
            headers=NOTION_HEADERS,
            timeout=6
        )
        return r.json()
    except:
        return {}

# ==========================================
# TEXT READERS
# ==========================================
def title(prop):
    try:
        return "".join(x["plain_text"] for x in prop["title"]).strip()
    except:
        return ""

def rich(prop):
    try:
        return "".join(x["plain_text"] for x in prop["rich_text"]).strip()
    except:
        return ""

def selectv(prop):
    try:
        return prop["select"]["name"]
    except:
        return ""

def multi(prop):
    try:
        return ", ".join(x["name"] for x in prop["multi_select"])
    except:
        return ""

def numberv(prop):
    try:
        n = prop["number"]
        return "" if n is None else str(n)
    except:
        return ""

def datev(prop):
    try:
        return prop["date"]["start"]
    except:
        return ""

# ==========================================
# PAGE TITLE (Relation Page)
# ==========================================
def get_page_title(page_id):

    if page_id in PAGE_CACHE:
        return PAGE_CACHE[page_id]

    try:
        data = notion_get(f"https://api.notion.com/v1/pages/{page_id}")
        props = data["properties"]

        txt = ""

        for k, v in props.items():
            if v["type"] == "title":
                txt = title(v)
                break

        PAGE_CACHE[page_id] = txt
        return txt

    except:
        return ""

# ==========================================
# RELATION
# ==========================================
def relation(prop):
    try:
        arr = prop["relation"]

        vals = []
        for x in arr[:20]:
            t = get_page_title(x["id"])
            if t:
                vals.append(t)

        return ", ".join(vals)
    except:
        return ""

# ==========================================
# ROLLUP
# ==========================================
def rollup(prop):
    try:
        ru = prop["rollup"]

        if ru["type"] == "number":
            return str(ru["number"])

        if ru["type"] == "array":

            vals = []

            for x in ru["array"]:

                t = x["type"]

                if t == "title":
                    vals.append(title(x))

                elif t == "rich_text":
                    vals.append(rich(x))

                elif t == "select":
                    vals.append(selectv(x))

                elif t == "number":
                    vals.append(numberv(x))

                elif t == "date":
                    vals.append(datev(x))

            return ", ".join(v for v in vals if v)

        return ""

    except:
        return ""

# ==========================================
# UNIVERSAL READ
# ==========================================
def val(props, key):

    if key not in props:
        return ""

    p = props[key]
    t = p["type"]

    if t == "title":
        return title(p)

    if t == "rich_text":
        return rich(p)

    if t == "select":
        return selectv(p)

    if t == "multi_select":
        return multi(p)

    if t == "number":
        return numberv(p)

    if t == "date":
        return datev(p)

    if t == "relation":
        return relation(p)

    if t == "rollup":
        return rollup(p)

    return ""

# ==========================================
# SEARCH
# ==========================================
def search_notion(keyword):

    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

    payload = {
        "page_size": 25,
        "filter": {
            "or": [

                {
                    "property": "ชื่อ",
                    "title": {
                        "contains": keyword
                    }
                },

                {
                    "property": "เลขบัตรประชาชน",
                    "rich_text": {
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
                    "property": "ชื่อเครือข่ายหลัก",
                    "rich_text": {
                        "contains": keyword
                    }
                },

                {
                    "property": "จังหวัด",
                    "relation": {
                        "contains": keyword
                    }
                },

                {
                    "property": "สถานะ",
                    "select": {
                        "equals": keyword
                    }
                }

            ]
        }
    }

    data = notion_post(url, payload)
    return data.get("results", [])

# ==========================================
# RENDER
# ==========================================
def render(rows):

    if not rows:
        return (
            "❌ ไม่พบข้อมูล\n\n"
            "ค้นหาได้จาก:\n"
            "• ชื่อ\n"
            "• เลขบัตร\n"
            "• จังหวัด\n"
            "• สถานะ\n"
            "• Case ID\n"
            "• เครือข่าย"
        )

    msg = f"📊 พบ {len(rows)} รายการ\n\n"

    for i, row in enumerate(rows, start=1):

        p = row["properties"]

        name = val(p, "ชื่อ")
        cid = val(p, "เลขบัตรประชาชน")
        netmain = val(p, "ชื่อเครือข่ายหลัก")
        network = val(p, "เครือข่าย")
        caseid = val(p, "Case id")
        province = val(p, "จังหวัด")
        addr = val(p, "ที่อยู่ตามบัตรประชาชน")
        status = val(p, "สถานะ")
        ship = val(p, "สถานะการส่ง")
        unit = val(p, "หน่วยรับผิดชอบ")
        unit2 = val(p, "หน่วย(ย้อนหลัง)")
        post = val(p, "ที่อยู่ไปรษณีย์(Auto)")
        send_date = val(p, "วันที่ส่ง")
        role = val(p, "บทบาทในเครือข่าย")

        msg += (
            f"📌 รายการ {i}\n"
            f"👤 ชื่อ: {name}\n"
            f"🪪 เลขบัตร: {cid}\n"
            f"🌐 เครือข่ายหลัก: {netmain}\n"
            f"🧩 เครือข่าย: {network}\n"
            f"📁 Case ID: {caseid}\n"
            f"📍 จังหวัด: {province}\n"
            f"🏠 ที่อยู่: {addr}\n"
            f"🎯 สถานะ: {status}\n"
            f"🚚 สถานะการส่ง: {ship}\n"
            f"👮 หน่วยรับผิดชอบ: {unit}\n"
            f"🚓 หน่วยย้อนหลัง: {unit2}\n"
            f"📮 ไปรษณีย์: {post}\n"
            f"📅 วันที่ส่ง: {send_date}\n"
            f"🏷 บทบาท: {role}\n"
            f"\n----------------------\n\n"
        )

    return msg[:4900]

# ==========================================
# WEBHOOK
# ==========================================
@app.route("/webhook", methods=["POST"])
def webhook():

    try:
        body = request.get_json()
        events = body.get("events", [])

        for event in events:

            if event["type"] != "message":
                continue

            if event["message"]["type"] != "text":
                continue

            keyword = event["message"]["text"].strip()
            reply_token = event["replyToken"]

            print("SEARCH:", keyword)

            rows = search_notion(keyword)
            msg = render(rows)

            reply(reply_token, msg)

    except Exception as e:
        print("WEBHOOK ERROR:", e)

    return jsonify({"status": "ok"})

# ==========================================
# RUN
# ==========================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
