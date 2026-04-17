from flask import Flask, request
import requests
import os

app = Flask(__name__)

# ===== ENV =====
LINE_TOKEN = os.getenv("LINE_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

# ===== LINE REPLY =====
def reply(reply_token, text):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }
    body = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text[:5000]}]
    }
    requests.post(url, headers=headers, json=body)

# ===== GET NOTION =====
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

# ===== อ่านค่าจาก Notion (รองรับทุก type) =====
def get_value(prop):
    t = prop["type"]

    if t == "title":
        return prop["title"][0]["plain_text"] if prop["title"] else ""

    if t == "rich_text":
        return "".join([x["plain_text"] for x in prop["rich_text"]])

    if t == "select":
        return prop["select"]["name"] if prop["select"] else ""

    if t == "multi_select":
        return ", ".join([x["name"] for x in prop["multi_select"]])

    if t == "number":
        return str(prop["number"]) if prop["number"] else ""

    if t == "date":
        return prop["date"]["start"] if prop["date"] else ""

    # 🔥 Relation
    if t == "relation":
        return ", ".join([x["id"] for x in prop["relation"]])

    # 🔥 Rollup
    if t == "rollup":
        roll = prop["rollup"]

        if roll["type"] == "array":
            values = []
            for item in roll["array"]:
                values.append(get_value(item))
            return ", ".join(values)

        if roll["type"] == "number":
            return str(roll["number"])

        if roll["type"] == "date":
            return roll["date"]["start"] if roll["date"] else ""

        if roll["type"] == "rich_text":
            return "".join([x["plain_text"] for x in roll["rich_text"]])

    return ""

# ===== แปลง row =====
def parse(item):
    props = item["properties"]
    data = {}

    for key in props:
        data[key] = get_value(props[key])

    return data

# ===== UI แสดงผล =====
def format_case(p):
    return f"""
📌 เคส: {p.get('เคส ID','-')}
👤 ชื่อ: {p.get('Person','-')}
🌍 จังหวัด: {p.get('จังหวัด','-')}
🏢 หน่วยรับผิดชอบ: {p.get('หน่วย','-')}
📮 ไปรษณีย์: {p.get('ไปรษณีย์','-')}
🔗 เครือข่าย: {p.get('เครือข่าย','-')}
📊 สถานะ: {p.get('สถานะการส่ง','-')}
📅 วันที่ส่ง: {p.get('วันที่ส่ง','-')}
------------------------
"""

# ===== วิเคราะห์ =====
def analyze(data, keyword):
    keyword = keyword.lower()
    results = []

    for item in data:
        p = parse(item)

        if keyword in str(p).lower():
            results.append(p)

    if not results:
        return "❌ ไม่พบข้อมูล"

    text = f"🔍 ผลการค้นหา: {keyword}\n\n"

    for p in results[:5]:
        text += format_case(p)

    return text

# ===== สรุปติดตาม =====
def summary_followup(data):
    results = []

    for item in data:
        p = parse(item)

        if "ติดตาม" in str(p):
            results.append(p)

    if not results:
        return "✅ ไม่มีเคสคงค้าง"

    text = "📊 เคสติดตามขยายผล\n\n"

    provinces = set()

    for p in results:
        provinces.add(p.get("จังหวัด", "-"))

    text += "📍 จังหวัดที่ยังค้าง:\n"
    for pr in provinces:
        text += f"- {pr}\n"

    text += "\n💡 แนะนำค้นหา:\n"
    text += "- พิมพ์ชื่อจังหวัด เช่น: ชุมพร\n"
    text += "- พิมพ์เลขบัตร\n"
    text += "- พิมพ์ชื่อเครือข่าย\n"

    return text

# ===== เมนู =====
def menu():
    return """
🤖 เมนูคำสั่ง

🔍 ค้นหา:
- พิมพ์ จังหวัด
- พิมพ์ เลขบัตร
- พิมพ์ ชื่อเครือข่าย

📊 สรุป:
- พิมพ์: สรุป
- พิมพ์: ติดตาม

ตัวอย่าง:
👉 ชุมพร
👉 1103700xxxxx
👉 เครือข่าย A
"""

# ===== WEBHOOK =====
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    for event in data["events"]:
        if event["type"] == "message":
            msg = event["message"]["text"]
            reply_token = event["replyToken"]

            notion_data = get_notion_data()

            # ===== MENU =====
            if msg in ["menu", "เมนู"]:
                reply(reply_token, menu())
                return "OK"

            # ===== SUMMARY =====
            if msg in ["สรุป", "ติดตาม"]:
                result = summary_followup(notion_data)
                reply(reply_token, result)
                return "OK"

            # ===== SEARCH =====
            result = analyze(notion_data, msg)
            reply(reply_token, result)

    return "OK"

# ===== RUN =====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
