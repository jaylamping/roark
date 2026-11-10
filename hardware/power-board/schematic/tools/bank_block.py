"""bank_block.py: the positions of tools/place.py's 'bankctl' group (bank B's controller U1 and its parts, the gate
resistors R1 and R2, the MID dividers, their test points) as they are on the routed board, for a rebuild.
On 2026-11-10 R2 moved from the controller to the GATE tee beside R1, and R34 moved 1.66 mm west to make room, so
that G2 runs 29 mm with 2 vias (55.8 mm and 3 before). With parts moved by hand the packer would place the rest of the
group differently, so tools/place.py takes the whole group from PLACE_ALL: courtyard centre, pad 1, rotation, page mm.
The table is written by reading the board. The copper is in tools/hand_laid.specs (G2, the tee's leg)."""
import blocks
PLACE_ALL={'R63':((127.750,154.800),(127.750,157.762),90), 'TP3':((127.564,166.270),(127.563,166.270),90), 'C1':((121.320,168.970),(121.320,170.445),90),
 'R54':((121.650,162.400),(121.650,165.363),90), 'R55':((131.035,131.200),(131.035,132.025),90), 'R56':((128.593,133.643),(128.593,134.468),90),
 'C43':((130.493,134.600),(130.493,135.375),90), 'Q13':((122.550,154.550),(120.645,157.450),90), 'R33':((124.490,168.950),(124.490,170.412),90),
 'R34':((126.680,163.200),(125.218,163.200),0), 'D12':((124.470,144.420),(124.470,146.070),90), 'D17':((128.410,148.470),(126.760,148.470),0),
 'R52':((121.300,145.250),(121.300,147.562),90), 'TP6':((127.559,169.710),(127.557,169.710),0), 'C2':((130.477,169.907),(130.477,170.857),90),
 'U1':((141.750,127.400),(143.850,128.400),180), 'R1':((131.375,160.200),(131.375,161.025),90), 'R2':((129.800,163.175),(129.800,162.350),270),
 'R3':((128.593,137.043),(128.593,137.868),90), 'R4':((126.693,140.080),(126.693,140.905),90), 'R5':((120.450,140.080),(120.450,140.905),90),
 'R6':((120.670,136.440),(120.670,137.352),90), 'C3':((124.840,130.450),(124.065,130.450),0), 'C4':((121.320,132.020),(121.320,133.495),90),
 'D2':((128.410,145.960),(126.760,145.960),0), 'Q3':((123.990,136.460),(123.052,135.510),0), 'TP10':((128.864,130.721),(128.865,130.721),0),
 'TP12':((122.620,139.600),(122.621,139.600),90), 'TP14':((130.506,165.771),(130.508,165.771),0)}
def place(fps):
    for ref,(c,p1,rot) in PLACE_ALL.items():
        if p1 is None or (abs(p1[0]-c[0])<0.05 and abs(p1[1]-c[1])<0.05):
            fps[ref].SetOrientationDegrees(rot); blocks.place_fp(fps[ref],c,None)
        else: blocks.place_fp(fps[ref],c,p1,tol=0.08)
