from flask import Flask, request
import requests
import os

app = Flask(__name__)

# ==================================================
# ENV (ใส่ใน Render Environment เท่านั้น)
# ==================================================
LINE_TOKEN = os.getenv("LINE_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

# ==================================================
# LINE REPLY
# ==================================================
def reply(reply_token, text):
    url = "https://api.line.me/v2/bot/message/reply"

    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }

    body = {
        "replyToken": reply_token,
        "messages": [
            {
                "type": "text",
                "text": text[:5000]
            }
        ]
    }

    requests.post(url, headers=headers, json=body)

# ==================================================
# GET NOTION DATA
# ==================================================
def get_notion_data():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    res = requests.post(url, headers=headers)

    if res.status_code != 200:
        print("NOTION ERROR:", res.text)
        return []

    return res.json().get("results", [])

# ==================================================
# ดึงชื่อ Page จาก page_id (สำคัญมาก สำหรับ relation)
# ==================================================
def get_page_title(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28"
    }

    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        return page_id

    data = res.json()
    props = data.get("properties", {})

    for k in props:
        p = props[k]

        if p["type"] == "title":
            if p["title"]:
                return p["title"][0]["plain_text"]

    return page_id

# ==================================================
# แปลงค่า Notion ทุกชนิด
# ==================================================
def get_value(prop):
    t = prop["type"]

    # ---------- title ----------
    if t == "title":
        return "".join([x["plain_text"] for x in prop["title"]])

    # ---------- rich text ----------
    if t == "rich_text":
        return "".join([x["plain_text"] for x in prop["rich_text"]])

    # ---------- select ----------
    if t == "select":
        return prop["select"]["name"] if prop["select"] else ""

    # ---------- multi select ----------
    if t == "multi_select":
        return ", ".join([x["name"] for x in prop["multi_select"]])

    # ---------- number ----------
    if t == "number":
        return str(prop["number"]) if prop["number"] is not None else ""

    # ---------- status ----------
    if t == "status":
        return prop["status"]["name"] if prop["status"] else ""

    # ---------- people ----------
    if t == "people":
        return ", ".join([x["name"] for x in prop["people"]])

    # ---------- date ----------
    if t == "date":
        return prop["date"]["start"] if prop["date"] else ""

    # ---------- checkbox ----------
    if t == "checkbox":
        return "Yes" if prop["checkbox"] else "No"

    # ==================================================
    # RELATION (แปลง id เป็นชื่อจริง)
    # ==================================================
    if t == "relation":
        ids = prop["relation"]

        names = []
        for item in ids:
            page_id = item["id"]
            names.append(get_page_title(page_id))

        return ", ".join(names)

    # ==================================================
    # ROLLUP
    # ==================================================
    if t == "rollup":
        roll = prop["rollup"]

        if roll["type"] == "number":
            return str(roll["number"])

        if roll["type"] == "date":
            return roll["date"]["start"] if roll["date"] else ""

        if roll["type"] == "array":
            vals = []

            for item in roll["array"]:
                vals.append(get_value(item))

            return ", ".join([str(x) for x in vals if x])

    return ""

# ==================================================
# แปลง row
# ==================================================
def parse(item):
    props = item["properties"]
    row = {}

    for key in props:
        row[key] = get_value(props[key])

    return row

# ==================================================
# เมนู
# ==================================================
def menu():
    return """
🤖 BPP414 Drug Network BOT

🔎 วิธีค้นหา

1️⃣ ค้นหาจากเลขบัตรประชาชน
ตัวอย่าง:
1869900207310

2️⃣ ค้นหาจากชื่อ
ตัวอย่าง:
สมชาย

3️⃣ ค้นหาจากสถานะ
ตัวอย่าง:
ติดตามขยายผล

4️⃣ ค้นหาจากเครือข่าย
ตัวอย่าง:
เครือข่ายท่าตะเภา

5️⃣ ค้นหาจาก Case ID
ตัวอย่าง:
CASE001

6️⃣ ค้นหาจากหน่วย
ตัวอย่าง:
414

📌 พิมพ์ข้อความได้เลย ระบบจะค้นหาให้ทันที
"""

# ==================================================
# แสดงผล
# ==================================================
def show_case(p):
    return f"""
📊 ผลการค้นหา

👑 เครือข่ายหลัก: {p.get('เครือข่ายหลัก','-')}
🔗 เครือข่าย: {p.get('เครือข่าย','-')}

🆔 เลขบัตร: {p.get('เลขบัตรประชาชน','-')}
👤 ชื่อสกุล: {p.get('ชื่อสกุล','-')}

🏠 ที่อยู่: {p.get('ที่อยู่ตามบัตรประชาชน','-')}

📁 Case ID: {p.get('Case ID','-')}
📌 สถานะ: {p.get('สถานะ','-')}
🎭 บทบาท: {p.get('บทบาท','-')}

🚓 หน่วย: {p.get('หน่วย','-')}
📮 ไปรษณีย์: {p.get('ไปรษณีย์','-')}

-------------------------
"""

# ==================================================
# SEARCH
# ==================================================
def search_data(data, keyword):
    keyword = keyword.lower()
    results = []

    for item in data:
        row = parse(item)

        text = str(row).lower()

        if keyword in text:
            results.append(row)

    if not results:
        return """
❌ ไม่พบข้อมูล

💡 ลองค้นหาด้วย:
- เลขบัตรประชาชน
- ชื่อสกุล
- สถานะ
- เครือข่าย
- Case ID
"""

    msg = f"🔍 พบ {len(results)} รายการ\n"

    for r in results[:5]:
        msg += show_case(r)

    return msg[:5000]

# ==================================================
# WEBHOOK
# ==================================================
@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.json

    for event in body["events"]:

        if event["type"] == "message":

            msg = event["message"]["text"].strip()
            reply_token = event["replyToken"]

            # เมนู
            if msg.lower() in ["menu", "เมนู", "help"]:
                reply(reply_token, menu())
                continue

            # โหลดข้อมูล
            notion_data = get_notion_data()

            # ค้นหา
            result = search_data(notion_data, msg)

            reply(reply_token, result)

    return "OK"

# ==================================================
# RUN
# ==================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
