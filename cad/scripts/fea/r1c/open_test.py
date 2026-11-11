"""Open a part in this session's own instance (ARM_SW_DIR) and print OpenDoc6 errors/warnings and the body count.
python open_test.py PATH"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path('J:/code/roark-wt/left-arm-organic/cad/scripts/arm')))
from swlib import app
from win32com.client import VARIANT
import pythoncom
sw = app()
e = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
w = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
sw.CloseAllDocuments(True)
d = sw.OpenDoc6(sys.argv[1], 1, 1, '', e, w)
print('open', d is not None, 'errors', e.value, 'warnings', w.value, flush=True)
if d is not None:
    bs = d.GetBodies2(0, True)
    print('bodies', len(bs) if bs else 0, flush=True)
    sw.CloseDoc(d.GetTitle)
