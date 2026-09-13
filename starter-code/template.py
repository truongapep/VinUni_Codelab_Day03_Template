"""
Lab #3: Baseline Chatbot vs ReAct Agent
Học viên hoàn thiện các mục TODO để hoàn thành bài lab.

Lưu ý: Agent này mô phỏng "Thought/Action" bằng rule-based (phân tích từ khóa +
regex) thay vì gọi LLM thật, nhưng vẫn thực thi tool THẬT (đọc JSON) và tuân
theo đúng vòng lặp ReAct: Thought -> Action -> Observation -> ... -> Final Answer.
"""

import json
import re
from tools import TOOL_DEFINITIONS, TOOL_MAP, get_flight_info, get_weather_forecast

SYSTEM_PROMPT = """Bạn là một ReAct Agent thông minh hỗ trợ khách hàng Vingroup.
Bạn chỉ sử dụng các công cụ sau:
{tools}

Quy trình trả lời bắt buộc:
Thought: <Suy nghĩ bước tiếp theo>
Action: {{"name": "<tên tool>", "args": {{<tham số>}}}}
Observation: <Kết quả từ tool>
... (Lặp lại cho tới khi có đủ dữ liệu)
Final Answer: <Câu trả lời hoàn chỉnh cho khách hàng>
"""


class ChatbotBaseline:
    """Baseline LLM Chatbot (Không sử dụng ReAct Loop hay Tools)"""
    def query(self, user_input: str) -> dict:
        # TODO: Chatbot baseline không tra cứu dữ liệu thật, không gọi tool nào
        answer = (
            f"Xin lỗi, tôi không thể tra cứu dữ liệu thực tế cho câu hỏi: "
            f"'{user_input}'. Tôi chỉ có thể trả lời chung chung."
        )
        return {
            "status": "success",
            "answer": answer,
            "tool_calls": []
        }


