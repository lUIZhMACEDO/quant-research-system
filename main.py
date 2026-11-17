"""Daily report entry point: ``python main.py``. Logic lives in ``quant_research.reporting.daily``."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from quant_research.reporting.daily import main  # noqa: E402

if __name__ == "__main__":
    main()
