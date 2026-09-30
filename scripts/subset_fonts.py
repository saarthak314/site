from pathlib import Path

from sitegen.font_pipeline import SYMBOL_UNICODES, subset_font

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_FONT_DIR = PROJECT_ROOT / "assets" / "fonts"
OUTPUT_FONT_DIR = PROJECT_ROOT / "static" / "fonts"


def main() -> None:
  size = subset_font(
    SOURCE_FONT_DIR / "JetBrainsMono-Regular.ttf",
    OUTPUT_FONT_DIR / "jetbrains-mono-symbols.woff2",
    SYMBOL_UNICODES,
  )
  print(f"jetbrains-mono-symbols.woff2: {size} bytes")


if __name__ == "__main__":
  main()
