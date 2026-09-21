"""Look and small shared pieces: palette, typography, cards, flash messages."""

from __future__ import annotations

import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --ink: #0F172A; --muted: #64748B; --line: #E2E8F0;
  --brand: #0F766E; --brand-soft: #CCFBF1; --card: #FFFFFF; --page: #F6F7F9;
}
html, body, [class*="css"], .stMarkdown, .stText, label, p, span, div {
  font-family: 'Inter', system-ui, sans-serif;
}
.stApp { background: var(--page); }
.block-container { padding-top: 2.2rem; max-width: 1100px; }

h1, h2, h3 { color: var(--ink) !important; letter-spacing: -0.02em; }
p, label, .stMarkdown p { color: var(--ink) !important; }

.stMarkdown p.page-title {
  font-size: 1.9rem !important; font-weight: 700; color: var(--ink) !important;
  margin: 0; letter-spacing: -0.02em; line-height: 1.2;
}
.stMarkdown p.page-sub { color: var(--muted) !important; margin: 0.3rem 0 1.4rem; font-size: 0.98rem; }
.muted { color: var(--muted) !important; font-size: 0.88rem; }

/* cards: forms, and bordered containers created with a key starting "card" */
div[class*="st-key-card"], div[data-testid="stForm"] {
  background: var(--card); border: 1px solid var(--line) !important;
  border-radius: 14px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.card-title { font-weight: 600; font-size: 1.02rem; color: var(--ink); margin: 0; }
.pill {
  display: inline-block; padding: 0.12rem 0.6rem; border-radius: 999px;
  font-size: 0.78rem; font-weight: 600; margin-right: 0.35rem;
  background: var(--brand-soft); color: var(--brand) !important;
}
.pill.off { background: #F1F5F9; color: var(--muted) !important; }
.pill.warn { background: #FEF3C7; color: #92400E !important; }

.stTabs [data-baseweb="tab-list"] { gap: 0.25rem; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"] { font-weight: 500; color: var(--muted); padding: 0.6rem 0.9rem; }
.stTabs [aria-selected="true"] { color: var(--brand) !important; }

div[data-testid="stForm"] { padding: 1.1rem 1.2rem; }
.stMarkdown p.card-title { font-size: 1.05rem !important; margin-bottom: 0.3rem; }

.stButton button[kind="primary"], .stFormSubmitButton button {
  background: var(--brand); border: none; border-radius: 10px; padding: 0.45rem 1.1rem;
}
/* the generic p colour above would otherwise turn button labels dark */
.stButton button[kind="primary"] p, .stFormSubmitButton button p {
  color: #FFFFFF !important; font-weight: 600;
}
.stButton button[kind="primary"]:hover, .stFormSubmitButton button:hover { background: #115E59; }
.stButton button[kind="secondary"] { border-radius: 10px; border-color: var(--line); }
section[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid var(--line); }
.brand { font-weight: 700; font-size: 1.1rem; color: var(--ink); }
.brand span { color: var(--brand); }
</style>
"""


def apply() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def header(title: str, subtitle: str = "") -> None:
    st.markdown(f'<p class="page-title">{title}</p>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<p class="page-sub">{subtitle}</p>', unsafe_allow_html=True)


def card(key: str):
    """A white bordered card. Keys must be unique on the page."""
    return st.container(border=True, key=f"card_{key}")


def pill(text: str, kind: str = "") -> str:
    return f'<span class="pill {kind}">{text}</span>'


def flash(message: str) -> None:
    """Show a success message after the next rerun (st.rerun wipes st.success)."""
    st.session_state["_flash"] = message


def show_flash() -> None:
    if message := st.session_state.pop("_flash", None):
        st.toast(message, icon="✅")
