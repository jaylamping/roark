import re, sys
def rows(f):
    out = {}
    for ln in open(f, encoding='utf-8', errors='replace'):
        m = re.match(r'(arm|hub)\s+(.+?)\s+(vm|layer|shear)\s+peak.*worst avg \.5/1/2 SF (\S+)', ln)
        if m:
            out[(m.group(1), m.group(2).strip(), m.group(3))] = m.group(4)
    return out
for case in sys.argv[1:]:
    a, b = rows(f'cad/_sim/{case}/post.txt'), rows(f'cad/_sim/{case}/post_allc.txt')
    print('==', case)
    for k in b:
        if k not in a: continue
        va = [float(x) if x != '-' else 99 for x in a[k].split('/')]
        vb = [float(x) if x != '-' else 99 for x in b[k].split('/')]
        if any(y < x - 0.005 for x, y in zip(va, vb)) and min(vb) < 3.0:
            print(f'  {k[0]} {k[1][:46]:46s} {k[2]:5s} old {a[k]:18s} all-centres {b[k]}')
