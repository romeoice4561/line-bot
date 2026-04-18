from flask import Flask, request
import requests
import os
import time

app = Flask(__name__)

# =========================
# ENV
# =========================
LINE_TOKEN = os.getenv("LINE_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

# =========================
# CONFIG
# =========================
NOTION_VERSION = "2022-06-28"
CACHE_SECONDS = 180
MAX_SHOW = 50
TIMEOUT = 12

cache_data = []
cache_time = 0
page_cache = {}

# =========================
# HEADERS
# =========================
def notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
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
        "messages": [{
            "type": "text",
            "text": text[:5000]
        }]
    }
    requests.post(url, headers=headers, json=body, timeout=10)

# =========================
# SAFE REQUEST
# =========================
def safe_post(url, json_data=None):
    try:
        r = requests.post(
            url,
            headers=notion_headers(),
            json=json_data,
            timeout=TIMEOUT
        )
        return r.json()
    except:
        return {}

def safe_get(url):
    try:
        r = requests.get(
            url,
            headers=notion_headers(),
            timeout=TIMEOUT
        )
        return r.json()
    except:
        return {}

# =========================
# GET PAGE TITLE FROM PAGE ID
# =========================
def get_page_title(page_id):
    if page_id in page_cache:
        return page_cache[page_id]

    data = safe_get(f"https://api.notion.com/v1/pages/{page_id}")
    props = data.get("properties", {})

    title = ""
    for k, v in props.items():
        if v["type"] == "title":
            arr = v["title"]
            if arr:
                title = arr[0]["plain_text"]
                break

    if title == "":
        title = page_id[:8]

    page_cache[page_id] = title
    return title

# =========================
# PROPERTY READER
# =========================
def read_prop(prop):

    t = prop["type"]

    if t == "title":
        arr = prop["title"]
        return "".join([x["plain_text"] for x in arr])

    if t == "rich_text":
        arr = prop["rich_text"]
        return "".join([x["plain_text"] for x in arr])

    if t == "number":
        return str(prop["number"] or "")

    if t == "select":
        return prop["select"]["name"] if prop["select"] else ""

    if t == "multi_select":
        return ", ".join([x["name"] for x in prop["multi_select"]])

    if t == "status":
        return prop["status"]["name"] if prop["status"] else ""

    if t == "date":
        if prop["date"]:
            return prop["date"]["start"]
        return ""

    if t == "checkbox":
        return "ใช่" if prop["checkbox"] else "ไม่"

    if t == "phone_number":
        return prop["phone_number"] or ""

    if t == "email":
        return prop["email"] or ""

    if t == "url":
        return prop["url"] or ""

    # RELATION ดึงชื่อจริง
    if t == "relation":
        ids = prop["relation"]
        names = []
        for x in ids[:10]:
            names.append(get_page_title(x["id"]))
        return ", ".join(names)

    # ROLLUP
    if t == "rollup":
        roll = prop["rollup"]

        if roll["type"] == "number":
            return str(roll["number"] or "")

        if roll["type"] == "date":
            if roll["date"]:
                return roll["date"]["start"]
            return ""

        if roll["type"] == "array":
            vals = []
            for item in roll["array"]:

                inner_type = item["type"]

                if inner_type == "title":
                    vals.append(
                        "".join([x["plain_text"] for x in item["title"]])
                    )

                elif inner_type == "rich_text":
                    vals.append(
                        "".join([x["plain_text"] for x in item["rich_text"]])
                    )

                elif inner_type == "select":
                    if item["select"]:
                        vals.append(item["select"]["name"])

                elif inner_type == "number":
                    vals.append(str(item["number"]))

                elif inner_type == "relation":
                    for rr in item["relation"]:
                        vals.append(get_page_title(rr["id"]))

            return ", ".join([v for v in vals if v])

        return ""

    return ""

# =========================
# LOAD NOTION
# =========================
def load_data():
    global cache_data, cache_time

    now = time.time()

    if now - cache_time < CACHE_SECONDS and cache_data:
        return cache_data

    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

    rows = []
    cursor = None

    while True:
        payload = {"page_size": 100}

        if cursor:
            payload["start_cursor"] = cursor

        data = safe_post(url, payload)

        results = data.get("results", [])
        rows.extend(results)

        if data.get("has_more"):
            cursor = data.get("next_cursor")
        else:
            break

        if len(rows) > 1000:
            break

    cache_data = rows
    cache_time = now
    return rows

