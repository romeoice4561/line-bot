from flask import Flask, request
import requests
import os
import json
from functools import lru_cache

app = Flask(__name__)

# ==========================================
# ENV
# ==========================================
LINE_TOKEN = os.getenv("LINE_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

NOTION_VERSION = "2022-06-28"
LINE_URL = "https://api.line.me/v2/bot/message/reply"

# ==========================================
# HEADERS
# ==========================================
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json"
}

# ==========================================
# HOME
# ==========================================
@app.route("/", methods=["GET"])
def home():
    return "BOT RUNNING"

# ==========================================
# LINE REPLY
# ==========================================
def reply(reply_token, text):
    try:
        headers = {
            "Authorization": f"Bearer {LINE_TOKEN}",
            "Content-Type": "application/json"
        }

        body = {
            "replyToken": reply_token,
            "messages": [{
                "type": "text",
                "text": text[:4900]
            }]
        }

        requests.post(LINE_URL, headers=headers, json=body, timeout=15)

    except:
        pass

# ==========================================
# CACHE PAGE TITLE
# ==========================================
@lru_cache(maxsize=1000)
def get_page_title(page_id):
    try:
        url = f"https://api.notion.com/v1/pages/{page_id}"

        r = requests.get(url, headers=NOTION_HEADERS, timeout=10)
        data = r.json()

        props = data.get("properties", {})

        for key in props:
            p = props[key]

            if p["type"] == "title":
                arr = p["title"]
                return "".join([x["plain_text"] for x in arr])

        return page_id[:8]

    except:
        return page_id[:8]

# ==========================================
# GET ALL DATA
# ==========================================
def get_rows():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

    rows = []
    has_more = True
    cursor = None

    while has_more:

        payload = {}

        if cursor:
            payload["start_cursor"] = cursor

        r = requests.post(
            url,
            headers=NOTION_HEADERS,
            json=payload,
            timeout=20
        )

        data = r.json()

        rows.extend(data.get("results", []))

        has_more = data.get("has_more", False)
        cursor = data.get("next_cursor")

    return rows

# ==========================================
# READ VALUE
# ==========================================
def get_value(prop):
    t = prop["type"]

    try:
        # -----------------------
        if t == "title":
            return "".join([x["plain_text"] for x in prop["title"]])

        elif t == "rich_text":
            return "".join([x["plain_text"] for x in prop["rich_text"]])

        elif t == "number":
            return str(prop["number"]) if prop["number"] is not None else ""

        elif t == "select":
            return prop["select"]["name"] if prop["select"] else ""

        elif t == "multi_select":
            return ", ".join([x["name"] for x in prop["multi_select"]])

        elif t == "status":
            return prop["status"]["name"] if prop["status"] else ""

        elif t == "date":
            return prop["date"]["start"] if prop["date"] else ""

        elif t == "checkbox":
            return "ใช่" if prop["checkbox"] else "ไม่"

        elif t == "phone_number":
            return prop["phone_number"] or ""

        elif t == "url":
            return prop["url"] or ""

        elif t == "email":
            return prop["email"] or ""

        # ==================================
        # RELATION = อ่านชื่อจริง
        # ==================================
        elif t == "relation":
            arr = prop["relation"]

            names = []

            for item in arr[:10]:
                page_id = item["id"]
                names.append(get_page_title(page_id))

            return ", ".join(names)

        # ==================================
        # FORMULA
        # ==================================
        elif t == "formula":
            f = prop["formula"]

            if f["type"] == "string":
                return f["string"] or ""

            elif f["type"] == "number":
                return str(f["number"]) if f["number"] else ""

            elif f["type"] == "boolean":
                return "ใช่" if f["boolean"] else "ไม่"

        # ==================================
        # ROLLUP
        # ==================================
        elif t == "rollup":
            r = prop["rollup"]

            if r["type"] == "number":
                return str(r["number"]) if r["number"] else ""

            elif r["type"] == "date":
                return r["date"]["start"] if r["date"] else ""

            elif r["type"] == "array":

                vals = []

                for x in r["array"][:20]:
                    vals.append(get_value(x))

                return ", ".join([v for v in vals if v])

        return ""

    except:
        return ""

# ==========================================
# PARSE
# ==========================================
def parse(item):
    props = item["properties"]

    row = {}

    for k in props:
        row[k] = get_value(props[k])

    return row

# ==========================================
# PICK FIELD
# ==========================================
def pick(row, names):
    for n in names:
        if n in row and row[n]:
            return row[n]
    return ""

# ==========================================
# SHOW PERSON
# ==========================================
def show_person(row, i):
    return f"""
📌 รายการ {i}

👤 ชื่อ: {pick(row,['ชื่อ','ชื่อสกุล'])}
🆔 เลขบัตร: {pick(row,['เลขบัตรประชาชน'])}
🌐 เครือข่ายหลัก: {pick(row,['เครือข่ายหลัก'])}
🕸️ เครือข่าย: {pick(row,['เครือข่าย'])}
📁 Case ID: {pick(row,['Case ID','Case id'])}
📍 จังหวัด: {pick(row,['จังหวัด'])}
🏠 ที่อยู่: {pick(row,['ที่อยู่ตามบัตรประชาชน'])}
🎯 สถานะ: {pick(row,['สถานะ'])}
📤 สถานะการส่ง: {pick(row,['สถานะการส่ง'])}
👮 หน่วยรับผิดชอบ: {pick(row,['หน่วย'])}
📮 ไปรษณีย์: {pick(row,['ไปรษณีย์'])}
📅 วันที่ส่ง: {pick(row,['วันที่ส่ง'])}
🏷️ บทบาท: {pick(row,['บทบาท'])}

-------------------------
"""

# ==========================================
# SEARCH
# ==========================================
def search(keyword):
    rows = get_rows()

    found = []

    kw = keyword.lower()

    for item in rows:
        row = parse(item)

        txt = json.dumps(row, ensure_ascii=False).lower()

        if kw in txt:
            found.append(row)

    if not found:
        return """❌ ไม่พบข้อมูล

🔎 ลองค้นหาจาก:
• เลขบัตร
• ชื่อ
• จังหวัด
• สถานะ
• Case ID
• เครือข่าย
"""

    text = f"📊 พบ {len(found)} รายการ\n"

    for i, row in enumerate(found[:20], 1):
        text += show_person(row, i)

    if len(found) > 20:
        text += f"\n⚠️ แสดง 20 จาก {len(found)} รายการ"

    return text[:4900]

# ==========================================
# MENU
# ==========================================
def menu():
    return """
🤖 ระบบค้นหาอ่าน Relation จริง

ค้นหาได้ เช่น

ชุมพร
414
1840400058473
ติดตามขยายผล
007/69
เครือข่ายท่าแซะ
"""

# ==========================================
# WEBHOOK
# ==========================================
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        body = request.json

        for event in body["events"]:

            if event["type"] == "message":

                msg = event["message"]["text"].strip()
                token = event["replyToken"]

                if msg.lower() in ["menu","เมนู","help"]:
                    reply(token, menu())

                else:
                    reply(token, search(msg))

        return "OK"

    except Exception as e:
        return str(e), 500

# ==========================================
# RUN
# ==========================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
