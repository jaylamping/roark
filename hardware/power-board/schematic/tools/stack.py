"""The rev B5 main board's layer stack (2026-11-09: 6 layers, cheaper at JLC than 4 layers with 2 oz outer), shared by the
plain-Python router and the KiCad-Python tools. Layer index = position in NAMES; routes.json and copper.json use it.
  L1 F.Cu  : parts, power pours, short escapes (2 oz)
  L2 In1   : solid GND (0.5 oz)
  L3 In2   : signal (Kelvin pairs, gates, UVLO run here between two GND planes)
  L4 In3   : signal
  L5 In4   : solid GND
  L6 B.Cu  : power mirrors, heatsink pads, GND fill (2 oz)
The 60 A path runs on the 2 oz outer pours, L1 and L6 together (LAYOUT_RULES.md). L1..L6 are physical positions;
KiCad calls them F.Cu, In1..In4, B.Cu."""
NAMES=['F.Cu','In1.Cu','In2.Cu','In3.Cu','In4.Cu','B.Cu']
NL=len(NAMES)
OUTER={0,NL-1}     # IPC-2221B external layers
GNDPLANE={1,4}     # never routed; they join GND for connectivity
ROUTABLE=[i for i in range(NL) if i not in GNDPLANE]
COST={0:1.0,2:1.0,3:1.05,5:1.1}   # grid_route.py step cost per routable layer: the inner signal layers sit between GND planes
assert OUTER<=set(ROUTABLE) and set(COST)==set(ROUTABLE)
CU_UM=[70.0,17.5,17.5,17.5,17.5,70.0]   # finished copper per layer, um: 2 oz outer, 0.5 oz inner (tools/pour_width.py)
# L1 to L2 dielectric, for the absorber loop model (absorber_loop.py): a larger h gives a larger loop inductance and a
# higher spike, so the model keeps the old 4-layer 0.2104 mm (JLC04161H-7628) until JLC confirms the 2 oz 6-layer stack.
# JLC's 1 oz 6-layer 1.6 mm stack uses one sheet of 2313 prepreg, about 0.1 mm; 2 oz outer copper may use thicker prepreg.
import os
H_L1_L2=float(os.environ.get('MARENGO_H_L1_L2_MM','0.2104'))*1e-3   # MARENGO_H_L1_L2_MM=0.0994: the thin-prepreg case, for comparison
# Zone clearance of the GND planes and fills on the four inner layers (In1-In4), mm. 0.6 mm (the old uncoated outer-layer
# rule) cut the planes away under every fine-pitch via row; 0.3 mm keeps them solid there. IPC-2221B B1 (internal
# conductors, 51-100 V) asks 0.1 mm. A 0.6/0.3 mm via then has 0.45 mm from its drill to the plane (every via and plated
# pad on this board keeps its inner lands). tools/route_power.py builds the zones with it, tools/plane_clearance.py sets
# it on a routed board, tools/route_checks.py check 6 tests it. The outer GND fills (L1, L6) keep a 0.6 mm zone
# clearance (tools/route_power.py), more than the coated board's 0.2 mm rule asks.
PLANE_CLEAR=0.3
def kicad_layers(pcbnew):
    """pcbnew layer IDs in index order"""
    L=[pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.In3_Cu,pcbnew.In4_Cu,pcbnew.B_Cu]
    assert len(L)==NL
    return L
def check_board(b):
    """stop if a board doesn't have this stack's copper layer count (a stale 4-layer board or work dir)"""
    n=b.GetCopperLayerCount()
    assert n==NL,f'the board has {n} copper layers; tools/stack.py has {NL}: rebuild it from place (tools/build_board.sh)'
def check_json(d,what):
    """stop if a copper.json or routes.json was written for another layer stack"""
    assert d.get('layers')==NAMES,f'{what} was written for layers {d.get("layers")}, not {NAMES}: rerun it'
def via_name():
    """KiCad's Specctra name for the 0.6/0.3 mm through via on this stack"""
    return f'Via[0-{NL-1}]_600:300_um'
