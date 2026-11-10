"""
theme.py — the dashboard's "game studio" look.

apply_theme() injects the CSS once per run; hero(), login_header() and
player_card() render the custom HTML blocks. Everything else stays plain
Streamlit (see CLAUDE.md: no custom components), styled through CSS that
targets Streamlit's data-testid / baseweb hooks.

Colours live in .streamlit/config.toml (built-in widgets) and in the :root
variables below (custom blocks). Keep the two in step.
"""

import html
from datetime import datetime, timedelta, timezone

import streamlit as st

STUDIO_NAME = "Game Village Studio"
APP_NAME_PLAIN, APP_NAME_GLOW = "Play Store", "Watchdog"
PKT = timezone(timedelta(hours=5))

# Gamepad mark used in the hero and on the login page.
_LOGO_SVG = (
    '<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
    '<path d="M20 18h24c8.8 0 15 7.2 15 16.4 0 9.7-5 17.6-11.3 17.6-4.3 0-6.6-3.5-9-7.2-1.1-1.7-2.7-2.8-4.7-2.8h-4'
    'c-2 0-3.6 1.1-4.7 2.8-2.4 3.7-4.7 7.2-9 7.2C9.9 52 5 44.1 5 34.4 5 25.2 11.2 18 20 18Z" '
    'fill="rgba(255,255,255,.14)" stroke="#fff" stroke-width="3" stroke-linejoin="round"/>'
    '<path d="M20 28v10M15 33h10" stroke="#fff" stroke-width="3.4" stroke-linecap="round"/>'
    '<circle cx="42" cy="30" r="3.2" fill="#22e4ff"/><circle cx="48.5" cy="36.5" r="3.2" fill="#b6ff3b"/>'
    '</svg>'
)

_FONTS = ("https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900"
          "&family=Rajdhani:wght@500;600;700&family=Inter:wght@400;500;600&display=swap")

