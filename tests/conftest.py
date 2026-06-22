"""Make the bot's modules (which use bare imports) importable from tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
