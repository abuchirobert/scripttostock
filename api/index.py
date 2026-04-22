"""
Vercel Python entrypoint.
Vercel's @vercel/python runtime auto-detects the `app` WSGI variable.
All routes are rewritten here via vercel.json.
"""
import sys
import os

# Allow importing the sibling module from the repo root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Import the Flask app (WSGI-compatible). Vercel auto-detects this.
from script_to_stock import app  # noqa: E402,F401