class ReActAgent:
    """ReAct Agent có sử dụng Thought-Action-Observation Loop"""

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.trace = []

    # ---------- Public API ----------
    def run(self, user_input: str) -> dict:
        self.trace = []
        self._last_flight_part = None
        self._last_weather_part = None

        # TODO 1: Lập kế hoạch các bước cần thực hiện (thay cho việc LLM tự quyết định)
        plan = self._build_plan(user_input)

        # TODO 2: Vòng lặp thực thi từng bước trong kế hoạch
        for step in plan:
            # TODO 4 (Safeguard): kiểm tra giới hạn max_iterations trước mỗi bước
            if len(self.trace) >= self.max_iterations:
                return {
                    "status": "max_iterations_reached",
                    "iterations": len(self.trace),
                    "trace": self.trace,
                    "answer": None
                }

            step_type = step["type"]

            # TODO 3 + 5: Thực thi Action, ghi Observation, lặp lại hoặc trả Final Answer
            if step_type == "flight_tool":
                entry, _ = self._execute_flight(step, include_final=False)
                self.trace.append(entry)

            elif step_type == "weather_tool":
                entry, _ = self._execute_weather(step, include_final=False)
                self.trace.append(entry)

            elif step_type == "final":
                parts = [p for p in [self._last_flight_part, self._last_weather_part] if p]
                answer = " ".join(parts)
                entry = {
                    "iteration": len(self.trace) + 1,
                    "thought": "Đã thu thập đủ thông tin, tổng hợp câu trả lời cuối cùng.",
                    "action": None,
                    "final_answer": answer
                }
                self.trace.append(entry)
                return {
                    "status": "completed",
                    "iterations": len(self.trace),
                    "trace": self.trace,
                    "answer": answer
                }

            elif step_type == "flight_final":
                entry, answer = self._execute_flight(step, include_final=True)
                self.trace.append(entry)
                return {
                    "status": "completed",
                    "iterations": len(self.trace),
                    "trace": self.trace,
                    "answer": answer
                }

            elif step_type == "weather_final":
                entry, answer = self._execute_weather(step, include_final=True)
                self.trace.append(entry)
                return {
                    "status": "completed",
                    "iterations": len(self.trace),
                    "trace": self.trace,
                    "answer": answer
                }

            elif step_type == "faq_final":
                answer = self._faq_answer(user_input)
                entry = {
                    "iteration": len(self.trace) + 1,
                    "thought": "Câu hỏi không cần tra cứu dữ liệu, trả lời từ kiến thức chung.",
                    "action": None,
                    "final_answer": answer
                }
                self.trace.append(entry)
                return {
                    "status": "completed",
                    "iterations": len(self.trace),
                    "trace": self.trace,
                    "answer": answer
                }

        return {
            "status": "max_iterations_reached",
            "iterations": len(self.trace),
            "trace": self.trace,
            "answer": None
        }

    # ---------- Planning (thay thế bước LLM sinh Thought/Action) ----------
    def _build_plan(self, user_input: str):
        codes_in_order = re.findall(r"\b(HAN|SGN|DAD)\b", user_input.upper())
        unique_codes = list(dict.fromkeys(codes_in_order))  # giữ thứ tự, loại trùng

        has_flight_kw = any(kw in user_input.lower() for kw in ["chuyến bay", "vé"])
        has_weather_kw = any(kw in user_input.lower() for kw in ["thời tiết", "mặc gì"])

        flight_needed = has_flight_kw and len(unique_codes) >= 2
        weather_needed = has_weather_kw and len(codes_in_order) >= 1

        if flight_needed and weather_needed:
            max_price = self._extract_max_price(user_input)
            return [
                {"type": "flight_tool", "origin": unique_codes[0],
                 "destination": unique_codes[1], "max_price": max_price},
                {"type": "weather_tool", "city_code": codes_in_order[-1]},
                {"type": "final"}
            ]
        elif flight_needed:
            max_price = self._extract_max_price(user_input)
            return [{"type": "flight_final", "origin": unique_codes[0],
                     "destination": unique_codes[1], "max_price": max_price}]
        elif weather_needed:
            return [{"type": "weather_final", "city_code": codes_in_order[-1]}]
        else:
            return [{"type": "faq_final"}]

    def _extract_max_price(self, user_input: str) -> int:
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*tri[eệ]u", user_input.lower())
        if match:
            value = float(match.group(1).replace(",", "."))
            return int(value * 1_000_000)
        return 5_000_000

    # ---------- Tool execution helpers ----------
    def _execute_flight(self, step, include_final: bool):
        thought = f"Cần tra cứu chuyến bay từ {step['origin']} đến {step['destination']}."
        action = {
            "name": "get_flight_info",
            "args": {
                "origin": step["origin"],
                "destination": step["destination"],
                "max_price": step["max_price"]
            }
        }
        result = get_flight_info(**action["args"])
        observation = f"Observation: {json.dumps(result, ensure_ascii=False)}"
        answer_part = self._format_flights(result)

        entry = {
            "iteration": len(self.trace) + 1,
            "thought": thought,
            "action": action,
            "observation": observation
        }

        if include_final:
            entry["final_answer"] = answer_part
            return entry, answer_part
        else:
            self._last_flight_part = answer_part
            return entry, None

    def _execute_weather(self, step, include_final: bool):
        thought = f"Cần tra cứu thời tiết tại {step['city_code']}."
        action = {"name": "get_weather_forecast", "args": {"city_code": step["city_code"]}}
        result = get_weather_forecast(**action["args"])
        observation = f"Observation: {json.dumps(result, ensure_ascii=False)}"
        answer_part = self._format_weather(result)

        entry = {
            "iteration": len(self.trace) + 1,
            "thought": thought,
            "action": action,
            "observation": observation
        }

        if include_final:
            entry["final_answer"] = answer_part
            return entry, answer_part
        else:
            self._last_weather_part = answer_part
            return entry, None

    # ---------- Answer formatting ----------
    def _format_flights(self, flights) -> str:
        if not flights:
            return "Không tìm thấy chuyến bay phù hợp."
        parts = [
            f"Chuyến bay {f['flight_number']} ({f['airline']}) giá {f['price_vnd']:,} VND, "
            f"khởi hành {f['departure_time']}."
            for f in flights
        ]
        return " ".join(parts)

    def _format_weather(self, weather: dict) -> str:
        if "error" in weather:
            return f"Không tìm thấy dữ liệu thời tiết ({weather['error']})."
        return (
            f"Thời tiết tại {weather['city']}: {weather['temperature_c']}°C, "
            f"{weather['condition']}, độ ẩm {weather['humidity_pct']}%. "
            f"Gợi ý: {weather['recommendation']}"
        )

    def _faq_answer(self, user_input: str) -> str:
        return (
            "Theo chính sách của Vinpearl, khách hàng có thể đổi/trả vé máy bay tùy theo "
            "hạng vé và điều kiện của hãng bay, thường mất phí đổi vé và cần thực hiện "
            "trước giờ khởi hành. Vui lòng liên hệ tổng đài Vinpearl để biết chi tiết."
        )


def main():
    user_query = "Tìm cho tôi chuyến bay từ HAN đi SGN dưới 2 triệu, rồi cho biết thời tiết SGN nên mặc gì?"

    print("=== RUNNING CHATBOT BASELINE ===")
    chatbot = ChatbotBaseline()
    print(json.dumps(chatbot.query(user_query), indent=2, ensure_ascii=False))

    print("\n=== RUNNING REACT AGENT ===")
    agent = ReActAgent(max_iterations=5)
    result = agent.run(user_query)
    print("Result:", json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()