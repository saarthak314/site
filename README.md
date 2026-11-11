# sλrthak

the source behind [sarrthak.com](https://sarrthak.com): personal site, writings, and a small static-site generator built from scratch.

no frontend framework: markdown goes in, and plain html, one stylesheet and two small scripts come out.

## map

- `content/`: the pages
  - `_index.md` is the home page: the intro copy, with experience, projects and `now_playing` in its front matter
  - each writing lives at `blogs/<slug>/index.md`
  - `404.md` is the not-found page
- `templates/`: jinja layouts (`base`, `home`, `blog`, `tags`, `404`, `redirect`) and partials (header, footer, the cat banner, the city under each post, the listening pane)
- `static/`: copied into the build as is
  - `index.css`, plus `code.css` for code blocks
  - `site.js` for the listening pane, its spectrum and the ships; `cat.js` for the ripple through the banner under a mouse or a finger
  - fonts, images, `CNAME`, `robots.txt`, `llms.txt`
- `assets/`: source fonts and images; the scripts below turn them into the symbol font subset and the webp variants in `static/`
- `src/sitegen/`: the generator
  - front matter, markdown, the content index and jinja rendering
  - atomic builds, feeds, validation and the dev server
  - `city.py`, the skyline drawn under each post
- `src/tests/`: unit tests, one file per module; `src/test_*.py` test the whole built site
- `scripts/`: generators for the art, images and fonts, plus `verify.sh`, the check ci runs
- `worker/spotify/`: the cloudflare worker behind the listening pane; its own readme covers setup
- `config.json`: site url, author, email, twitter handle, default social image
- `.github/workflows/`: checks, deploy, link check

## stack

- **build:** python 3.11+ with uv
- **pages:** jinja2 templates
- **markdown:** markdown-it-py, with pygments for code and latex2mathml for math
- **minifying:** rcssmin and rjsmin
- **build-time tools:** pillow for the banner, the images and the link preview card; fonttools and brotli for font subsets
- **fonts:** instrument serif, ibm plex mono and jetbrains mono, all self-hosted. the λ in the title, the banner, the city and the player's glyphs come from a small jetbrains mono subset
- **hosting:** github pages
- **listening pane:** a cloudflare worker that asks spotify what's playing

## run it

requires python 3.11+.

```sh
uv sync --dev
uv run sitegen dev --open
```

`dev` rebuilds on source changes, hot-swaps css, reloads changed pages, and keeps the last valid build visible when something breaks. `./main.sh` does the same on `0.0.0.0:${PORT:-8888}`.

## writing

```sh
uv run sitegen new my-post --title "..."  # scaffold a draft at content/blogs/my-post/
```

front matter takes:

- `title` and `date`, both required
- optional: `updated`, `description`, `tags`, `aliases` (old urls that redirect here), `slug`, `permalink`, `social_image`, `noindex`, `copyright` (overrides the © line in the footer)

drafts (`draft: true`) publish like any other post but carry a draft notice and a badge in the lists, are `noindex`, and stay out of the feed and sitemap. pass `--no-drafts` to any command to leave them out entirely.

`now_playing: https://.../now` on the home page turns on the listening pane under the social links. the browser fetches it from the worker, and the pane stays hidden until the worker answers.

## useful bits

```sh
uv run sitegen build                          # build into docs/
uv run sitegen check                          # build, then validate links, images, metadata, rss and sitemap
uv run sitegen serve                          # serve once without dev tooling
uv run python scripts/optimize_images.py      # rebuild responsive images and icons from assets/
uv run python scripts/subset_fonts.py         # rebuild the symbol font subset (λ, box drawing, banner, city and player glyphs)
uv run python scripts/generate_cat.py         # redraw the home banner (cat in space, as svg dots)
uv run python scripts/generate_art.py         # redraw the dartboard svg in the randomness post
uv run python scripts/generate_social_card.py # redraw the link preview card (the banner over the name)
./test.sh                                     # lint, format check, tests, a clean build, check, diff check
```

`python3 src/main.py` still works as the old build-only entrypoint.

## how it ships

- **ci:** every push runs `scripts/verify.sh` on python 3.11 and 3.13.
- **deploy:** a push to `main` builds the site, deploys it to github pages, and smoke-tests production.
- **links:** a weekly lychee job checks published links for rot. hosts that block bots are listed in `.lycheeignore`.
- **dependencies:** dependabot checks python and action dependencies weekly.

`docs/` is generated output and stays out of git.
