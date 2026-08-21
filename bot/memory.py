from collections import deque


class ConversationMemory:
    def __init__(self, max_messages=20):
        self.messages = deque(maxlen=max_messages)

    def add_user(self, text):
        self.messages.append(
            {
                "role": "user",
                "text": text,
            }
        )

    def add_screenbot(self, text):
        self.messages.append(
            {
                "role": "screenbot",
                "text": text,
            }
        )

    def recent_text(self):
        if not self.messages:
            return "No recent conversation."

        lines = []

        for item in self.messages:
            speaker = "User" if item["role"] == "user" else "ScreenBot"
            lines.append(f"{speaker}: {item['text']}")

        return "\n".join(lines)
