# sλrthak

the source behind [sarrthak.com](https://sarrthak.com): personal site, writings, and a small static-site generator built from scratch.

no frontend framework: markdown goes in, and plain html, one stylesheet and two small scripts come out.

## map

- `content/`: the pages
  - `_index.md` is the home page: the intro copy, with experience, projects, `now_playing` and `location` in its front matter
  - each writing lives at `blogs/<slug>/index.md`
  - `404.md` is the not-found page
- `templates/`: jinja layouts (`base`, `home`, `blog`, `tags`, `404`, `redirect`) and partials (header, footer, the cat banner, the city under each post, the listening pane)
- `static/`: copied into the build as is
  - `index.css`, plus `code.css` for code blocks
  - `site.js` for the listening pane, its spectrum and the ships; `cat.js` for the ripple through the banner under a mouse or a finger
  - fonts, images, `CNAME`, `robots.txt`, `llms.txt`
- `assets/`: the sources behind generated files in `static/`: original images, the full fonts, and `cards.json`, what each post's card was drawn with
- `src/sitegen/`: the generator, roughly in the order a build runs
  - `config.py`, `frontmatter.py`, `content.py`, `models.py`: read `config.json` and the pages into one content index
  - `markdown.py`: markdown to html, with code, math, image sizes, heading links and quote credits
  - `render.py`: the jinja environment and what each template is given; `city.py` draws the skyline under each post
  - `build.py`, `manifest.py`, `feeds.py`: atomic, incremental builds, the rss feed and the sitemap
  - `validate.py`: what `sitegen check` checks
  - `server.py`, `http_server.py`, `live_reload.py`, `watcher.py`: the dev server
  - `cli.py` is the `sitegen` command; `smoke.py` checks production after a deploy
  - `image_pipeline.py`, `font_pipeline.py`: the image and font steps the scripts below use
- `tests/`: one file per generator module, named after it; `test_site.py` and `test_site_fonts.py` build the real site and check the result; `test_workflows.py` holds ci and this readme to what they promise
- `scripts/`: redraw generated files (the banner, the link cards, the dartboard, image variants, the font subset); `verify.sh` is the full check ci runs
- `worker/spotify/`: the cloudflare worker behind the listening pane, and `auth.py`, which mints its spotify token; its own readme covers setup
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

`dev` rebuilds on source changes, hot-swaps css, reloads changed pages, and keeps the last valid build visible when something breaks. add `--host 0.0.0.0` to open it from a phone on the same network.

## writing

```sh
uv run sitegen new my-post --title "..."  # scaffold a draft at content/blogs/my-post/
```

front matter takes:

- `title` and `date`, both required
- optional: `updated`, `description`, `tags`, `aliases` (old urls that redirect here), `slug`, `permalink`, `social_image`, `noindex`, `copyright` (overrides the © line in the footer)

in a post:

- a code fence's language (` ```cpp `) shows as a small label on its frame; a fence marked ` ```output ` is what a program printed, set in a dashed frame with no copy button
- a quote whose last line starts with `-- ` (or `—`) shows that line under the quote as its credit
- every `##` and `###` heading links to itself, and the posts either side by date are linked at the foot

each post gets its own link preview card (the banner, the title, the date) once `scripts/generate_social_card.py --posts` has drawn `static/images/cards/<slug>.jpg`; until then it uses the site's card. run it again after adding a post or changing a title.

drafts (`draft: true`) publish like any other post but carry a draft notice and a badge in the lists, are `noindex`, and stay out of the feed and sitemap. pass `--no-drafts` to any command to leave them out entirely.

`now_playing: https://.../now` on the home page turns on the listening pane under the social links. the browser fetches it from the worker, and the pane stays hidden until the worker answers.

`location: new delhi` on the home page puts a small pin and the place in the header, and gives search engines the same place in the page's structured data.

## useful bits

```sh
uv run sitegen build                          # build into docs/
uv run sitegen check                          # build, then validate links, images, metadata, rss and sitemap
uv run sitegen serve                          # serve once without dev tooling
uv run python scripts/optimize_images.py      # rebuild responsive images and icons from assets/
uv run python scripts/subset_fonts.py         # rebuild the symbol font subset (λ, box drawing, banner, city and player glyphs)
uv run python scripts/generate_cat.py         # redraw the home banner (cat in space, as svg dots)
uv run python scripts/generate_dartboard.py   # redraw the dartboard svg in the randomness post
uv run python scripts/generate_social_card.py --posts # redraw the link preview cards (the site's, and one per post)
./scripts/verify.sh                           # lint, format check, tests, a clean build, check, diff check
```

## how it ships

- **ci:** every push runs `scripts/verify.sh` on python 3.11 and 3.13.
- **deploy:** a push to `main` builds the site, deploys it to github pages, and smoke-tests production.
- **links:** a weekly lychee job checks published links for rot. hosts that block bots are listed in `.lycheeignore`.
- **dependencies:** dependabot checks python and action dependencies weekly.

`docs/` is generated output and stays out of git.
