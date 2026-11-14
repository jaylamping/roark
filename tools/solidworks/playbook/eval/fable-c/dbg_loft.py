import sys
from c2_build import *
tests = [('mid', BONE[3:9]), ('from3', BONE[3:]), ('mid2', BONE[3:9]), ('first4', BONE[:4]), ('first4b', BONE[:4]), ('all', BONE), ('all2', BONE), ('from1', BONE[1:]), ('from2', BONE[2:])]
with job() as j:
    for k, rows in tests:
        d = new_part(j.sw, OUT / f'dbg_{k}.SLDPRT')
        try:
            loft_of(d, rows, 'L')
            log('OK', k, volume(d))
        except Failed as ex:
            log('FAIL', k)
        close(j.sw, d)
