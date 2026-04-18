from flask import Flask, request
import requests
import os
import time
import threading

app = Flask(__name__)

# =========================
# ENV
# =========================
LINE_TOKEN = os.getenv("LINE_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

NOTION_URL = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

# =========================
# CACHE
# =========================
CACHE = {
    "time": 0,
    "data": []
}

CACHE_SECONDS = 180

# =========================
# HEADERS
# =========================
def notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

# =========================
# LINE REPLY
# =========================
def reply(token, text):
    url = "https://api.line.me/v2/bot/message/reply"

    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }

    body = {
        "replyToken": token,
        "messages": [
            {
                "type": "text",
                "text": text[:5000]
            }
        ]
    }

    try:
        requests.post(url, headers=headers, json=body, timeout=10)
    except:
        pass

# =========================
# SAFE VALUE READER
# =========================
def read_property(prop):

    t = prop.get("type", "")

    try:
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
            return ", ".join([x["id"][:6] for x in ids])

        elif t == "rollup":
            ru = prop["rollup"]

            if ru["type"] == "number":
                return str(ru["number"])

            elif ru["type"] == "date":
                return ru["date"]["start"] if ru["date"] else ""

            elif ru["type"] == "array":
                vals = []
                for i in ru["array"]:
                    vals.append(read_property(i))
                return ", ".join([v for v in vals if v])

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

# =========================
# GET ALL DATA (CACHE)
# =========================
def get_all_data():

    now = time.time()

    if now - CACHE["time"] < CACHE_SECONDS:
        return CACHE["data"]

    data = []
    cursor = None

    while True:

        payload = {
            "page_size": 100
        }

        if cursor:
            payload["start_cursor"] = cursor

        r = requests.post(
            NOTION_URL,
            headers=notion_headers(),
            json=payload,
            timeout=20
        )

        js = r.json()

        data.extend(js.get("results", []))

        if js.get("has_more"):
            cursor = js.get("next_cursor")
        else:
            break

    CACHE["time"] = now
    CACHE["data"] = data

    return data

# =========================
# CONVERT ROW
# =========================
def parse_row(item):

    props = item["properties"]

    row = {}

    for k in props:
        row[k] = read_property(props[k])

    return row

# =========================
# SMART SEARCH
# =========================
def search(keyword):

    keyword = keyword.strip().lower()

    rows = get_all_data()

    result = []

    for item in rows:

        row = parse_row(item)

        text = " | ".join([str(v).lower() for v in row.values()])

        if keyword in text:
            result.append(row)

    return result

# =========================
# FORMAT RESULT
# =========================
def show(rows):

    if not rows:
        return """❌ ไม่พบข้อมูล

🔎 ค้นหาได้จาก:
• เลขบัตร
• ชื่อ
• จังหวัด
• สถานะ
• Case ID
• เครือข่าย"""

    txt = f"📊 พบ {len(rows)} รายการ\n\n"

    count = 1

    for row in rows[:20]:

        txt += f"""📌 รายการ {count}
👤 ชื่อ: {row.get('ชื่อ','')}
🆔 เลขบัตร: {row.get('เลขบัตรประชาชน','')}
🌐 เครือข่ายหลัก: {row.get('เครือข่ายหลัก','')}
🕸️ เครือข่าย: {row.get('เครือข่าย','')}
📁 Case ID: {row.get('Case id','')}
📍 จังหวัด: {row.get('จังหวัด','')}
🏠 ที่อยู่: {row.get('ที่อยู่ตามบัตรประชาชน','')}
🎯 สถานะ: {row.get('สถานะ','')}
🏷️ บทบาท: {row.get('บทบาท','')}
👮 หน่วยรับผิดชอบ: {row.get('หน่วย','')}
🚓 หน่วยย้อนหลัง: {row.get('หน่วยย้อนหลัง','')}
📮 ไปรษณีย์: {row.get('ไปรษณีย์','')}
📅 วันที่ส่ง: {row.get('วันที่ส่ง','')}

----------------------

"""

        count += 1

    txt += """🔎 ค้นหาต่อได้จาก:
• เลขบัตร
• ชื่อ
• จังหวัด
• สถานะ
• Case ID
• เครือข่าย"""

    return txt[:5000]

# =========================
# ASYNC HANDLE
# =========================
def process_message(reply_token, msg):

    try:
        rows = search(msg)
        text = show(rows)
        reply(reply_token, text)

    except Exception as e:
        reply(reply_token, f"❌ ระบบขัดข้อง\n{str(e)[:100]}")

# =========================
# HOME
# =========================
@app.route("/")
def home():
    return "BOT RUNNING"

# =========================
# WEBHOOK
# =========================
@app.route("/webhook", methods=["POST"])
def webhook():

    data = request.json

    try:
        for event in data["events"]:

            if event["type"] == "message":

                msg = event["message"]["text"]
                token = event["replyToken"]

                threading.Thread(
                    target=process_message,
                    args=(token, msg)
                ).start()

        return "OK"

    except:
        return "OK"

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
