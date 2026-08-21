import random


class LifeEngine:
    def __init__(self):
        self.seconds_alive = 0
        self.last_action = 0
        self.last_speech = -300

    def tick(self, state, memory):
        self.seconds_alive += 1

        if state in {"thinking", "speaking", "sleepy"}:
            return None

        energy = float(memory.get("energy", 90))
        curiosity = float(memory.get("curiosity", 25))
        social = float(memory.get("social", 60))

        # Ordinary animations/actions can happen fairly often.
        if self.seconds_alive - self.last_action < 12:
            return None

        choices = ["idle"] * 8

        if curiosity > 35:
            choices.extend(["curious"] * 3)

        if energy > 40:
            choices.extend(["happy", "look_around"])

        # ScreenBot may speak AT MOST once every 5 minutes.
        can_speak = self.seconds_alive - self.last_speech >= 300

        if can_speak and social > 45:
            choices.extend(["speak"] * 2)

        # Usually nothing happens.
        if random.random() > 0.20:
            return None

        action = random.choice(choices)

        self.last_action = self.seconds_alive

        if action == "speak":
            self.last_speech = self.seconds_alive

        return action
