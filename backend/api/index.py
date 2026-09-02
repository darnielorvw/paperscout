import os
import sys

# main.py lives one directory up (backend/) and imports its modules
# (database, services, config, ...) as top-level packages, so that directory
# needs to be on sys.path before we can import it from here.
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from main import app  # noqa: E402  (Vercel's Python runtime expects `app`)
