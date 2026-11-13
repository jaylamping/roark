"""Cut a Z range out of an STL so sheet.py draws it large: python zoom.py in.stl out.stl zlo zhi (open where it is cut)."""
import struct
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from sheet import read_stl          # noqa: E402

t = read_stl(sys.argv[1])
lo, hi = float(sys.argv[3]), float(sys.argv[4])
t = t[(t[:, :, 2].min(axis=1) >= lo) & (t[:, :, 2].max(axis=1) <= hi)].astype(np.float32)
with open(sys.argv[2], 'wb') as f:
    f.write(b'zoom'.ljust(80, b' '))
    f.write(struct.pack('<I', len(t)))
    for tri in t:
        f.write(struct.pack('<12fH', 0, 0, 0, *tri.ravel(), 0))
