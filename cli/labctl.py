"""CLI entrypoint shortcut for labctl."""
import sys
from pathlib import Path

# Add cli directory to sys.path so labctl module is findable directly
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from labctl.main import main

if __name__ == "__main__":
    main()
