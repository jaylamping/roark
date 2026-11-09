"""The rev B5 main board's layer stack (2026-11-09: 6 layers, cheaper at JLC than 4 layers with 2 oz outer), shared by the
plain-Python router and the KiCad-Python tools. Layer index = position in NAMES; routes.json and copper.json use it.
  L1 F.Cu  : parts, power pours, short escapes (1 oz)
  L2 In1   : solid GND (0.5 oz)
  L3 In2   : signal (Kelvin pairs, gates, UVLO run here between two GND planes)
  L4 In3   : signal
  L5 In4   : solid GND
  L6 B.Cu  : power mirrors, heatsink pads, GND fill (1 oz)
The 60 A path is carried by soldered copper bars, not the 1 oz pours (LAYOUT_RULES.md, "Power path")."""
NL=6
NAMES=['F.Cu','In1.Cu','In2.Cu','In3.Cu','In4.Cu','B.Cu']
OUTER={0,5}        # IPC-2221B external layers
GNDPLANE={1,4}     # never routed; they join GND for connectivity
ROUTABLE=[0,2,3,5]
# L1 to L2 dielectric: JLC's 6-layer 1.6 mm stackup uses one sheet of 2313 prepreg, about 0.1 mm (JLC help centre, "PCB
# Stackup"; confirm with JLC's impedance calculator before ordering). The absorber loop model uses it.
H_L1_L2=0.10e-3
def kicad_layers(pcbnew):
    """pcbnew layer IDs in index order"""
    return [pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.In3_Cu,pcbnew.In4_Cu,pcbnew.B_Cu]
