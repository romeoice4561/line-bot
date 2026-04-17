from flask import Flask, request
import requests
import os
import json
from collections import Counter

app = Flask(__name__)

# =========================
# ENV
# =========================
LINE_TOKEN = os.getenv("LINE_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

LINE_URL = "https://api.line.me/v2/bot/message/reply"
NOTION_VERSION = "2022-06-28"

# =========================
# HOME
# =========================
@app.route("/", methods=["GET"])
def home():
    return "SMART BOT RUNNING"

# =========================
# LINE REPLY
# =========================
def reply(reply_token, text):
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

# =========================
# GET NOTION DATA ALL PAGE
# =========================
def get_rows():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }

    rows = []
    has_more = True
    cursor = None

    while has_more:
        payload = {}

        if cursor:
            payload["start_cursor"] = cursor

        r = requests.post(url, headers=headers, json=payload, timeout=20)
        data = r.json()

        rows.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        cursor = data.get("next_cursor")

    return rows

# =========================
# READ NOTION VALUE
# =========================
def get_value(prop):
    t = prop["type"]

    try:
        if t == "title":
            return "".join([x["plain_text"] for x in prop["title"]])

        if t == "rich_text":
            return "".join([x["plain_text"] for x in prop["rich_text"]])

        if t == "number":
            return str(prop["number"]) if prop["number"] else ""

        if t == "select":
            return prop["select"]["name"] if prop["select"] else ""

        if t == "multi_select":
            return ", ".join([x["name"] for x in prop["multi_select"]])

        if t == "status":
            return prop["status"]["name"] if prop["status"] else ""

        if t == "date":
            return prop["date"]["start"] if prop["date"] else ""

        if t == "checkbox":
            return "ใช่" if prop["checkbox"] else "ไม่"

        if t == "relation":
            return f"{len(prop['relation'])} รายการ" if prop["relation"] else ""

        if t == "formula":
            f = prop["formula"]
            if f["type"] == "string":
                return f["string"] or ""
            if f["type"] == "number":
                return str(f["number"]) if f["number"] else ""

        if t == "rollup":
            r = prop["rollup"]

            if r["type"] == "number":
                return str(r["number"]) if r["number"] else ""

            if r["type"] == "array":
                vals = []
                for x in r["array"]:
                    vals.append(get_value(x))
                return ", ".join([v for v in vals if v])

        return ""

    except:
        return ""

# =========================
# PARSE
# =========================
def parse(item):
    props = item["properties"]
    row = {}

    for k in props:
        row[k] = get_value(props[k])

    return row

# =========================
# PICK FIELD
# =========================
def pick(row, arr):
    for x in arr:
        if x in row and row[x]:
            return row[x]
    return ""

# =========================
# FORMAT PERSON
# =========================
def show_person(row, i):
    return f"""
📌 รายการ {i}

👤 ชื่อ: {pick(row,['ชื่อ','ชื่อสกุล'])}
🆔 เลขบัตร: {pick(row,['เลขบัตรประชาชน'])}
🌐 เครือข่ายหลัก: {pick(row,['เครือข่ายหลัก'])}
🕸️ เครือข่าย: {pick(row,['เครือข่าย'])}
📁 Case ID: {pick(row,['Case ID','Case id'])}
📍 จังหวัด: {pick(row,['จังหวัด'])}
🏠 ที่อยู่: {pick(row,['ที่อยู่ตามบัตรประชาชน','ที่อยู่'])}
🎯 สถานะ: {pick(row,['สถานะ'])}
📤 สถานะการส่ง: {pick(row,['สถานะการส่ง'])}
👮 หน่วยรับผิดชอบ: {pick(row,['หน่วย'])}
📮 ไปรษณีย์: {pick(row,['ไปรษณีย์'])}
📅 วันที่ส่ง: {pick(row,['วันที่ส่ง'])}
🏷️ บทบาท: {pick(row,['บทบาท'])}

-------------------------
"""

# =========================
# SEARCH
# =========================
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
        return "❌ ไม่พบข้อมูล"

    text = f"📊 พบ {len(found)} รายการ\n"

    for i, row in enumerate(found[:20], 1):
        text += show_person(row, i)

    if len(found) > 20:
        text += f"\n⚠️ แสดง 20 จาก {len(found)} รายการ"

    text += """
🔍 ค้นหาต่อได้จาก:
• เลขบัตร
• ชื่อ
• จังหวัด
• สถานะ
• Case ID
• เครือข่าย
"""

    return text

# =========================
# SMART ANALYZE
# =========================
def summary(keyword):
    rows = get_rows()
    found = []

    kw = keyword.lower()

    for item in rows:
        row = parse(item)
        txt = json.dumps(row, ensure_ascii=False).lower()

        if kw in txt:
            found.append(row)

    if not found:
        return "❌ ไม่พบข้อมูล"

    status_counter = Counter()
    unit_counter = Counter()
    net_counter = Counter()

    for row in found:
        status_counter[pick(row,["สถานะ"])] += 1
        unit_counter[pick(row,["หน่วย"])] += 1
        net_counter[pick(row,["เครือข่ายหลัก"])] += 1

    text = f"📈 วิเคราะห์คำค้น: {keyword}\n"
    text += f"📊 พบทั้งหมด {len(found)} รายการ\n\n"

    text += "🎯 สถานะ:\n"
    for k,v in status_counter.items():
        if k:
            text += f"• {k} {v}\n"

    text += "\n👮 หน่วยรับผิดชอบ:\n"
    for k,v in unit_counter.items():
        if k:
            text += f"• {k} {v}\n"

    text += "\n🌐 เครือข่ายหลัก:\n"
    for k,v in net_counter.items():
        if k:
            text += f"• {k} {v}\n"

    text += "\n🔍 พิมพ์ชื่อจังหวัด / หน่วย / สถานะ ต่อได้"

    return text

# =========================
# MENU
# =========================
def menu():
    return """
🤖 ระบบค้นหาอัจฉริยะ

ค้นหาปกติ:
ชุมพร
1840400058473
007/69
ติดตามขยายผล

วิเคราะห์:
สรุป ชุมพร
สรุป สุราษฎร์ธานี
สรุป ถูกจับกุม
สรุป 414
"""

# =========================
# WEBHOOK
# =========================
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json

        for event in data["events"]:
            if event["type"] == "message":
                msg = event["message"]["text"].strip()
                token = event["replyToken"]

                if msg.lower() in ["menu","เมนู","help"]:
                    reply(token, menu())

                elif msg.startswith("สรุป "):
                    key = msg.replace("สรุป ","").strip()
                    reply(token, summary(key))

                else:
                    reply(token, search(msg))

        return "OK"

    except Exception as e:
        return str(e), 500

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
