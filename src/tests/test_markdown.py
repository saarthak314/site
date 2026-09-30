import tempfile
import unittest
from pathlib import Path

from sitegen.markdown import MarkdownRenderer, RenderedMarkdown


class TestMarkdownRenderer(unittest.TestCase):
  def setUp(self) -> None:
    self.renderer = MarkdownRenderer()

  def test_preserves_final_block_without_trailing_newline(self) -> None:
    rendered = self.renderer.render("first paragraph\n\nfinal paragraph")

    self.assertIn("<p>first paragraph</p>", rendered.html)
    self.assertIn("<p>final paragraph</p>", rendered.html)

  def test_preserves_unclosed_fence_content(self) -> None:
    rendered = self.renderer.render("```python\nprint('still here')")

    self.assertIn('<code class="language-python">', rendered.html)
    self.assertIn("still here", rendered.html)
    self.assertTrue(rendered.has_code)

  def test_renders_nested_emphasis_and_parenthesized_links(self) -> None:
    rendered = self.renderer.render(
      "**bold with _nested emphasis_** and [docs](https://example.com/a_(b))"
    )

    self.assertIn("<strong>bold with <em>nested emphasis</em></strong>", rendered.html)
    self.assertIn('href="https://example.com/a_(b)"', rendered.html)

  def test_keeps_mathjax_inside_inline_code_as_code(self) -> None:
    rendered = self.renderer.render("Use `$x_i + y_j$` literally.")

    self.assertIn("<code>$x_i + y_j$</code>", rendered.html)
    self.assertFalse(rendered.has_math)
    self.assertTrue(rendered.has_code)

  def test_preserves_mathjax_in_text_without_parsing_its_markdown(self) -> None:
    rendered = self.renderer.render("Inline $x_i * y_j$ and display \\[a_b + c_d\\].")

    self.assertIn("$x_i * y_j$", rendered.html)
    self.assertIn("\\[a_b + c_d\\]", rendered.html)
    self.assertNotIn("<em>", rendered.html)
    self.assertTrue(rendered.has_math)

  def test_renders_fence_languages_and_tables(self) -> None:
    rendered = self.renderer.render(
      "| name | value |\n| --- | --- |\n| alpha | 1 |\n\n```rust\nfn main() {}\n```"
    )

    self.assertIn("<table>", rendered.html)
    self.assertIn('<code class="language-rust">', rendered.html)
    self.assertIn('<span class="k">fn</span>', rendered.html)
    self.assertTrue(rendered.has_code)

  def test_disables_raw_html_and_escapes_image_attributes(self) -> None:
    rendered = self.renderer.render(
      '<script>alert("nope")</script>\n\n'
      '![the "quote" & more](https://example.com/a.png "title & more")'
    )

    self.assertIn("&lt;script&gt;alert(&quot;nope&quot;)&lt;/script&gt;", rendered.html)
    self.assertIn('alt="the &quot;quote&quot; &amp; more"', rendered.html)
    self.assertIn('title="title &amp; more"', rendered.html)
    self.assertNotIn("</img>", rendered.html)

  def test_assigns_deterministic_unique_heading_ids(self) -> None:
    markdown = "# Hello *World*\n\n## Hello World\n\n# Hello, World!"

    first = self.renderer.render(markdown)
    second = self.renderer.render(markdown)

    self.assertIn('<h1 id="hello-world">', first.html)
    self.assertIn('<h2 id="hello-world-2">', first.html)
    self.assertIn('<h1 id="hello-world-3">', first.html)
    self.assertEqual(first.html, second.html)

  def test_rejects_javascript_links(self) -> None:
    rendered = self.renderer.render("[do not click](javascript:alert(1))")

    self.assertNotIn("href=", rendered.html)
    self.assertNotIn("<a", rendered.html)

  def test_labels_generic_external_links_for_screen_readers(self) -> None:
    rendered = self.renderer.render(
      "read [more](https://cs3110.github.io/textbook/chapters/intro/past.html)"
    )

    self.assertIn(
      'more<span class="visually-hidden"> at cs3110.github.io</span>',
      rendered.html,
    )

  def test_adds_lazy_image_attributes_and_local_dimensions(self) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
      static_dir = Path(temp_dir)
      image_dir = static_dir / "images"
      image_dir.mkdir()
      png = (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00" * 8
        + (4).to_bytes(4, "big")
        + (3).to_bytes(4, "big")
      )
      image_dir.joinpath("test.png").write_bytes(png)
      image_dir.joinpath("test-480w.png").write_bytes(png)
      image_dir.joinpath("test-960w.png").write_bytes(png)

      rendered = MarkdownRenderer(static_dir=static_dir).render(
        "![test](/images/test.png)"
      )

    self.assertIn('loading="lazy"', rendered.html)
    self.assertIn('decoding="async"', rendered.html)
    self.assertIn('width="4"', rendered.html)
    self.assertIn('height="3"', rendered.html)
    self.assertIn(
      'srcset="/images/test-480w.png 480w, /images/test-960w.png 960w, /images/test.png 4w"',
      rendered.html,
    )
    self.assertIn('sizes="(max-width: 640px) calc(100vw - 34px), 653px"', rendered.html)

  def test_returns_description_reading_time_and_asset_flags(self) -> None:
    markdown = (
      "# Heading only\n\n"
      "> ignored quote\n\n"
      "A short **description** with a [link](https://example.com).\n\n"
      + " ".join(["word"] * 201)
      + "\n\n$$x + y$$\n\n`inline code`"
    )

    rendered = self.renderer.render(markdown)

    self.assertIsInstance(rendered, RenderedMarkdown)
    self.assertEqual(rendered.description, "A short description with a link.")
    self.assertEqual(rendered.reading_time, "2 min read")
    self.assertTrue(rendered.has_math)
    self.assertTrue(rendered.has_code)


if __name__ == "__main__":
  unittest.main()
