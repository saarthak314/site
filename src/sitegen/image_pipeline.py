from pathlib import Path

from PIL import Image, ImageOps

RESAMPLE = Image.Resampling.LANCZOS


def optimize_image(
  source: Path,
  output: Path,
  *,
  max_width: int | None = None,
  quality: int = 80,
) -> None:
  output.parent.mkdir(parents=True, exist_ok=True)
  with Image.open(source) as image:
    converted = image.convert("RGB")
    if max_width is not None and converted.width > max_width:
      height = round(converted.height * max_width / converted.width)
      converted = converted.resize((max_width, height), RESAMPLE)
    converted.save(output, "WEBP", quality=quality, method=6)


def write_responsive_variants(
  source: Path,
  output: Path,
  *,
  widths: tuple[int, ...] = (480, 960),
  quality: int = 78,
) -> tuple[Path, ...]:
  with Image.open(source) as image:
    source_width = image.width
  variants: list[Path] = []
  for width in sorted(set(widths)):
    if width >= source_width:
      continue
    variant = output.with_name(f"{output.stem}-{width}w{output.suffix}")
    optimize_image(source, variant, max_width=width, quality=quality)
    variants.append(variant)
  return tuple(variants)


def write_social_card(source: Path, output: Path) -> None:
  output.parent.mkdir(parents=True, exist_ok=True)
  with Image.open(source) as image:
    card = ImageOps.fit(image.convert("RGB"), (1200, 630), method=RESAMPLE)
    card.save(output, "JPEG", quality=84, optimize=True, progressive=True)


def write_favicon(source: Path, output: Path) -> None:
  output.parent.mkdir(parents=True, exist_ok=True)
  with Image.open(source) as image:
    square = ImageOps.fit(image.convert("RGBA"), (48, 48), method=RESAMPLE)
    square.save(output, "ICO", sizes=[(16, 16), (32, 32), (48, 48)])
