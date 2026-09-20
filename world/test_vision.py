from world.vision import VisionEngine


def main():
    vision = VisionEngine()

    print("👁️ Capturing screen...")

    screenshot = vision.capture_screen()

    if screenshot is None:
        print("❌ Screenshot failed.")
        return

    print(f"✅ Screenshot: {screenshot}")

    # Test several locations across the lower part of the screen.
    # These rectangles are roughly Bob-sized.
    positions = [
        (50, 600),
        (300, 600),
        (550, 600),
        (800, 600),
        (1050, 600),
    ]

    print()
    print("🤖 Searching for parking spots...")
    print()

    best = None

    for x, y in positions:
        result = vision.score_region(
            screenshot,
            x,
            y,
            180,
            160,
        )

        print(
            f"x={x:4} y={y:4}  "
            f"score={result['score']:.2f}  "
            f"text={result['text']:.2f}  "
            f"visual={result['visual']:.2f}"
        )

        if best is None or result["score"] < best["score"]:
            best = {
                "x": x,
                "y": y,
                **result,
            }

    print()
    print(
        "🏆 Best parking spot:",
        f"x={best['x']}",
        f"y={best['y']}",
        f"score={best['score']:.2f}",
    )


if __name__ == "__main__":
    main()
