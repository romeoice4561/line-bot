from flask import Flask, request
import requests
import os
import traceback

app = Flask(__name__)

# ===============================
# ENV (ใส่ใน Render Environment)
# ===============================
LINE_TOKEN = os.getenv("LINE_TOKEN", "")
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
DATABASE_ID = os.getenv("DATABASE_ID", "")

# ===============================
# ตั้งค่า timeout
# ===============================
TIMEOUT = 12

# ===============================
# Header Notion
# ===============================
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}


# ==================================================
# ส่งข้อความกลับ LINE
# ==================================================
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

    except Exception as e:
        print("reply error:", e)


# ==================================================
# อ่านข้อมูล Notion
# ==================================================
def get_notion_data():
    try:
        url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

        payload = {
            "page_size": 100
        }

        res = requests.post(
            url,
            headers=NOTION_HEADERS,
            json=payload,
            timeout=TIMEOUT
        )

        return res.json().get("results", [])

    except Exception as e:
        print("notion query error:", e)
        return []


# ==================================================
# อ่าน relation page title
# ==================================================
def get_page_title(page_id):
    try:
        url = f"https://api.notion.com/v1/pages/{page_id}"

        res = requests.get(
            url,
            headers=NOTION_HEADERS,
            timeout=TIMEOUT
        )

        data = res.json()

        props = data.get("properties", {})

        for k in props:
            p = props[k]
            if p["type"] == "title":
                arr = p["title"]
                if arr:
                    return arr[0]["plain_text"]

        return page_id[:8]

    except:
        return page_id[:8]


# ==================================================
# อ่านค่า property ทุกชนิด
# ==================================================
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
            if prop["date"]:
                return prop["date"]["start"]
            return ""

        elif t == "checkbox":
            return "ใช่" if prop["checkbox"] else "ไม่"

        elif t == "url":
            return prop["url"] or ""

        elif t == "email":
            return prop["email"] or ""

        elif t == "phone_number":
            return prop["phone_number"] or ""

        elif t == "relation":
            ids = prop["relation"]
            if not ids:
                return ""

            names = []
            for r in ids[:5]:
                names.append(get_page_title(r["id"]))

            return ", ".join(names)

        elif t == "rollup":
            r = prop["rollup"]

            if r["type"] == "number":
                return str(r["number"])

            elif r["type"] == "date":
                if r["date"]:
                    return r["date"]["start"]
                return ""

            elif r["type"] == "array":
                arr = []
                for x in r["array"]:
                    if x["type"] == "title":
                        arr.append("".join([a["plain_text"] for a in x["title"]]))
                    elif x["type"] == "rich_text":
                        arr.append("".join([a["plain_text"] for a in x["rich_text"]]))
                    elif x["type"] == "select":
                        if x["select"]:
                            arr.append(x["select"]["name"])
                return ", ".join(arr)

            return ""

        elif t == "formula":
            f = prop["formula"]

            if f["type"] == "string":
                return f["string"] or ""

            elif f["type"] == "number":
                return str(f["number"])

            elif f["type"] == "boolean":
                return "ใช่" if f["boolean"] else "ไม่"

            return ""

        return ""

    except:
        return ""


# ==================================================
# แปลง row
# ==================================================
def parse_row(item):
    props = item["properties"]
    row = {}

    for k in props:
        row[k] = get_value(props[k])

    return row


# ==================================================
# ค้นหา
# ==================================================
def search(keyword):
    rows = get_notion_data()

    results = []

    for r in rows:
        data = parse_row(r)

        text_all = " ".join([str(v) for v in data.values()]).lower()

        if keyword.lower() in text_all:
            results.append(data)

    return results


# ==================================================
# จัดรูปแบบผลลัพธ์
# ==================================================
def show_result(results, keyword):
    if not results:
        return f"""❌ ไม่พบข้อมูล "{keyword}"

🔎 ลองค้นหาด้วย:
• เลขบัตรประชาชน
• จังหวัด
• สถานะ
• Case ID
• เครือข่าย
"""

    msg = f"📊 ผลการค้นหา {len(results)} รายการ\n\n"

    for i, p in enumerate(results[:5], start=1):
        msg += f"""📌 รายการ {i}
👤 ชื่อ: {p.get("ชื่อสกุล","")}
🆔 เลขบัตร: {p.get("เลขบัตรประชาชน","")}
🌐 เครือข่ายหลัก: {p.get("เครือข่ายหลัก","")}
🕸️ เครือข่าย: {p.get("เครือข่าย","")}
📁 Case ID: {p.get("Case ID","")}
📍 จังหวัด: {p.get("จังหวัด","")}
🎯 สถานะ: {p.get("สถานะ","")}
👮 หน่วย: {p.get("หน่วย","")}
📮 ไปรษณีย์: {p.get("ไปรษณีย์","")}
🏷️ บทบาท: {p.get("บทบาท","")}
🏠 ที่อยู่: {p.get("ที่อยู่ตามบัตรประชาชน","")}

-------------------
"""

    msg += """
🔎 ค้นหาต่อได้ด้วย:
• เลขบัตร
• จังหวัด
• สถานะ
• Case ID
• เครือข่าย
"""

    return msg[:5000]


# ==================================================
# เมนูเริ่มต้น
# ==================================================
def menu_text():
    return """🤖 ระบบค้นหาฐานข้อมูล

พิมพ์ค้นหาได้ เช่น

🆔 เลขบัตรประชาชน
📍 จังหวัด
📁 Case ID
🌐 เครือข่าย
🎯 สถานะ

ตัวอย่าง:
ชุมพร
ติดตามขยายผล
1869900207310
CASE001
"""


# ==================================================
# webhook
# ==================================================
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json

        for event in data["events"]:

            if event["type"] == "message":

                msg = event["message"]["text"].strip()
                reply_token = event["replyToken"]

                if msg.lower() in ["menu", "help", "start", "เริ่ม", "เมนู"]:
                    reply(reply_token, menu_text())
                    continue

                results = search(msg)

                text = show_result(results, msg)

                reply(reply_token, text)

        return "OK"

    except Exception as e:
        print(traceback.format_exc())
        return "OK"


# ==================================================
# home
# ==================================================
@app.route("/")
def home():
    return "LINE BOT RUNNING"


# ==================================================
# run
# ==================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
