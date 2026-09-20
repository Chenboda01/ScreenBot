import math
from typing import Final


MAX_TEXT_SCORE: Final = 0.05
MAX_VISUAL_SCORE: Final = 0.55


class ParkingEngine:
    def __init__(
        self,
        vision,
        bot_width=180,
        bot_height=160,
        step=90,
        max_score=0.22,
        max_travel=700,
        padding=30,
    ):
        self.vision = vision
        self.bot_width = bot_width
        self.bot_height = bot_height
        self.step = step
        self.max_score = max_score
        self.max_travel = max_travel
        self.padding = padding

    def evaluate_destination(
        self,
        screenshot,
        x,
        y,
    ):
        scan_x = x - self.padding
        scan_y = y - self.padding

        scan_width = (
            self.bot_width
            + self.padding * 2
        )

        scan_height = (
            self.bot_height
            + self.padding * 2
        )

        result = self.vision.score_region(
            screenshot,
            scan_x,
            scan_y,
            scan_width,
            scan_height,
        )

        return {
            "x": x,
            "y": y,
            "score": result["score"],
            "raw_score": result["score"],
            "text": result["text"],
            "visual": result["visual"],
        }

    def current_location(
        self,
        screenshot,
        current_x,
        current_y,
    ):
        return self.evaluate_destination(
            screenshot,
            current_x,
            current_y,
        )

    def is_safe(self, destination):
        return (
            destination["raw_score"] <= self.max_score
            and destination["text"] <= MAX_TEXT_SCORE
            and destination["visual"] <= MAX_VISUAL_SCORE
        )

    def intersects(self, x, y, rect):
        rx, ry, rw, rh = rect

        return not (
            x + self.bot_width <= rx
            or rx + rw <= x
            or y + self.bot_height <= ry
            or ry + rh <= y
        )

    def plan_parking(
        self,
        screenshot,
        territory_x,
        territory_y,
        territory_width,
        territory_height,
        current_x,
        current_y=None,
        own_rect=None,
        exclude_rect=None,
    ):
        self.vision.prepare_scan(screenshot, own_rect)

        if current_y is None:
            current_y = territory_y

        current = self.current_location(
            screenshot,
            current_x,
            current_y,
        )

        escape_mode = not self.is_safe(current)

        destination = self.find_best_spot(
            screenshot=screenshot,
            territory_x=territory_x,
            territory_y=territory_y,
            territory_width=territory_width,
            territory_height=territory_height,
            current_x=current_x,
            current_y=current_y,
            allow_long_travel=escape_mode,
            exclude_rect=exclude_rect,
        )

        return {
            "current": current,
            "destination": destination,
            "escape_mode": escape_mode,
        }

    def find_best_spot(
        self,
        screenshot,
        territory_x,
        territory_y,
        territory_width,
        territory_height,
        current_x=None,
        current_y=None,
        allow_long_travel=False,
        exclude_rect=None,
    ):
        candidates = []

        if current_y is None:
            current_y = territory_y

        max_x = (
            territory_x
            + territory_width
            - self.bot_width
        )

        max_y = (
            territory_y
            + territory_height
            - self.bot_height
        )

        y = territory_y

        while y <= max_y:
            x = territory_x

            while x <= max_x:
                distance = None

                if (
                    current_x is not None
                    and not allow_long_travel
                ):
                    distance = math.hypot(
                        x - current_x,
                        y - current_y,
                    )

                    if distance > self.max_travel:
                        x += self.step
                        continue

                if (
                    exclude_rect is not None
                    and self.intersects(
                        x,
                        y,
                        exclude_rect,
                    )
                ):
                    x += self.step
                    continue

                candidate = self.evaluate_destination(
                    screenshot,
                    x,
                    y,
                )

                score = candidate["raw_score"]

                if (
                    distance is not None
                    and distance < 100
                ):
                    score += 0.08

                if distance is not None:
                    score += (
                        distance
                        / self.max_travel
                        * 0.10
                    )

                candidate["score"] = score
                candidates.append(candidate)

                x += self.step

            y += self.step

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: item["score"]
        )

        best = candidates[0]

        # If everything nearby is busy,
        # Bob stays where he is.
        if not self.is_safe(best):
            return None

        return best