_CSS = """
@import url('__FONTS__');

:root {
  --gv-bg: #06050d;
  --gv-panel: rgba(21, 18, 46, .72);
  --gv-line: rgba(139, 92, 246, .28);
  --gv-line-strong: rgba(139, 92, 246, .62);
  --gv-violet: #8b5cf6;
  --gv-pink: #ff2e88;
  --gv-cyan: #22e4ff;
  --gv-lime: #b6ff3b;
  --gv-text: #ecebff;
  --gv-muted: #a3a0cc;
  --gv-display: 'Orbitron', 'Rajdhani', sans-serif;
  --gv-ui: 'Rajdhani', 'Inter', sans-serif;
  --gv-body: 'Inter', 'Source Sans Pro', sans-serif;
}

/* ---------- canvas: deep space + neon glow + faint grid ---------- */
.stApp {
  font-family: var(--gv-body);
  color: var(--gv-text);
  background:
    radial-gradient(1100px 560px at 8% -12%, rgba(139, 92, 246, .26), transparent 62%),
    radial-gradient(900px 520px at 108% 6%, rgba(255, 46, 136, .16), transparent 60%),
    radial-gradient(900px 640px at 50% 118%, rgba(34, 228, 255, .10), transparent 62%),
    linear-gradient(rgba(139, 92, 246, .045) 1px, transparent 1px) 0 0 / 46px 46px,
    linear-gradient(90deg, rgba(139, 92, 246, .045) 1px, transparent 1px) 0 0 / 46px 46px,
    var(--gv-bg);
  background-attachment: fixed;
}
[data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stBottom"] > div {
  background: transparent;
}
[data-testid="stHeader"] {
  background: rgba(6, 5, 13, .6);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--gv-line);
}
[data-testid="stMainBlockContainer"] { padding-top: 3.4rem; }
::selection { background: rgba(255, 46, 136, .35); }

/* ---------- type ---------- */
.stApp h1, .stApp h2 { font-family: var(--gv-display); letter-spacing: .04em; }
.stApp h3 {
  font-family: var(--gv-ui);
  font-weight: 700;
  font-size: 1.4rem;
  text-transform: uppercase;
  letter-spacing: .09em;
  display: flex;
  align-items: center;
  gap: .65rem;
}
.stApp h3::before {
  content: "";
  flex: none;
  width: 6px;
  height: 1.1em;
  border-radius: 3px;
  background: linear-gradient(180deg, var(--gv-cyan), var(--gv-pink));
  box-shadow: 0 0 14px rgba(34, 228, 255, .65);
}
.stApp h4, .stApp h5 { font-family: var(--gv-ui); font-weight: 700; letter-spacing: .05em; }
.stApp a { color: var(--gv-cyan); text-decoration: none; }
.stApp a:hover { color: var(--gv-pink); text-shadow: 0 0 12px rgba(255, 46, 136, .6); }
.stApp code {
  color: var(--gv-cyan);
  background: rgba(34, 228, 255, .08);
  border: 1px solid rgba(34, 228, 255, .18);
  border-radius: 6px;
}
[data-testid="stCaptionContainer"] { color: var(--gv-muted); }
.stApp hr {
  border: none;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--gv-line-strong), rgba(34, 228, 255, .5), transparent);
}

/* ---------- tabs: a glowing nav bar ----------
   Streamlit >= 1.6x renders tabs with react-aria ([role=tab], aria-selected);
   older versions used baseweb. Both are covered. */
.stTabs [role="tablist"] {
  gap: 4px;
  height: auto;
  flex-wrap: wrap;      /* 10 tabs: wrap to a second row instead of hiding some behind a scroll */
  overflow: visible;
  padding: 6px;
  background: var(--gv-panel);
  border: 1px solid var(--gv-line);
  border-radius: 14px;
  backdrop-filter: blur(10px);
  box-shadow: 0 18px 40px -28px rgba(139, 92, 246, .9);
}
.stTabs [role="tablist"]::after, .stTabs .react-aria-SelectionIndicator,
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }
.stTabs [role="tab"] {
  flex: none;
  height: auto;
  padding: 7px 12px;
  border-radius: 10px;
  background: transparent;
  color: var(--gv-muted);
  transition: background .18s, color .18s, box-shadow .18s;
}
.stTabs [role="tab"] p {
  font-family: var(--gv-ui);
  font-weight: 700;
  font-size: 1rem;
  letter-spacing: .03em;
  white-space: nowrap;
}
.stTabs [role="tab"]:hover { color: var(--gv-text); background: rgba(139, 92, 246, .14); }
.stTabs [role="tab"][aria-selected="true"] {
  color: #fff;
  background: linear-gradient(135deg, rgba(124, 58, 237, .95), rgba(255, 46, 136, .88));
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, .12), 0 6px 22px -6px rgba(255, 46, 136, .7);
}
.stTabs [role="tab"]:focus-visible { outline: 2px solid var(--gv-cyan); outline-offset: 1px; }
.stTabs [data-testid="stTabPanel"], .stTabs [data-baseweb="tab-panel"] { padding-top: 1.1rem; }

/* ---------- buttons ---------- */
[data-testid^="stBaseButton"] {
  border-radius: 10px;
  transition: transform .12s ease, box-shadow .18s ease, border-color .18s ease, filter .18s ease;
}
[data-testid^="stBaseButton"] p {
  font-family: var(--gv-ui);
  font-weight: 700;
  font-size: 1rem;
  letter-spacing: .07em;
  text-transform: uppercase;
}
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"] {
  background: rgba(139, 92, 246, .08);
  border: 1px solid var(--gv-line-strong);
  color: var(--gv-text);
}
[data-testid="stBaseButton-secondary"]:hover, [data-testid="stBaseButton-secondaryFormSubmit"]:hover {
  border-color: var(--gv-cyan);
  color: #fff;
  background: rgba(34, 228, 255, .08);
  box-shadow: inset 0 0 0 1px var(--gv-cyan), 0 0 20px -4px rgba(34, 228, 255, .7);
  transform: translateY(-1px);
}
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
  border: 0;
  color: #fff;
  background: linear-gradient(135deg, #7c3aed 0%, #c026d3 55%, #ff2e88 100%);
  box-shadow: 0 10px 26px -12px rgba(255, 46, 136, .9), inset 0 1px 0 rgba(255, 255, 255, .25);
}
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {
  color: #fff;
  filter: brightness(1.12) saturate(1.1);
  box-shadow: 0 14px 34px -10px rgba(255, 46, 136, 1), 0 0 0 1px rgba(255, 255, 255, .15) inset;
  transform: translateY(-1px);
}
[data-testid^="stBaseButton"]:active { transform: translateY(0) scale(.98); }
[data-testid^="stBaseButton"]:focus-visible { outline: 2px solid var(--gv-cyan); outline-offset: 2px; }

/* ---------- inputs ---------- */
[data-testid="stWidgetLabel"] p {
  font-family: var(--gv-ui);
  font-weight: 700;
  font-size: .95rem;
  letter-spacing: .05em;
  color: var(--gv-muted);
}
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div {
  background: rgba(9, 8, 22, .85);
  border-color: var(--gv-line);
  border-radius: 10px;
  transition: border-color .18s, box-shadow .18s;
}
[data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within,
[data-baseweb="select"] > div:focus-within {
  border-color: var(--gv-cyan);
  box-shadow: 0 0 0 3px rgba(34, 228, 255, .14), 0 0 20px -8px rgba(34, 228, 255, .8);
}

/* ---------- cards: expanders, forms, metrics, tables, alerts ---------- */
[data-testid="stExpander"] details {
  background: var(--gv-panel);
  border: 1px solid var(--gv-line);
  border-radius: 14px;
  overflow: hidden;
  backdrop-filter: blur(8px);
  transition: border-color .2s, box-shadow .2s;
}
[data-testid="stExpander"] details:hover {
  border-color: var(--gv-line-strong);
  box-shadow: 0 0 26px -14px rgba(139, 92, 246, .95);
}
[data-testid="stExpander"] details[open] { border-color: rgba(34, 228, 255, .42); }
[data-testid="stExpander"] summary:hover { background: rgba(139, 92, 246, .10); }
[data-testid="stExpander"] summary p { font-family: var(--gv-ui); font-weight: 700; font-size: 1.05rem; letter-spacing: .02em; }
[data-testid="stForm"] {
  background: var(--gv-panel);
  border: 1px solid var(--gv-line);
  border-radius: 16px;
  backdrop-filter: blur(8px);
}
[data-testid="stMetric"] {
  background: var(--gv-panel);
  border: 1px solid var(--gv-line);
  border-radius: 14px;
  padding: 14px 16px;
}
[data-testid="stMetricValue"] { font-family: var(--gv-display); text-shadow: 0 0 18px rgba(34, 228, 255, .45); }
@media (max-width: 640px) { [data-testid="stMetricValue"] { font-size: 1.75rem; } }
/* Value cards: show the help icon as an (i) instead of Streamlit's (?) */
[data-testid="stMetric"] [data-testid="stTooltipHoverTarget"] button {
  position: relative;
  color: var(--gv-cyan);
  opacity: .8;
  cursor: help;
  transition: opacity .15s, filter .15s;
}
[data-testid="stMetric"] [data-testid="stTooltipHoverTarget"] button svg path,
[data-testid="stMetric"] [data-testid="stTooltipHoverTarget"] button svg line { display: none; }
[data-testid="stMetric"] [data-testid="stTooltipHoverTarget"] button::after {
  content: "i";
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  font: 700 10px/1 Georgia, 'Times New Roman', serif;
  color: currentColor;
  pointer-events: none;
}
[data-testid="stMetric"] [data-testid="stTooltipHoverTarget"] button:hover {
  opacity: 1;
  filter: drop-shadow(0 0 6px rgba(34, 228, 255, .9));
}
[data-testid="stTooltipContent"] {
  max-width: 340px;
  font-family: var(--gv-body);
  line-height: 1.45;
  color: var(--gv-text);
  background: rgba(16, 13, 36, .97);
  border: 1px solid rgba(34, 228, 255, .45);
  border-radius: 12px;
  box-shadow: 0 14px 40px -12px rgba(0, 0, 0, .9), 0 0 24px -10px rgba(34, 228, 255, .7);
}
[data-testid="stMetricLabel"] p { font-family: var(--gv-ui); font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--gv-muted); }
[data-testid="stDataFrame"], [data-testid="stTable"] {
  border: 1px solid var(--gv-line);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 16px 36px -24px rgba(0, 0, 0, .95);
}
[data-testid="stAlertContainer"] { border-radius: 12px; border: 1px solid rgba(255, 255, 255, .07); backdrop-filter: blur(6px); }

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, rgba(22, 16, 50, .97), rgba(7, 6, 18, .97));
  border-right: 1px solid var(--gv-line);
}
.gv-player {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  margin-bottom: .8rem;
  border-radius: 14px;
  background: rgba(139, 92, 246, .10);
  border: 1px solid var(--gv-line);
}
.gv-avatar {
  flex: none;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  font-family: var(--gv-display);
  font-weight: 900;
  font-size: 1.2rem;
  color: #fff;
  background: linear-gradient(135deg, #7c3aed, #ff2e88);
  box-shadow: 0 0 22px -6px rgba(255, 46, 136, .9);
}
.gv-player-label { font-family: var(--gv-ui); font-weight: 700; font-size: .72rem; letter-spacing: .22em; color: var(--gv-muted); }
.gv-player-name { font-family: var(--gv-ui); font-weight: 700; font-size: 1.12rem; color: #fff; line-height: 1.15; word-break: break-all; }
.gv-badge {
  display: inline-block;
  margin-top: 4px;
  padding: 1px 8px;
  border-radius: 999px;
  font-family: var(--gv-ui);
  font-weight: 700;
  font-size: .7rem;
  letter-spacing: .16em;
  color: var(--gv-lime);
  border: 1px solid rgba(182, 255, 59, .4);
  background: rgba(182, 255, 59, .08);
}

/* ---------- hero banner ---------- */
.gv-hero {
  position: relative;
  overflow: hidden;
  margin: 0 0 1.1rem;
  padding: 28px 32px 24px;
  border-radius: 22px;
  border: 1px solid var(--gv-line);
  background:
    radial-gradient(560px 220px at 88% -10%, rgba(255, 46, 136, .32), transparent 70%),
    radial-gradient(640px 260px at -5% 110%, rgba(34, 228, 255, .20), transparent 70%),
    linear-gradient(135deg, rgba(40, 22, 92, .92), rgba(10, 8, 26, .94));
  box-shadow: 0 34px 80px -44px rgba(139, 92, 246, 1), inset 0 1px 0 rgba(255, 255, 255, .07);
}
.gv-hero::after {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: repeating-linear-gradient(0deg, rgba(255, 255, 255, .022) 0 1px, transparent 1px 3px);
}
.gv-hero-top { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.gv-brand { display: flex; align-items: center; gap: 18px; }
.gv-logo {
  flex: none;
  width: 60px;
  height: 60px;
  border-radius: 18px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #7c3aed, #ff2e88);
  box-shadow: 0 0 34px -4px rgba(255, 46, 136, .85), inset 0 0 0 1px rgba(255, 255, 255, .22);
}
.gv-logo svg { width: 38px; height: 38px; }
.gv-eyebrow { font-family: var(--gv-ui); font-weight: 700; font-size: .8rem; letter-spacing: .34em; text-transform: uppercase; color: var(--gv-cyan); }
.gv-title {
  margin-top: 2px;
  font-family: var(--gv-display);
  font-weight: 900;
  font-size: clamp(1.55rem, 3.1vw, 2.6rem);
  line-height: 1.05;
  letter-spacing: .05em;
  text-transform: uppercase;
  color: #fff;
}
.gv-title span {
  background: linear-gradient(90deg, var(--gv-cyan), var(--gv-violet), var(--gv-pink), var(--gv-cyan));
  background-size: 300% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  filter: drop-shadow(0 0 14px rgba(139, 92, 246, .55));
  animation: gv-shine 9s linear infinite;
}
.gv-clock {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  padding: 7px 14px;
  border-radius: 999px;
  font-family: var(--gv-ui);
  font-weight: 700;
  font-size: .85rem;
  letter-spacing: .16em;
  color: var(--gv-lime);
  border: 1px solid rgba(182, 255, 59, .35);
  background: rgba(182, 255, 59, .06);
}
.gv-clock i { width: 8px; height: 8px; border-radius: 50%; background: var(--gv-lime); box-shadow: 0 0 10px var(--gv-lime); animation: gv-pulse 1.8s ease-in-out infinite; }
.gv-sub { position: relative; margin: 12px 0 18px; max-width: 760px; color: var(--gv-muted); font-size: 1rem; }
.gv-stats { position: relative; display: grid; grid-template-columns: repeat(auto-fit, minmax(165px, 1fr)); gap: 12px; }
.gv-stat {
  position: relative;
  padding: 13px 15px 11px;
  border-radius: 14px;
  background: rgba(6, 5, 13, .55);
  border: 1px solid rgba(255, 255, 255, .07);
}
.gv-stat::before {
  content: "";
  position: absolute;
  top: 0;
  left: 15px;
  right: 15px;
  height: 2px;
  border-radius: 2px;
  background: var(--c);
  box-shadow: 0 0 12px var(--c);
}
.gv-stat b { display: block; font-family: var(--gv-display); font-size: 1.5rem; color: #fff; text-shadow: 0 0 18px var(--c); }
.gv-stat span {
  display: block;
  font-family: var(--gv-ui);
  font-weight: 700;
  font-size: .8rem;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--gv-muted);
  word-break: normal;
  overflow-wrap: normal;
}
@media (max-width: 700px) { .gv-hero { padding: 22px 18px; } }

/* ---------- login ---------- */
.gv-login-head { text-align: center; margin: 4vh 0 1.4rem; }
.gv-login-head .gv-logo { margin: 0 auto 16px; width: 74px; height: 74px; border-radius: 22px; }
.gv-login-head .gv-logo svg { width: 46px; height: 46px; }
.gv-login-head .gv-sub { margin: 10px auto 0; }

/* ---------- Recent Activity: developer bar ---------- */
.gv-devbar {
  margin: 14px 0 10px;
  padding: 9px 14px;
  border-radius: 10px;
  border: 1px solid var(--gv-line);
  border-left: 3px solid var(--gv-cyan);
  background: linear-gradient(90deg, rgba(139, 92, 246, .24), rgba(139, 92, 246, .03));
  font-family: var(--gv-ui);
  font-weight: 700;
  font-size: 1.3rem;
  letter-spacing: .03em;
}

/* ---------- scrollbars ---------- */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: linear-gradient(180deg, var(--gv-violet), var(--gv-pink)); border-radius: 8px; border: 2px solid var(--gv-bg); }

@keyframes gv-shine { to { background-position: 300% 0; } }
@keyframes gv-pulse { 50% { opacity: .35; transform: scale(.7); } }
@media (prefers-reduced-motion: reduce) {
  .gv-title span, .gv-clock i { animation: none; }
  [data-testid^="stBaseButton"] { transition: none; }
}
""".replace("__FONTS__", _FONTS)


