# sλrthak

the source behind [sarrthak.com](https://sarrthak.com): personal site, writings, and a small static-site generator built from scratch.

## map

- `content/`: pages and writings
- `assets/`: source images used to generate published variants
- `templates/`: jinja layouts and partials
- `static/`: css, images, and public files
- `src/sitegen/`: the generator itself
- `.github/workflows/`: checks and deployment

## run it

requires python 3.11+.

```sh
uv sync --dev
uv run sitegen dev --open
```

`dev` rebuilds on source changes, hot-swaps css, reloads changed pages, and keeps the last valid build visible when something breaks.

drafts (`draft: true` in front matter) publish like any other post but carry a draft notice, a badge in the lists, `noindex`, and stay out of the feed and sitemap. pass `--no-drafts` to any command to leave them out entirely.

## useful bits

```sh
uv run sitegen build                    # build into docs/
uv run sitegen check                    # validate the generated site
uv run sitegen serve                    # serve once without dev tooling
uv run sitegen new my-post --title "..." # scaffold a draft writing
uv run python scripts/optimize_images.py # rebuild responsive images and icons
uv run python scripts/subset_fonts.py    # rebuild the symbol font subset (box drawing, λ)
uv run python scripts/generate_art.py    # regenerate the dartboard svg
uv run python scripts/generate_portrait.py # regenerate the home-page ascii portrait
uv run python scripts/generate_social_card.py # redraw the social preview card from the portrait
./test.sh                                # run every local verification
```

`python3 src/main.py` still works as the old build-only entrypoint.

## how it ships

every push runs the same verification script on python 3.11 and 3.13. `main` is built, deployed to github pages, and smoke-tested against production. a weekly job checks published links for rot.

`docs/` is generated output and stays out of git. dependabot checks python and action dependencies weekly.
