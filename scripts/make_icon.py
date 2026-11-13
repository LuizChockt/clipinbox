"""Reproducible geometric application icon; original artwork, no external assets."""

from pathlib import Path

from PIL import Image, ImageDraw


def main():
    folder = Path(__file__).resolve().parents[1] / "src" / "clipinbox" / "resources"
    folder.mkdir(exist_ok=True)
    image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 8, 248, 248), radius=48, fill="#132b45")
    draw.rounded_rectangle((64, 48, 192, 177), radius=14, fill="#ffffff")
    draw.line((88, 78, 167, 78), fill="#83a6c3", width=9)
    draw.line((88, 104, 153, 104), fill="#83a6c3", width=9)
    draw.polygon(
        [
            (38, 145),
            (89, 145),
            (103, 166),
            (153, 166),
            (167, 145),
            (218, 145),
            (203, 211),
            (53, 211),
        ],
        fill="#39d4ad",
    )
    image.save(folder / "clipinbox.png")
    image.save(
        folder / "clipinbox.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


if __name__ == "__main__":
    main()
