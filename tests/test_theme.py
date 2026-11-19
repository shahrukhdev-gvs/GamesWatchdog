"""Guards for theme.py's stylesheet.

    python -m pytest tests/test_theme.py
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import theme  # noqa: E402


def test_stylesheet_has_nothing_the_html_sanitiser_would_strip():
    # st.html runs the <style> block through DOMPurify, which removes the whole
    # element if its text contains something tag-like ("<" + letter or "/").
    # That silently drops the entire theme, so it must never appear.
    found = re.findall(r".{0,30}<[/\w].{0,30}", theme._CSS)
    assert not found, f"tag-like text in theme._CSS: {found}"


def test_every_theme_colour_has_light_and_dark_values():
    # The :root palette must give a light and a dark value for every colour,
    # or that colour won't change when the viewer switches theme.
    root = re.search(r":root\s*\{(.*?)\}", theme._CSS, re.S).group(1)
    colours = [line.strip() for line in root.splitlines()
               if line.strip().startswith("--gv-") and "font" not in line
               and not any(k in line for k in ("display", "-ui:", "body:"))]
    assert colours, "no colour variables found in :root"
    missing = [c for c in colours if "light-dark(" not in c]
    assert not missing, f"colours without a light/dark pair: {missing}"
