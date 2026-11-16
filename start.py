#!/usr/bin/env python3
"""Double-click launcher; reuses an existing local runtime when available."""
from pathlib import Path
import json,os,subprocess,sys,urllib.request,webbrowser
ROOT=Path(__file__).resolve().parent
URL="http://127.0.0.1:8765"
try:
    with urllib.request.urlopen(URL+"/api/health",timeout=1) as r:
        import json
        if r.status==200 and str(json.load(r).get("version","")).startswith("long-view-"):webbrowser.open(URL);sys.exit(0)
except Exception:pass
try:preferences=json.loads((Path(os.environ.get('LONG_VIEW_DATA_DIR',ROOT/'data'))/'preferences.json').read_text())
except (OSError,ValueError):preferences={}
configured=os.environ.get('LONG_VIEW_PYTHON') or preferences.get('python')
candidates=[Path(configured)] if configured else []
venv_python=ROOT/".venv"/("Scripts/python.exe" if os.name=="nt" else "bin/python")
candidates += [venv_python,Path(sys.executable)]
runtime=None
for p in candidates:
    if p.exists() and subprocess.run([str(p),"-c","import numpy"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:runtime=p;break
if runtime is None:
    subprocess.run([sys.executable,"-m","venv",str(ROOT/".venv")],check=True);runtime=venv_python
    subprocess.run([str(runtime),"-m","pip","install","-r",str(ROOT/"requirements.txt")],check=True)
os.chdir(ROOT)
os.execv(str(runtime),[str(runtime),str(ROOT/"server.py"),"--port","8765","--open"])
