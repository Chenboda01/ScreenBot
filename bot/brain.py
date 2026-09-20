import json
import os
from pathlib import Path

import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:1b"

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-v4-flash"


def load_screenbot_secrets():
    path = (
        Path.home()
        / ".config"
        / "screenbot"
        / "secrets.env"
    )

    if not path.exists():
        return

    for line in path.read_text().splitlines():
        line = line.strip()

        if (
            not line
            or line.startswith("#")
            or "=" not in line
        ):
            continue

        key, value = line.split("=", 1)

        os.environ.setdefault(
            key.strip(),
            value.strip(),
        )


load_screenbot_secrets()


class HybridBrain:
    def __init__(self):
        self.deepseek_key = os.environ.get(
            "DEEPSEEK_API_KEY",
            "",
        )

        self.last_mode = "local"

    def pro_available(self):
        return bool(self.deepseek_key)

    def stream(self, prompt, mode="auto"):
        if (
            mode != "local"
            and self.pro_available()
        ):
            try:
                self.last_mode = "pro"

                yield from self._stream_deepseek(
                    prompt
                )

                return

            except Exception as error:
                print(
                    "[BRAIN] ⚠️ Pro Mode failed:",
                    error,
                )

                print(
                    "[BRAIN] 🏠 Falling back to Ollama."
                )

        self.last_mode = "local"

        yield from self._stream_ollama(
            prompt
        )

    def _stream_ollama(self, prompt):
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": True,
            },
            stream=True,
            timeout=180,
        )

        response.raise_for_status()

        for line in response.iter_lines():
            if not line:
                continue

            data = json.loads(
                line.decode("utf-8")
            )

            piece = data.get(
                "response",
                "",
            )

            if piece:
                yield piece

            if data.get("done"):
                break

    def _stream_deepseek(self, prompt):
        response = requests.post(
            DEEPSEEK_URL,
            headers={
                "Authorization":
                    f"Bearer {self.deepseek_key}",
                "Content-Type":
                    "application/json",
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are ScreenBot, a small "
                            "desktop robot companion. "
                            "Be friendly, clever, curious, "
                            "playful, and concise."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                "stream": True,
            },
            stream=True,
            timeout=180,
        )

        response.raise_for_status()

        for line in response.iter_lines():
            if not line:
                continue

            decoded = line.decode(
                "utf-8"
            ).strip()

            if not decoded.startswith("data:"):
                continue

            payload = decoded[5:].strip()

            if payload == "[DONE]":
                break

            data = json.loads(payload)

            choices = data.get(
                "choices",
                [],
            )

            if not choices:
                continue

            delta = choices[0].get(
                "delta",
                {},
            )

            piece = delta.get(
                "content",
                "",
            )

            if piece:
                yield piece
