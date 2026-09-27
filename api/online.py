import os
import sys
from pathlib import Path
os.environ['MARASSIM_DB_BACKEND']='sqlite'
os.environ['MARASSIM_DB_PATH']=':memory:'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop/server'))
from cloud_web import handler as OnlineHandler

class handler(OnlineHandler):
    """Explicit Vercel file-based Python entrypoint."""
    pass
