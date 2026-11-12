"""Print exact baseline/final routing counts from KiCad DRC JSON reports.

Plain Python finish_report.py BASELINE_DRC FINAL_DRC
Reports every violation type, parity issue type, fully closed and still-open
nets, and connection-count changes. No board edits or inferred counts.
"""
import sys,json,re,collections
a,b=[json.load(open(p,encoding='utf-8')) for p in sys.argv[1:3]]
def nets(d): return collections.Counter(re.search(r'\[([^]]+)\]',u['items'][0]['description'])[1] for u in d['unconnected_items'])
A,B=nets(a),nets(b)
print('baseline unconnected_items:',len(a['unconnected_items']),'nets:',len(A))
print('final unconnected_items:',len(b['unconnected_items']),'nets:',len(B))
print('connections reduced:',len(a['unconnected_items'])-len(b['unconnected_items']))
for name,d in (('baseline',a),('final',b)):
    c=collections.Counter(v['type'] for v in d['violations'])
    print(name,'DRC violation counts:',dict(sorted(c.items())))
    print(name,'clearance violations:',c['clearance'])
    p=collections.Counter(v['type'] for v in d['schematic_parity'])
    print(name,'schematic parity issues:',len(d['schematic_parity']),'by type:',dict(sorted(p.items())))
    print(name,'schematic parity errors:',sum(v['severity']=='error' for v in d['schematic_parity']))
def parity(d): return {(v['type'],v['description'],tuple(i['uuid'] for i in v['items'])) for v in d['schematic_parity']}
print('schematic parity unchanged:',parity(a)==parity(b))
print('fully closed nets:',', '.join(sorted(set(A)-set(B))))
print('partially closed nets:',', '.join(f'{n} ({A[n]} -> {B[n]})' for n in sorted(B) if B[n]<A[n]))
print('still open:',', '.join(f'{n} ({B[n]})' for n in sorted(B)))
print('newly open nets:',', '.join(sorted(set(B)-set(A))) or 'none')
