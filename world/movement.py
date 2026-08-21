import random


class MovementEngine:
    def __init__(self):
        self.target_x = None
        self.speed = 3
        self.direction = 1

    def choose_target(self, current_x, screen_width, bot_width):
        max_x = max(0, screen_width - bot_width)

        # Usually wander somewhere nearby instead of
        # crossing the entire screen.
        distance = random.randint(100, 350)

        if random.random() < 0.5:
            distance = -distance

        target = current_x + distance
        target = max(0, min(max_x, target))

        self.target_x = target

        if target > current_x:
            self.direction = 1
        elif target < current_x:
            self.direction = -1

        return target

    def step(self, current_x):
        if self.target_x is None:
            return current_x, True

        distance = self.target_x - current_x

        if abs(distance) <= self.speed:
            current_x = self.target_x
            self.target_x = None
            return current_x, True

        if distance > 0:
            current_x += self.speed
            self.direction = 1
        else:
            current_x -= self.speed
            self.direction = -1

        return current_x, False
