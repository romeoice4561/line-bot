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
# LINE REPLY
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
# อ่านค่า property แบบเร็วมาก
# ===============================
def get_value(prop):
    try:
        t = prop["type"]

        if t == "title":
            arr = prop["title"]
            return "".join([x["plain_text"] for x in arr])

        elif t == "rich_text":
            arr = prop["rich_text"]
            return "".join([x["plain_text"] for x in arr])

        elif t == "select":
            return prop["select"]["name"] if prop["select"] else ""

        elif t == "multi_select":
            return ", ".join([x["name"] for x in prop["multi_select"]])

        elif t == "number":
            return str(prop["number"]) if prop["number"] else ""

        elif t == "date":
            return prop["date"]["start"] if prop["date"] else ""

        elif t == "formula":
            f = prop["formula"]

            if f["type"] == "string":
                return f["string"] or ""

            if f["type"] == "number":
                return str(f["number"])

        elif t == "rollup":
            r = prop["rollup"]

            if r["type"] == "number":
                return str(r["number"])

            if r["type"] == "array":
                vals = []

                for x in r["array"][:5]:
                    if x["type"] == "rich_text":
                        vals.append("".join([a["plain_text"] for a in x["rich_text"]]))

                    elif x["type"] == "title":
                        vals.append("".join([a["plain_text"] for a in x["title"]]))

                    elif x["type"] == "select":
                        if x["select"]:
                            vals.append(x["select"]["name"])

                return ", ".join(vals)

        elif t == "relation":
            # ไม่ยิง API ซ้ำ
            return str(len(prop["relation"])) + " รายการ"

        return ""

    except:
        return ""


# ===============================
# ดึงข้อมูล Notion เร็ว
# ===============================
def get_data():
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
# แปลง row
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
    rows = get_data()

    found = []

    for r in rows:
        p = parse(r)

        text_all = " ".join([str(v) for v in p.values()]).lower()

        if keyword.lower() in text_all:
            found.append(p)

    return found


# ===============================
# SHOW RESULT
# ===============================
def show(found, keyword):
    if not found:
        return f"""❌ ไม่พบข้อมูล {keyword}

🔎 ค้นหาได้จาก:
🆔 เลขบัตร
📍 จังหวัด
📁 Case ID
🎯 สถานะ
🌐 เครือข่าย
"""

    txt = f"📊 พบ {len(found)} รายการ\n\n"

    for i, p in enumerate(found[:5], start=1):
        txt += f"""📌 รายการ {i}
👤 {p.get("ชื่อสกุล","")}
🆔 {p.get("เลขบัตรประชาชน","")}
🌐 {p.get("เครือข่ายหลัก","")}
🕸️ {p.get("เครือข่าย","")}
📁 {p.get("Case ID","")}
📍 {p.get("จังหวัด","")}
🎯 {p.get("สถานะ","")}
👮 {p.get("หน่วย","")}
📮 {p.get("ไปรษณีย์","")}
🏷️ {p.get("บทบาท","")}

----------------
"""

    txt += """
🔎 ค้นหาต่อ:
เลขบัตร / จังหวัด / สถานะ / Case ID
"""

    return txt[:5000]


# ===============================
# MENU
# ===============================
def menu():
    return """🤖 ระบบค้นหาฐานข้อมูล

พิมพ์ได้ เช่น

1869900207310
ชุมพร
ติดตามขยายผล
CASE001

🔎 ค้นหาจาก:
🆔 เลขบัตร
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
