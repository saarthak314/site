from pathlib import Path

from sitegen.image_pipeline import (
  optimize_image,
  write_favicon,
  write_responsive_variants,
  write_social_card,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_IMAGE_DIR = PROJECT_ROOT / "assets" / "images"
OUTPUT_IMAGE_DIR = PROJECT_ROOT / "static" / "images"


ARTICLE_IMAGES = (
  "ritsuko.png",
  "immutability.jpg",
  "frieren-studying.jpg",
  "lain_studying.png",
  "gojo.jpeg",
  "reddit-meme.jpg",
  "rand_max.png",
  "die_num_line.png",
  "partitions.png",
  "steps.png",
  "blackbox1.png",
  "blackbox2.png",
  "blackbox3.png",
  "lain-meme.jpeg",
  "square.png",
)


def main() -> None:
  for name in ARTICLE_IMAGES:
    source = SOURCE_IMAGE_DIR / name
    output = OUTPUT_IMAGE_DIR / Path(name).with_suffix(".webp")
    optimize_image(source, output, max_width=1200)
    write_responsive_variants(source, output)

  write_social_card(
    SOURCE_IMAGE_DIR / "ritsuko.png", OUTPUT_IMAGE_DIR / "social-card.jpg"
  )
  write_favicon(
    SOURCE_IMAGE_DIR / "favicon.png",
    OUTPUT_IMAGE_DIR / "favicon.ico",
  )


if __name__ == "__main__":
  main()
