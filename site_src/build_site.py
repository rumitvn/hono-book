#!/usr/bin/env python3
"""Entry point — kept so `python3 site_src/build_site.py` works as documented.

The renderer lives in engine.py (identical in every RumitX book); everything
specific to this book lives in book.py.
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import main

if __name__ == "__main__":
    main()