def apply_theme():
    """Inject the stylesheet. Call once per run, right after st.set_page_config."""
    st.html(f"<style>{_CSS}</style>")


def _md(html_str):
    # One line, no indentation: Markdown would turn indented HTML into a code block.
    st.markdown(html_str, unsafe_allow_html=True)


def hero(stats):
    """Top banner: studio mark, app name, current PKT time and four live counters.

    stats: [(value, label, colour), ...]; a value of None shows as an em dash.
    """
    now = datetime.now(PKT).strftime("%a %d %b · %H:%M PKT").upper()
    tiles = "".join(
        f'<div class="gv-stat" style="--c:{color}"><b>{"—" if value is None else f"{value:,}"}</b>'
        f"<span>{html.escape(label)}</span></div>"
        for value, label, color in stats
    )
    _md(
        '<div class="gv-hero"><div class="gv-hero-top"><div class="gv-brand">'
        f'<div class="gv-logo">{_LOGO_SVG}</div><div>'
        f'<div class="gv-eyebrow">{html.escape(STUDIO_NAME)}</div>'
        f'<div class="gv-title">{APP_NAME_PLAIN} <span>{APP_NAME_GLOW}</span></div>'
        f'</div></div><div class="gv-clock"><i></i>{now}</div></div>'
        '<p class="gv-sub">Trace publishers through app-ads.txt, watch their catalogs, '
        "and catch every launch, transfer and takedown before anyone else does.</p>"
        f'<div class="gv-stats">{tiles}</div></div>'
    )


def login_header():
    _md(
        '<div class="gv-login-head">'
        f'<div class="gv-logo">{_LOGO_SVG}</div>'
        f'<div class="gv-eyebrow">{html.escape(STUDIO_NAME)}</div>'
        f'<div class="gv-title">{APP_NAME_PLAIN} <span>{APP_NAME_GLOW}</span></div>'
        '<p class="gv-sub">Sign in to enter the command center.</p></div>'
    )


def player_card(username, is_admin=False):
    name = username or "unknown"
    badge = '<span class="gv-badge">ADMIN</span>' if is_admin else ""
    _md(
        '<div class="gv-player">'
        f'<div class="gv-avatar">{html.escape(name[:1].upper())}</div>'
        '<div><div class="gv-player-label">SIGNED IN AS</div>'
        f'<div class="gv-player-name">{html.escape(name)}</div>{badge}</div></div>'
    )


def dev_bar(name):
    """Heading strip for one developer in Recent Activity."""
    _md(f'<div class="gv-devbar">🏢 {html.escape(name)}</div>')
