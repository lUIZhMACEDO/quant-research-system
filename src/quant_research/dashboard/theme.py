"""Dashboard palette and CSS."""

from __future__ import annotations

BG = "#000000"
CARD = "#0d1117"
ALT = "#111827"
BORDER = "#1a2235"
TEXT = "#d1d4dc"
DIM = "#6b7280"
GREEN = "#00d26a"
RED = "#f6465d"
AMBER = "#f0b90b"
BLUE = "#3b82f6"
WHITE = "#ffffff"
PURPLE = "#a78bfa"
CYAN = "#22d3ee"

# Moving starfield background (Streamlit .stApp override)
STARFIELD_CSS = """
<style>
.stApp {
    background-color: #000000 !important;
    background-image:
        radial-gradient(white, rgba(255,255,255,.2) 2px, transparent 4px),
        radial-gradient(white, rgba(255,255,255,.15) 1px, transparent 3px),
        radial-gradient(white, rgba(255,255,255,.1) 2px, transparent 4px) !important;
    background-size: 550px 550px, 350px 350px, 250px 250px !important;
    background-position: 0 0, 40px 60px, 130px 270px !important;
    animation: star-movement 100s linear infinite !important;
}

@keyframes star-movement {
    0% { background-position: 0 0, 40px 60px, 130px 270px; }
    100% { background-position: -550px 550px, -310px 410px, 120px 520px; }
}

header[data-testid="stHeader"] {
    background-color: transparent !important;
}
</style>
"""


def layout_css() -> str:
    """Typography, cards, badges and tab styling."""
    return f"""
<style>
    html, body, [class*="css"] {{ font-size: 16px; }}
    section[data-testid="stSidebar"] {{ background-color: {CARD}; }}
    section[data-testid="stSidebar"] * {{ font-size: 15px !important; }}
    .block-container {{
        padding-top: 0.5rem;
        background: transparent !important;
    }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 6px; background-color: {CARD}; border-radius: 10px; padding: 5px;
    }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 8px; color: {DIM}; font-weight: 700;
        font-size: 16px !important; padding: 12px 24px !important;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {ALT} !important; color: {WHITE} !important;
    }}
    [data-testid="stMetricLabel"] {{ font-size: 15px !important; color: {DIM}; font-weight: 700; }}
    [data-testid="stMetricValue"] {{ font-size: 2.2rem !important; font-weight: 900; color: {WHITE}; }}
    [data-testid="stMetricDelta"] {{ font-size: 1.1rem !important; }}
    .stock-card {{
        background: {CARD}; border: 1px solid {BORDER};
        border-radius: 14px; padding: 26px 30px; margin-bottom: 20px;
    }}
    .badge {{
        display: inline-block; padding: 6px 18px; border-radius: 7px;
        font-weight: 900; font-size: 15px; letter-spacing: 0.5px;
    }}
    .badge-buy   {{ background: {GREEN}22; color: {GREEN}; border: 1px solid {GREEN}44; }}
    .badge-sell  {{ background: {RED}22;   color: {RED};   border: 1px solid {RED}44; }}
    .badge-hold  {{ background: {DIM}33;   color: {TEXT};  border: 1px solid {DIM}55; }}
    .badge-trim  {{ background: {AMBER}22; color: {AMBER}; border: 1px solid {AMBER}44; }}
    .badge-watch {{ background: {AMBER}22; color: {AMBER}; border: 1px solid {AMBER}44; }}
    .kpi-label {{
        font-size: 12px; color: {DIM}; text-transform: uppercase;
        letter-spacing: 1.2px; margin-bottom: 4px; font-weight: 700;
    }}
    .kpi-value {{ font-size: 20px; font-weight: 900; line-height: 1.2; }}
    .card-info {{
        font-size: 15px !important; color: {TEXT}; line-height: 1.9;
        padding: 14px 18px; background: {ALT}; border-radius: 10px; margin-top: 12px;
    }}
    .card-timeline {{
        font-size: 15px !important; color: {TEXT}; line-height: 1.9;
        padding: 14px 18px; background: {ALT}; border-radius: 10px; margin-top: 12px;
    }}
    .timeline-label {{
        color: {CYAN}; font-weight: 800; font-size: 15px !important;
        margin-top: 8px; margin-bottom: 3px;
    }}
    .card-reason {{ font-size: 15px; color: {DIM}; font-style: italic; margin-top: 8px; }}
    .card-action {{ font-size: 16px; color: {AMBER}; font-weight: 800; margin-top: 8px; }}
    .card-ticker {{ font-size: 26px; font-weight: 900; color: {WHITE}; }}
    .card-name   {{ font-size: 15px; color: {DIM}; margin-left: 12px; }}
    .news-item {{
        padding: 12px 0; border-bottom: 1px solid {BORDER};
        font-size: 15px; color: {TEXT}; line-height: 1.7;
    }}
    .dataframe td, .dataframe th {{ font-size: 15px !important; padding: 12px 16px !important; }}
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {{ font-size: 16px !important; padding: 12px 14px !important;
        min-width: 80px; overflow: visible; }}
    .stNumberInput > div {{ overflow: visible !important; }}
    section[data-testid="stSidebar"] .stNumberInput input {{ min-width: 70px !important; }}
    section[data-testid="stSidebar"] .stNumberInput {{ margin-bottom: 1rem !important; }}
    .stNumberInput [data-testid="stCaptionContainer"] {{ display: none !important; }}
    label[data-testid="stWidgetLabel"] p {{ font-size: 16px !important; font-weight: 700; }}
    .stButton > button, .stFormSubmitButton > button {{
        font-size: 17px !important; font-weight: 800 !important;
        padding: 14px 32px !important; border-radius: 10px !important;
        white-space: nowrap !important; min-width: 120px !important;
    }}
    section[data-testid="stSidebar"] .stButton > button {{
        min-width: 100% !important; width: 100% !important;
    }}
    .hero-title {{
        font-size: 44px; font-weight: 900; color: {WHITE};
        letter-spacing: -0.5px; line-height: 1.2;
    }}
    .hero-sub {{
        font-size: 19px; color: {DIM}; margin-top: 12px; line-height: 1.7;
    }}
    .regime-banner {{
        border-radius: 10px; padding: 14px 20px; margin-bottom: 14px;
        font-size: 15px; font-weight: 700; letter-spacing: 0.3px;
    }}
    @keyframes live-pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:0.3}} }}
    .live-dot {{
        display:inline-block; width:10px; height:10px; border-radius:50%;
        background:{AMBER}; box-shadow:0 0 10px {AMBER};
        animation:live-pulse 1.5s ease-in-out infinite;
        margin-right:8px; vertical-align:middle;
    }}
    @keyframes ticker-scroll {{ 0%{{transform:translateX(0)}} 100%{{transform:translateX(-33.333%)}} }}
    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}
    header {{ visibility: hidden; }}
</style>
"""
