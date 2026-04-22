"""
Netlify Function entrypoint for the Flask app.

Netlify runs this as an AWS Lambda function. We bridge Flask (WSGI) → Lambda
event/response using `serverless-wsgi`.

Timeout warning: Netlify synchronous functions cap at 10s (free) / 26s (paid).
This app's /api/generate endpoint takes 1-4 minutes for real scripts and
WILL TIME OUT on Netlify. Key-test and static endpoints still work.
For a working deploy, use Vercel Pro (60s), Render, Railway, or Fly.io.
"""
import os
import sys

# Make the sibling modules importable (we copy script_to_stock.py next to this file
# during Netlify's function packaging — see netlify.toml + requirements.txt).
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import serverless_wsgi  # noqa: E402
from script_to_stock import app  # noqa: E402


def handler(event, context):
    """Lambda handler invoked by Netlify on every request."""
    return serverless_wsgi.handle_request(app, event, context)
