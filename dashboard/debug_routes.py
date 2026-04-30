
import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from dashboard.api import app

for route in app.routes:
    print(f"{route.path} {getattr(route, 'methods', 'MOUNT')}")
