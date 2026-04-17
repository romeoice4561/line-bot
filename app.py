from flask import Flask, request
import requests
import os

app = Flask(__name__)

LINE_TOKEN = os.getenv("LINE_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

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

def get_notion_data():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    res = requests.post(url, headers=headers)
    return res.json().get("results", [])

def get_value(prop):
    if prop["type"] == "title":
        return prop["title"][0]["plain_text"] if prop["title"] else ""

    if prop["type"] == "rich_text":
        return "".join([t["plain_text"] for t in prop["rich_text"]])

    if prop["type"] == "select":
        return prop["select"]["name"] if prop["select"] else ""

    if prop["type"] == "multi_select":
        return ", ".join([x["name"] for x in prop["multi_select"]])

    return ""

def parse(item):
    props = item["properties"]
    data = {}
    for key in props:
        data[key] = get_value(props[key])
    return data

def analyze(data, keyword):
    results = []
    for item in data:
        person = parse(item)
        if keyword in str(person):
            results.append(person)

    if not results:
        return "❌ ไม่พบข้อมูล"

    text = "📊 ผลการค้นหา\n\n"
    for p in results[:5]:
        for k, v in p.items():
            text += f"{k}: {v}\n"
        text += "\n-----------------\n"

    return text

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
