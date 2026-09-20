"""Entry → MARSAD dashboard"""
import runpy, sys
from pathlib import Path
dashboard = Path(__file__).resolve().parent / "dashboard.py"
sys.argv[0] = str(dashboard)
runpy.run_path(str(dashboard), run_name="__main__")
