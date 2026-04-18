from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

# ===============================
# ENV (Render Variables)
# ===============================
LINE_TOKEN = os.getenv("LINE_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"
NOTION_URL = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

# ===============================
# HOME
# ===============================
@app.route("/", methods=["GET"])
def home():
    return "BOT RUNNING FAST"

# ===============================
# LINE REPLY
# ===============================
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

    try:
        requests.post(LINE_REPLY_URL, headers=headers, json=body, timeout=10)
    except:
        pass

# ===============================
# NOTION QUERY (เร็วพิเศษ)
# ===============================
def notion_query():
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    payload = {
        "page_size": 50
    }

    try:
        r = requests.post(NOTION_URL, headers=headers, json=payload, timeout=10)
        data = r.json()
        return data.get("results", [])
    except:
        return []

# ===============================
# READ VALUE
# ===============================
def get_value(prop):
    try:
        t = prop["type"]

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

        if t == "relation":
            return f"{len(prop['relation'])} รายการ"

        return ""

    except:
        return ""

# ===============================
# PARSE ROW
# ===============================
def parse(item):
    row = {}

    for k, v in item["properties"].items():
        row[k] = get_value(v)

    return row

# ===============================
# PICK FIELD
# ===============================
def pick(row, names):
    for n in names:
        if n in row and row[n]:
            return row[n]
    return ""

# ===============================
# SHOW PERSON
# ===============================
def person_text(row, i):
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

# ===============================
# SEARCH
# ===============================
def search(keyword):
    rows = notion_query()

    if not rows:
        return "❌ ดึงข้อมูล Notion ไม่สำเร็จ"

    kw = keyword.lower()
    found = []

    for item in rows:
        row = parse(item)
        txt = json.dumps(row, ensure_ascii=False).lower()

        if kw in txt:
            found.append(row)

    if not found:
        return """❌ ไม่พบข้อมูล

🔍 ค้นหาได้จาก:
• เลขบัตร
• ชื่อ
• จังหวัด
• สถานะ
• Case ID
• เครือข่าย"""

    text = f"📊 พบ {len(found)} รายการ\n"

    for i, row in enumerate(found[:20], 1):
        text += person_text(row, i)

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

# ===============================
# MENU
# ===============================
def menu():
    return """
🤖 ระบบค้นหาฐานข้อมูล (เร็วพิเศษ)

พิมพ์ค้นหาได้ทันที เช่น

ชุมพร
สุราษฎร์ธานี
1840400058473
007/69
ติดตามขยายผล
ท่าแซะ
"""

# ===============================
# WEBHOOK
# ===============================
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        body = request.json

        for event in body["events"]:
            if event["type"] == "message":
                msg = event["message"]["text"].strip()
                token = event["replyToken"]

                if msg.lower() in ["menu", "เมนู", "help"]:
                    reply(token, menu())
                else:
                    reply(token, search(msg))

        return "OK"

    except Exception as e:
        return str(e), 500

# ===============================
# RUN
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
