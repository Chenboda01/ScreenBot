import tempfile
import unittest
from pathlib import Path

from bot.chats import (
    NEW_CHAT_TITLE,
    ChatStore,
    sanitize_title,
    suggested_title,
)


class TitleHelperTests(unittest.TestCase):
    def test_sanitize_title_strips_quotes_and_limits_words(self):
        # Given: an over-long quoted title line.
        raw = '"Tips for Google Slides and Other Things Today"'

        # When: it is sanitized.
        title = sanitize_title(raw)

        # Then: quotes are gone and only six words remain.
        self.assertEqual(
            "Tips for Google Slides and Other",
            title,
        )

    def test_sanitize_title_keeps_only_the_first_line(self):
        # Given: a multi-line reply from the brain.
        raw = "Tips for Google Slides\nHere is why I chose it."

        # When: it is sanitized.
        title = sanitize_title(raw)

        # Then: only the title line survives.
        self.assertEqual("Tips for Google Slides", title)

    def test_suggested_title_drops_filler_and_capitalizes(self):
        # Given: a chatty first message.
        message = (
            "can you tell me how to fix my python launcher error"
        )

        # When: a fallback title is suggested.
        title = suggested_title(message)

        # Then: the filler is gone and the first letter is capitalized.
        self.assertEqual(
            "How to fix my python launcher",
            title,
        )

    def test_suggested_title_falls_back_for_empty_message(self):
        # Given: an empty message.

        # When: a fallback title is suggested.
        title = suggested_title("   ")

        # Then: it is the neutral default.
        self.assertEqual(NEW_CHAT_TITLE, title)


class ChatStoreTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.NamedTemporaryFile(
            suffix=".json",
            delete=False,
        )
        temp.close()

        self.path = Path(temp.name)
        self.path.unlink()

    def tearDown(self):
        if self.path.exists():
            self.path.unlink()

    def test_new_chat_becomes_active_and_persists(self):
        # Given: an empty store.
        store = ChatStore(self.path)

        # When: a chat is created.
        chat = store.new_chat()

        # Then: it is active and survives a reload.
        self.assertEqual(chat["id"], store.active_id)
        self.assertEqual([], chat["messages"])
        self.assertEqual(NEW_CHAT_TITLE, chat["title"])

        reloaded = ChatStore(self.path)

        self.assertIsNotNone(reloaded.active())
        self.assertEqual(
            chat["id"],
            reloaded.active()["id"],
        )

    def test_append_stores_messages_and_orders_by_activity(self):
        # Given: two chats where the first one was used.
        store = ChatStore(self.path)
        first = store.new_chat()
        second = store.new_chat()

        store.append(first["id"], "user", "hello")
        store.append(first["id"], "screenbot", "hi")

        # When: the chats are listed.
        ordered = store.ordered()

        # Then: the used chat is first and messages persist.
        self.assertEqual(first["id"], ordered[0]["id"])
        self.assertEqual(second["id"], ordered[1]["id"])

        self.assertEqual(
            [
                {"role": "user", "text": "hello"},
                {"role": "screenbot", "text": "hi"},
            ],
            ChatStore(self.path).get(first["id"])["messages"],
        )

    def test_search_matches_titles_case_insensitively(self):
        # Given: two named chats.
        store = ChatStore(self.path)
        first = store.new_chat()
        second = store.new_chat()

        store.rename(first["id"], "Tips for Google Slides")
        store.rename(second["id"], "Python Launcher Error")

        # When: searching with a lowercase fragment.
        found = store.search("google")

        # Then: only the matching chat is returned.
        self.assertEqual(
            [first["id"]],
            [chat["id"] for chat in found],
        )

    def test_rename_wins_over_later_auto_title(self):
        # Given: a chat the user renamed.
        store = ChatStore(self.path)
        chat = store.new_chat()
        store.rename(chat["id"], "My Name")

        # When: the brain tries to title it later.
        store.auto_title(chat["id"], "Some Brain Title")

        # Then: the user's name is kept.
        self.assertEqual(
            "My Name",
            store.get(chat["id"])["title"],
        )

    def test_auto_title_cleans_and_applies_when_untouched(self):
        # Given: a fresh chat.
        store = ChatStore(self.path)
        chat = store.new_chat()

        # When: the brain suggests a quoted title.
        store.auto_title(chat["id"], '"Tips for Google Slides."')

        # Then: the cleaned title is stored.
        self.assertEqual(
            "Tips for Google Slides",
            store.get(chat["id"])["title"],
        )

    def test_delete_removes_chat_and_persists(self):
        # Given: two named chats.
        store = ChatStore(self.path)
        first = store.new_chat()
        second = store.new_chat()
        store.rename(first["id"], "First")
        store.rename(second["id"], "Second")

        # When: one is deleted.
        self.assertTrue(store.delete(second["id"]))

        # Then: only the other one survives on disk.
        self.assertEqual(
            ["First"],
            [
                chat["title"]
                for chat in ChatStore(self.path).ordered()
            ],
        )

    def test_deleting_active_chat_activates_the_newest_left(self):
        # Given: two chats where the older one was used most recently.
        store = ChatStore(self.path)
        older = store.new_chat()
        newer = store.new_chat()
        store.append(older["id"], "user", "hello")
        store.select(newer["id"])

        # When: the active chat is deleted.
        store.delete(newer["id"])

        # Then: the newest remaining chat becomes active.
        self.assertEqual(older["id"], store.active_id)

    def test_deleting_last_chat_clears_active(self):
        # Given: a store with a single chat.
        store = ChatStore(self.path)
        chat = store.new_chat()

        # When: it is deleted.
        store.delete(chat["id"])

        # Then: nothing is active and nothing persists.
        self.assertIsNone(store.active_id)
        self.assertEqual([], ChatStore(self.path).chats)

    def test_delete_unknown_chat_reports_false(self):
        # Given: an empty store.

        # When: an unknown id is deleted.
        store = ChatStore(self.path)

        # Then: it reports failure instead of raising.
        self.assertFalse(store.delete("missing"))

    def test_load_ignores_a_corrupt_file(self):
        # Given: a broken chats file.
        self.path.write_text("{not json")

        # When: the store loads.
        store = ChatStore(self.path)

        # Then: it starts empty instead of crashing.
        self.assertEqual([], store.chats)


if __name__ == "__main__":
    unittest.main()
