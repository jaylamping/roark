"""Build link_organic from c2v2, save, export STEP + STL, report volume. Usage: finalize.py [out_name]"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from c2v2 import *
if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else 'link_organic'
    with job() as j:
        d = final(j, out)
        v = volume(d)
        log('volume', v, 'bodies', bodies(d), 'errors', feature_errors(d))
        single_body(d)
        export(j.sw, d, WIP / f'{out}.stl'); export(j.sw, d, WIP / f'{out}.step'); save(d); close(j.sw, d)
