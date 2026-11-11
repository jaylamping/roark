"""hv_buck.py: the buck board's 54 V nets, the one list (plain Python, no KiCad needed). Copper at or switching up to the
input voltage: VIN_P, VIN, VIN_C, SW, HO, BST, BST_R, ILIM (on SW through 330R) and EN / ON_N (on VIN through 300k / 220k).
Used by tools/spacing_buck.py (SP_EN keeps SP_MIN to these), by tools/build_buck.sh (the routers' 54 V list,
PB_HV_EXTRA) and named in BUCK_LAYOUT.md. `python hv_buck.py` prints the list comma-separated, without the '/'."""
HV=('/VIN_P','/VIN','/VIN_C','/SW','/HO','/BST','/BST_R','/ILIM','/EN','/ON_N')
SP_RULE=1.5   # mm: the main board's E-stop rule (tools/domains.py), every layer
SP_MIN=1.7    # mm: what this board keeps, the rule plus 0.2 mm for etch and registration tolerance
if __name__=='__main__':
    print(','.join(n.lstrip('/') for n in HV))
