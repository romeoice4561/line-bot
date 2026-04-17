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

# ===== NOTION QUERY =====
def get_notion_data():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    res = requests.post(url, headers=headers)
    return res.json().get("results", [])

# ===== PARSE VALUE =====
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

    return ""

# ===== PARSE ROW =====
def parse(item):
    props = item["properties"]
    data = {}

    for key in props:
        data[key] = get_value(props[key])

    return data

# ===== MAIN SEARCH LOGIC =====
def analyze(data, keyword):

    keyword = keyword.strip()
    results = []

    for item in data:
        person = parse(item)

        # 🔍 ค้นหาทุก field
        if keyword in str(person):
            results.append(person)

    # ===== ไม่เจอ =====
    if not results:
        return (
            "❌ ไม่พบข้อมูล\n\n"
            "🔎 ลองค้นหา:\n"
            "- จังหวัด เช่น: สุราษฎร์ธานี\n"
            "- เลขบัตรประชาชน\n"
            "- สถานะ เช่น: ติดตามขยายผล"
        )

    # ===== แยกติดตามขยายผล =====
    follow_cases = []
    for p in results:
        if "ติดตาม" in str(p.get("สถานะ", "")):
            follow_cases.append(p)

    text = "📊 ผลการค้นหา\n\n"

    # ===== แสดงผล =====
    for p in results[:5]:
        text += "👤 ชื่อ: " + p.get("ชื่อ", "-") + "\n"
        text += "🆔 เลขบัตร: " + p.get("เลขบัตรประชาชน", "-") + "\n"
        text += "📍 จังหวัด: " + p.get("จังหวัด", "-") + "\n"
        text += "📌 สถานะ: " + p.get("สถานะ", "-") + "\n"
        text += "🚓 หน่วยรับผิดชอบ: " + p.get("หน่วย(เชื่อมจริง)", "-") + "\n"
        text += "📮 ไปรษณีย์: " + p.get("ที่อยู่ไปรษณีย์(Auto)", "-") + "\n"
        text += "\n-----------------\n"

    # ===== ถ้ามีติดตามขยายผล =====
    if follow_cases:
        text += "\n🚨 เคสติดตามขยายผล\n"
        text += f"พบ {len(follow_cases)} ราย\n"

        provinces = set()
        for p in follow_cases:
            provinces.add(p.get("จังหวัด", "-"))

        text += "📍 จังหวัดที่ยังต้องติดตาม:\n"
        for prov in provinces:
            text += f"- {prov}\n"

    # ===== เมนูแนะนำ =====
    text += "\n💡 คำแนะนำค้นหาเพิ่มเติม\n"
    text += "- พิมพ์ชื่อจังหวัด\n"
    text += "- พิมพ์เลขบัตร\n"
    text += "- พิมพ์ 'ติดตามขยายผล'\n"

    return text

# ===== WEBHOOK =====
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    for event in data["events"]:
        if event["type"] == "message":
            msg = event["message"]["text"]
            reply_token = event["replyToken"]

            notion_data = get_notion_data()
            result = analyze(notion_data, msg)

            reply(reply_token, result)

    return "OK"

# ===== RUN =====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
