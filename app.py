"""Streamlit entry point: ``streamlit run app.py``. The dashboard lives in ``src/quant_research/dashboard``."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from quant_research.dashboard.app import main  # noqa: E402

main()
