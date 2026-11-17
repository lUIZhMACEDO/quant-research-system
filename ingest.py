"""EOD ingest entry point: ``python ingest.py``. Logic lives in ``quant_research.ingest.pipeline``."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from quant_research.ingest.pipeline import main  # noqa: E402

if __name__ == "__main__":
    main()
