from flask import Flask, request
import requests
import os
import traceback

app = Flask(__name__)

# ===============================
# ENV
# ===============================
LINE_TOKEN = os.getenv("LINE_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

TIMEOUT = 8

# ===============================
# HEADERS
# ===============================
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

# ===============================
# ส่งข้อความกลับ LINE
# ===============================
def reply(reply_token, text):
    try:
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

        requests.post(url, headers=headers, json=body, timeout=TIMEOUT)

    except:
        pass


# ===============================
# อ่านค่า Property ทุกชนิด
# ===============================
def get_value(prop):
    try:
        t = prop["type"]

        if t == "title":
            return "".join([x["plain_text"] for x in prop["title"]])

        elif t == "rich_text":
            return "".join([x["plain_text"] for x in prop["rich_text"]])

        elif t == "number":
            return str(prop["number"]) if prop["number"] else ""

        elif t == "select":
            return prop["select"]["name"] if prop["select"] else ""

        elif t == "multi_select":
            return ", ".join([x["name"] for x in prop["multi_select"]])

        elif t == "date":
            return prop["date"]["start"] if prop["date"] else ""

        elif t == "formula":
            f = prop["formula"]

            if f["type"] == "string":
                return f["string"] or ""

            if f["type"] == "number":
                return str(f["number"])

            if f["type"] == "boolean":
                return "ใช่" if f["boolean"] else "ไม่"

        elif t == "relation":
            # แสดงจำนวน relation
            return ", ".join([x["id"][:6] for x in prop["relation"][:5]])

        elif t == "rollup":
            r = prop["rollup"]

            if r["type"] == "number":
                return str(r["number"])

            if r["type"] == "date":
                return r["date"]["start"] if r["date"] else ""

            if r["type"] == "array":
                vals = []

                for x in r["array"][:10]:

                    if x["type"] == "title":
                        vals.append("".join([a["plain_text"] for a in x["title"]]))

                    elif x["type"] == "rich_text":
                        vals.append("".join([a["plain_text"] for a in x["rich_text"]]))

                    elif x["type"] == "select":
                        if x["select"]:
                            vals.append(x["select"]["name"])

                    elif x["type"] == "number":
                        vals.append(str(x["number"]))

                return ", ".join(vals)

        return ""

    except:
        return ""


# ===============================
# Query Notion
# ===============================
def get_rows():
    try:
        url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

        payload = {
            "page_size": 50
        }

        res = requests.post(
            url,
            headers=NOTION_HEADERS,
            json=payload,
            timeout=TIMEOUT
        )

        return res.json().get("results", [])

    except:
        return []


# ===============================
# Parse Row
# ===============================
def parse(item):
    props = item["properties"]

    row = {}

    for k in props:
        row[k] = get_value(props[k])

    return row


# ===============================
# SEARCH
# ===============================
def search(keyword):
    rows = get_rows()

    found = []

    for r in rows:
        p = parse(r)

        all_text = " ".join([str(v) for v in p.values()]).lower()

        if keyword.lower() in all_text:
            found.append(p)

    return found


# ===============================
# แสดงผลแบบละเอียด
# ===============================
def show(found, keyword):

    if not found:
        return f"""❌ ไม่พบข้อมูล {keyword}

🔎 ค้นหาได้จาก:
🆔 เลขบัตรประชาชน
👤 ชื่อ
📍 จังหวัด
📁 Case ID
🎯 สถานะ
🌐 เครือข่าย
"""

    txt = f"📊 พบ {len(found)} รายการ\n\n"

    for i, p in enumerate(found[:5], start=1):

        txt += f"""📌 รายการ {i}

👤 ชื่อ: {p.get("ชื่อ","")}
🆔 เลขบัตร: {p.get("เลขบัตรประชาชน","")}
🌐 เครือข่ายหลัก: {p.get("เครือข่ายหลัก","")}
🕸️ เครือข่าย: {p.get("เครือข่าย(Auto)","")}
📁 Case ID: {p.get("Case id","")}
📍 จังหวัด: {p.get("จังหวัดที่จับกุม(สุพรรณ)","")}
🏠 ที่อยู่: {p.get("ที่อยู่ตามบัตรประชาชน","")}
🎯 สถานะ: {p.get("สถานะ","")}
📤 สถานะการส่ง: {p.get("สถานะการส่ง","")}
👮 หน่วยรับผิดชอบ: {p.get("หน่วย(Auto)","")}
🚓 หน่วย(ย้อนหลัง): {p.get("หน่วย(ย้อนหลัง)","")}
📮 ไปรษณีย์: {p.get("ที่อยู่ไปรษณีย์(Auto)","")}
📅 วันที่ส่ง: {p.get("วันที่ส่ง","")}
🏷️ บทบาท: {p.get("บทบาทที่ตั้ง","")}

------------------------
"""

    txt += """
🔎 ค้นหาต่อได้จาก:
• เลขบัตร
• ชื่อ
• จังหวัด
• สถานะ
• Case ID
• เครือข่าย
"""

    return txt[:5000]


# ===============================
# เมนู
# ===============================
def menu():
    return """🤖 ระบบค้นหาฐานข้อมูล Person

พิมพ์ค้นหาได้ เช่น

1869900207310
นายสมชาย
สุราษฎร์ธานี
ถูกจับกุม
ติดตามขยายผล
007/69
CMC0102

🔎 ค้นหาได้จาก
🆔 เลขบัตร
👤 ชื่อ
📍 จังหวัด
📁 Case ID
🎯 สถานะ
🌐 เครือข่าย
"""


# ===============================
# WEBHOOK
# ===============================
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json

        for event in data["events"]:

            if event["type"] == "message":

                msg = event["message"]["text"].strip()
                token = event["replyToken"]

                if msg.lower() in ["menu", "help", "start", "เริ่ม", "เมนู"]:
                    reply(token, menu())
                    continue

                result = search(msg)

                reply(token, show(result, msg))

        return "OK"

    except:
        print(traceback.format_exc())
        return "OK"


# ===============================
# HOME
# ===============================
@app.route("/")
def home():
    return "BOT RUNNING"


# ===============================
# RUN
# ===============================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
