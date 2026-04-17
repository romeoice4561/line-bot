from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

# ===============================
# ENVIRONMENT VARIABLES (Render)
# ===============================
LINE_TOKEN = os.getenv("LINE_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

# ===============================
# BASIC CONFIG
# ===============================
NOTION_VERSION = "2022-06-28"
LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"

# ===============================
# HOME
# ===============================
@app.route("/", methods=["GET"])
def home():
    return "LINE + NOTION BOT RUNNING"

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
        "messages": [
            {
                "type": "text",
                "text": text[:4900]
            }
        ]
    }

    requests.post(LINE_REPLY_URL, headers=headers, json=body, timeout=15)

# ===============================
# GET ALL DATA FROM NOTION
# ===============================
def get_all_rows():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }

    results = []
    has_more = True
    cursor = None

    while has_more:
        payload = {}

        if cursor:
            payload["start_cursor"] = cursor

        r = requests.post(url, headers=headers, json=payload, timeout=20)
        data = r.json()

        results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        cursor = data.get("next_cursor")

    return results

# ===============================
# READ EVERY TYPE OF NOTION FIELD
# ===============================
def get_value(prop):
    t = prop["type"]

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
            arr = prop["relation"]
            return f"{len(arr)} รายการ" if arr else ""

        elif t == "people":
            arr = prop["people"]
            return ", ".join([x["name"] for x in arr]) if arr else ""

        elif t == "formula":
            f = prop["formula"]
            if f["type"] == "string":
                return f["string"] or ""
            elif f["type"] == "number":
                return str(f["number"]) if f["number"] else ""
            elif f["type"] == "boolean":
                return "ใช่" if f["boolean"] else "ไม่"

        elif t == "rollup":
            r = prop["rollup"]

            if r["type"] == "number":
                return str(r["number"]) if r["number"] else ""

            elif r["type"] == "date":
                if r["date"]:
                    return r["date"]["start"]
                return ""

            elif r["type"] == "array":
                vals = []
                for item in r["array"]:
                    vals.append(get_value(item))
                return ", ".join([x for x in vals if x])

        return ""

    except:
        return ""

# ===============================
# PARSE ROW
# ===============================
def parse_row(item):
    props = item["properties"]
    row = {}

    for key in props:
        row[key] = get_value(props[key])

    return row

# ===============================
# FIND FIELD
# ===============================
def pick(row, names):
    for n in names:
        if n in row and row[n]:
            return row[n]
    return ""

# ===============================
# FORMAT RESULT
# ===============================
def format_person(row, i):
    name = pick(row, ["ชื่อ", "ชื่อสกุล", "Name"])
    cid = pick(row, ["เลขบัตรประชาชน", "เลขบัตร", "ID"])
    netmain = pick(row, ["เครือข่ายหลัก"])
    network = pick(row, ["เครือข่าย"])
    caseid = pick(row, ["Case ID", "Case id"])
    province = pick(row, ["จังหวัด"])
    address = pick(row, ["ที่อยู่ตามบัตรประชาชน", "ที่อยู่"])
    status = pick(row, ["สถานะ"])
    send_status = pick(row, ["สถานะการส่ง"])
    unit = pick(row, ["หน่วย", "หน่วยรับผิดชอบ"])
    unit2 = pick(row, ["หน่วย(ย้อนหลัง)", "หน่วยย้อนหลัง"])
    post = pick(row, ["ไปรษณีย์"])
    send_date = pick(row, ["วันที่ส่ง"])
    role = pick(row, ["บทบาท"])

    text = f"""📌 รายการ {i}

👤 ชื่อ: {name}
🆔 เลขบัตร: {cid}
🌐 เครือข่ายหลัก: {netmain}
🕸️ เครือข่าย: {network}
📁 Case ID: {caseid}
📍 จังหวัด: {province}
🏠 ที่อยู่: {address}
🎯 สถานะ: {status}
📤 สถานะการส่ง: {send_status}
👮 หน่วยรับผิดชอบ: {unit}
👮‍♂️ หน่วย(ย้อนหลัง): {unit2}
📮 ไปรษณีย์: {post}
📅 วันที่ส่ง: {send_date}
🏷️ บทบาท: {role}

-------------------------
"""
    return text

# ===============================
# SEARCH
# ===============================
def search_data(keyword):
    rows = get_all_rows()
    found = []

    kw = keyword.strip().lower()

    for item in rows:
        row = parse_row(item)
        blob = json.dumps(row, ensure_ascii=False).lower()

        if kw in blob:
            found.append(row)

    if not found:
        return """❌ ไม่พบข้อมูล

🔎 ลองค้นหาจาก:
• เลขบัตร
• ชื่อ
• จังหวัด
• สถานะ
• Case ID
• เครือข่าย"""

    text = f"📊 พบ {len(found)} รายการ\n\n"

    count = 1
    for row in found[:20]:
        text += format_person(row, count)
        count += 1

    text += """
🔍 ค้นหาต่อได้จาก:
• เลขบัตร
• ชื่อ
• จังหวัด
• สถานะ
• Case ID
• เครือข่าย
"""

    if len(found) > 20:
        text += f"\n⚠️ แสดง 20 จาก {len(found)} รายการ"

    return text

# ===============================
# MENU
# ===============================
def menu_text():
    return """🤖 ระบบค้นหาฐานข้อมูลเครือข่าย

พิมพ์ค้นหาได้ทันที เช่น:

• เลขบัตรประชาชน
• ชื่อบุคคล
• จังหวัด
• สถานะ
• Case ID
• เครือข่าย

ตัวอย่าง:
ชุมพร
สุราษฎร์ธานี
ติดตามขยายผล
007/69
1840400058473
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
                reply_token = event["replyToken"]

                if msg.lower() in ["menu", "เมนู", "help", "ช่วย"]:
                    reply(reply_token, menu_text())
                else:
                    result = search_data(msg)
                    reply(reply_token, result)

        return "OK"

    except Exception as e:
        return str(e), 500

# ===============================
# RUN
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
