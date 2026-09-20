from world.vision import VisionEngine
from world.parking import ParkingEngine


def main():
    vision = VisionEngine()

    parking = ParkingEngine(
        vision=vision,
        bot_width=180,
        bot_height=160,
        step=120,
        max_score=0.30,
    )

    print("👁️ Capturing screen...")

    screenshot = vision.capture_screen()

    if screenshot is None:
        print("❌ Screenshot failed.")
        return

    print(f"✅ Screenshot: {screenshot}")
    print()

    # Temporary DEFAULT territory:
    # scan a horizontal strip near the lower part of the screen.
    territory_x = 0
    territory_y = 600
    territory_width = 1400
    territory_height = 160

    print("🤖 Searching DEFAULT territory...")

    best = parking.find_best_spot(
        screenshot=screenshot,
        territory_x=territory_x,
        territory_y=territory_y,
        territory_width=territory_width,
        territory_height=territory_height,
        current_x=300,
    )

    print()

    if best is None:
        print("😐 No safe parking spot found.")
        return

    print("🏆 Bob found a parking spot!")
    print(f"x = {best['x']}")
    print(f"y = {best['y']}")
    print(f"score = {best['raw_score']:.2f}")
    print(f"text = {best['text']:.2f}")
    print(f"visual = {best['visual']:.2f}")


if __name__ == "__main__":
    main()
