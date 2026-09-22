import json
import time
import uuid
from pathlib import Path


NEW_CHAT_TITLE = "New chat"

FILLER_PREFIXES = (
    "can you tell me ",
    "can you show me ",
    "can you ",
    "could you ",
    "would you ",
    "how do i ",
    "how can i ",
    "how to ",
    "i want to ",
    "i need to ",
    "help me ",
    "please ",
    "tell me about ",
    "tell me ",
)

TITLE_WORD_LIMIT = 6
TITLE_CHAR_LIMIT = 60


def sanitize_title(text):
    if not text:
        return ""

    first_line = str(text).strip().splitlines()[0].strip()
    cleaned = first_line.strip(
        "\"'`*_#.-:;!?()[] "
    ).strip()

    if not cleaned:
        return ""

    words = cleaned.split()[:TITLE_WORD_LIMIT]
    title = " ".join(words)

    if len(title) > TITLE_CHAR_LIMIT:
        title = title[:TITLE_CHAR_LIMIT].rstrip()

    return title


def suggested_title(message):
    text = " ".join(str(message).strip().split())

    lowered = text.lower()

    for prefix in FILLER_PREFIXES:
        if lowered.startswith(prefix):
            text = text[len(prefix):]
            break

    title = sanitize_title(text)

    if not title:
        return NEW_CHAT_TITLE

    if title[0].islower():
        title = title[0].upper() + title[1:]

    return title


class ChatStore:
    def __init__(self, path):
        self.path = Path(path)
        self.chats = []
        self.active_id = None
        self.mode = "shared"
        self.separate_modes = False
        self.load()

    def configure_mode(self, mode, separate_modes):
        self.mode = mode
        self.separate_modes = separate_modes
        self.active_id = None

    def belongs_to_current_mode(self, chat):
        if not self.separate_modes:
            return True

        return chat.get("mode", "shared") in {"shared", self.mode}

    def load(self):
        self.chats = []
        self.active_id = None

        if not self.path.exists():
            return

        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return

        if not isinstance(data, dict):
            return

        stored = data.get("chats")

        if not isinstance(stored, list):
            return

        for item in stored:
            chat = self.parse_chat(item)

            if chat is not None:
                self.chats.append(chat)

        active_id = data.get("active_id")

        if self.get(active_id) is not None:
            self.active_id = active_id

    def parse_chat(self, item):
        if not isinstance(item, dict):
            return None

        chat_id = item.get("id")

        if not isinstance(chat_id, str) or not chat_id:
            return None

        messages = []

        for message in item.get("messages", []):
            if not isinstance(message, dict):
                continue

            role = message.get("role")
            text = message.get("text")

            if role not in {"user", "screenbot"}:
                continue

            if not isinstance(text, str):
                continue

            messages.append(
                {
                    "role": role,
                    "text": text,
                }
            )

        title = item.get("title")
        created = item.get("created")
        updated = item.get("updated")

        return {
            "id": chat_id,
            "title": (
                title
                if isinstance(title, str) and title
                else NEW_CHAT_TITLE
            ),
            "messages": messages,
            "created": (
                float(created)
                if isinstance(created, (int, float))
                else 0.0
            ),
            "updated": (
                float(updated)
                if isinstance(updated, (int, float))
                else 0.0
            ),
            "renamed": bool(item.get("renamed", False)),
            "mode": item.get("mode", "shared"),
        }

    def save(self):
        data = {
            "chats": self.chats,
            "active_id": self.active_id,
        }

        self.path.write_text(
            json.dumps(data, indent=2)
        )

    def get(self, chat_id):
        for chat in self.chats:
            if chat["id"] == chat_id and self.belongs_to_current_mode(chat):
                return chat

        return None

    def active(self):
        if self.active_id is None:
            return None

        return self.get(self.active_id)

    def ordered(self):
        return sorted(
            [chat for chat in self.chats if self.belongs_to_current_mode(chat)],
            key=lambda chat: chat["updated"],
            reverse=True,
        )

    def search(self, query):
        needle = str(query or "").strip().lower()

        if not needle:
            return self.ordered()

        return [
            chat
            for chat in self.ordered()
            if needle in chat["title"].lower()
        ]

    def new_chat(self):
        now = time.time()

        chat = {
            "id": uuid.uuid4().hex,
            "title": NEW_CHAT_TITLE,
            "messages": [],
            "created": now,
            "updated": now,
            "renamed": False,
            "mode": self.mode if self.separate_modes else "shared",
        }

        self.chats.append(chat)
        self.active_id = chat["id"]
        self.save()

        return chat

    def select(self, chat_id):
        chat = self.get(chat_id)

        if chat is None:
            return None

        self.active_id = chat_id
        self.save()

        return chat

    def append(self, chat_id, role, text):
        chat = self.get(chat_id)

        if chat is None:
            return None

        chat["messages"].append(
            {
                "role": role,
                "text": text,
            }
        )

        chat["updated"] = time.time()
        self.save()

        return chat

    def auto_title(self, chat_id, title):
        chat = self.get(chat_id)

        if chat is None or chat["renamed"]:
            return None

        cleaned = sanitize_title(title)

        if not cleaned:
            return None

        chat["title"] = cleaned
        self.save()

        return chat

    def rename(self, chat_id, title):
        chat = self.get(chat_id)

        if chat is None:
            return None

        cleaned = sanitize_title(title)

        chat["title"] = cleaned or NEW_CHAT_TITLE
        chat["renamed"] = True
        self.save()

        return chat

    def delete(self, chat_id):
        chat = self.get(chat_id)

        if chat is None:
            return False

        self.chats.remove(chat)

        if self.active_id == chat_id:
            remaining = self.ordered()

            self.active_id = (
                remaining[0]["id"]
                if remaining
                else None
            )

        self.save()

        return True

    def copy_to_mode(self, source_modes, target_mode, chat_ids=None):
        now = time.time()
        copied = []

        for chat in self.chats:
            if chat.get("mode", "shared") not in source_modes:
                continue

            if chat_ids is not None and chat["id"] not in chat_ids:
                continue

            clone = {
                **chat,
                "id": uuid.uuid4().hex,
                "created": now,
                "updated": now,
                "mode": target_mode,
            }
            self.chats.append(clone)
            copied.append(clone)

        if copied:
            self.save()

        return copied