# =========================
# CONVERT ROW
# =========================
def parse_row(item):
    props = item["properties"]
    out = {}

    for k in props:
        try:
            out[k] = read_prop(props[k]).strip()
        except:
            out[k] = ""

    return out

# =========================
# SEARCH
# =========================
def search(keyword):
    rows = load_data()
    found = []

    kw = keyword.lower().strip()

    for r in rows:
        row = parse_row(r)

        text = " | ".join(row.values()).lower()

        if kw in text:
            found.append(row)

    return found

# =========================
# PICK FIELD
# =========================
def pick(row, names):
    for n in names:
        if n in row and row[n]:
            return row[n]
    return ""

# =========================
# FORMAT RESULT
# =========================
def render(keyword):

    if keyword in ["เมนู", "help", "menu"]:
        return """📌 เมนูค้นหา

ค้นหาได้จาก:
• เลขบัตรประชาชน
• ชื่อ
• จังหวัด
• สถานะ
• เครือข่าย
• Case ID
• หน่วย

ตัวอย่าง:
ชุมพร
ติดตามขยายผล
007/69
414
"""

    found = search(keyword)

    if not found:
        return "❌ ไม่พบข้อมูล"

    msg = f"📊 พบ {len(found)} รายการ\n\n"

    for i, row in enumerate(found[:MAX_SHOW], 1):

        name = pick(row, ["ชื่อ", "ชื่อสกุล", "Person"])
        cid = pick(row, ["เลขบัตรประชาชน", "เลขบัตร", "ID"])
        netmain = pick(row, ["เครือข่ายหลัก"])
        net = pick(row, ["เครือข่าย"])
        caseid = pick(row, ["Case ID", "Case id"])
        province = pick(row, ["จังหวัดที่จับกุม", "จังหวัด"])
        addr = pick(row, ["ที่อยู่ตามบัตรประชาชน", "ที่อยู่"])
        status = pick(row, ["สถานะ"])
        send = pick(row, ["สถานะการส่ง"])
        unit = pick(row, ["หน่วย", "หน่วยรับผิดชอบ"])
        unit2 = pick(row, ["หน่วย(ย้อนหลัง)"])
        post = pick(row, ["ไปรษณีย์"])
        date = pick(row, ["วันที่ส่ง"])
        role = pick(row, ["บทบาท"])

        msg += f"""📌 รายการ {i}
👤 ชื่อ: {name}
🆔 เลขบัตร: {cid}
🌐 เครือข่ายหลัก: {netmain}
🕸️ เครือข่าย: {net}
📁 Case ID: {caseid}
📍 จังหวัด: {province}
🏠 ที่อยู่: {addr}
🎯 สถานะ: {status}
📤 สถานะการส่ง: {send}
👮 หน่วยรับผิดชอบ: {unit}
🚓 หน่วย(ย้อนหลัง): {unit2}
📮 ไปรษณีย์: {post}
📅 วันที่ส่ง: {date}
🏷️ บทบาท: {role}

--------------------

"""

    if len(found) > MAX_SHOW:
        msg += f"📌 แสดง {MAX_SHOW} จาก {len(found)} รายการ\n\n"

    msg += """🔎 ค้นหาต่อได้จาก:
• เลขบัตร
• ชื่อ
• จังหวัด
• สถานะ
• Case ID
• เครือข่าย"""

    return msg[:5000]

# =========================
# HOME
# =========================
@app.route("/", methods=["GET"])
def home():
    return "LINE BOT RUNNING"

# =========================
# WEBHOOK
# =========================
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json

        for event in data["events"]:
            if event["type"] == "message":
                if event["message"]["type"] == "text":
                    txt = event["message"]["text"].strip()
                    token = event["replyToken"]

                    result = render(txt)
                    reply(token, result)

        return "OK"

    except Exception as e:
        return str(e), 500

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
