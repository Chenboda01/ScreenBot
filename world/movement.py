import random


class MovementEngine:
    def __init__(self):
        self.target_x = None
        self.target_y = None
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
        self.target_y = None

        if target > current_x:
            self.direction = 1
        elif target < current_x:
            self.direction = -1

        return target

    def set_target(self, target_x, target_y):
        self.target_x = target_x
        self.target_y = target_y

    def clear_target(self):
        self.target_x = None
        self.target_y = None

    def step(self, current_x):
        new_x, _, done = self.step_to(
            current_x,
            0,
        )

        return new_x, done

    def step_to(self, current_x, current_y):
        target_x = (
            current_x
            if self.target_x is None
            else self.target_x
        )

        target_y = (
            current_y
            if self.target_y is None
            else self.target_y
        )

        new_x = self.step_axis(
            current_x,
            target_x,
        )

        new_y = self.step_axis(
            current_y,
            target_y,
        )

        done = (
            new_x == target_x
            and new_y == target_y
        )

        if done:
            self.clear_target()

        if new_x > current_x:
            self.direction = 1

        elif new_x < current_x:
            self.direction = -1

        return new_x, new_y, done

    def step_axis(self, current, target):
        distance = target - current

        if abs(distance) <= self.speed:
            return target

        if distance > 0:
            return current + self.speed

        return current - self.speed
