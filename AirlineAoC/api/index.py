import os
import sys

# Add the root directory to the python path so it can find 'backend'
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.main import app

# Vercel needs the app object to be named 'app'
