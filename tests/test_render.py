import unittest
from types import SimpleNamespace

from sitegen.render import _neighbours


def post(route: str, draft: bool = False) -> SimpleNamespace:
  return SimpleNamespace(route=route, draft=draft, is_post=True)


class TestNeighbours(unittest.TestCase):
  def test_the_posts_either_side_skip_drafts_unless_this_is_the_draft(self) -> None:
    newest, draft, middle, oldest = (
      post("/a/"),
      post("/b/", draft=True),
      post("/c/"),
      post("/d/"),
    )
    index = SimpleNamespace(posts=(newest, draft, middle, oldest))

    self.assertEqual(_neighbours(middle, index), (oldest, newest))
    self.assertEqual(_neighbours(newest, index), (middle, None))
    self.assertEqual(_neighbours(oldest, index), (None, middle))
    self.assertEqual(_neighbours(draft, index), (middle, newest))

  def test_pages_that_are_not_posts_have_none(self) -> None:
    home = SimpleNamespace(route="/", draft=False, is_post=False)
    index = SimpleNamespace(posts=(post("/a/"),))

    self.assertEqual(_neighbours(home, index), (None, None))
    self.assertEqual(_neighbours(post("/a/"), None), (None, None))


if __name__ == "__main__":
  unittest.main()
