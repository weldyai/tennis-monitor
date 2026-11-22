from scraper import _scroll_to_top


class _FakePage:
    def __init__(self):
        self.wheels = []
        self.mouse = self
        self.waits = 0

    def wheel(self, dx, dy):
        self.wheels.append(dy)

    def wait_for_timeout(self, ms):
        self.waits += 1


def test_scroll_to_top_scrolls_up_only():
    page = _FakePage()
    _scroll_to_top(page)
    assert page.wheels and all(dy < 0 for dy in page.wheels)
