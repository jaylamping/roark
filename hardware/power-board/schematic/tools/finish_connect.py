"""Connect two explicit same-net pad components, avoiding zone-island ambiguity.

KiCad python finish_connect.py INPUT OUTPUT SRC_REF SRC_PAD DST_REF DST_PAD
Uses whole connected components as exact routing anchors. Optional SHOVE=1
permits finish_shove's transactional displacement. No Kelvin nets are accepted.
Refill with full custom rules using kicad-cli and validate the result afterwards.
"""
import sys,os
from finish_route import Router,UID,XY,RL
from finish_shove import shove
r=Router(sys.argv[1]); aa=[]
for ref,num in ((sys.argv[3],sys.argv[4]),(sys.argv[5],sys.argv[6])):
    f=r.b.FindFootprintByReference(ref); p=next(p for p in f.Pads() if p.GetNumber()==num)
    aa.append(p)
assert aa[0].GetNetname()==aa[1].GetNetname()
n=aa[0].GetNetname(); assert not n.startswith('/SH')
A=[(XY(aa[0].GetPosition()),L) for L in RL if aa[0].IsOnLayer(L)]
B=[(XY(aa[1].GetPosition()),L) for L in RL if aa[1].IsOnLayer(L)]
A0,B0=A,B
A=r.component_anchors({'uuid':UID(aa[0])},B0,A0); B=r.component_anchors({'uuid':UID(aa[1])},A0,B0)
print('explicit connection',n,sys.argv[3:7],flush=True)
items=r.simple(n,A,B) or r.maze(n,A,B)
if items:
    r.commit(n,items); r.save(sys.argv[2]); print('explicit connection routed',flush=True)
elif os.getenv('SHOVE')=='1' and shove(r,n,A,B):
    r.save(sys.argv[2]); print('explicit connection shoved',flush=True)
else: print('explicit connection failed; no output saved',flush=True)
