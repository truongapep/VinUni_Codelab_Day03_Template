"""
Demo server cho Lab #3: Chatbot Baseline vs ReAct Agent.

Chạy: python app.py
Mở trình duyệt: http://localhost:5000
"""

import os
import sys

# Thêm thư mục starter-code vào sys.path để import được template.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STARTER_CODE_DIR = os.path.join(BASE_DIR, "..", "starter-code")
sys.path.insert(0, os.path.abspath(STARTER_CODE_DIR))

from flask import Flask, render_template, request, jsonify  # noqa: E402
from template import ChatbotBaseline, ReActAgent  # noqa: E402

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/query", methods=["POST"])
def query():
    data = request.get_json(force=True, silent=True) or {}
    user_input = data.get("query", "").strip()

    if not user_input:
        return jsonify({"error": "Vui lòng nhập câu hỏi."}), 400

    chatbot = ChatbotBaseline()
    baseline_result = chatbot.query(user_input)

    agent = ReActAgent(max_iterations=5)
    agent_result = agent.run(user_input)

    return jsonify({
        "baseline": baseline_result,
        "agent": agent_result,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)