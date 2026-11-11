# Upper arm (concept A): print settings checklist

Five plates for the Bambu P2S. Each `.3mf` here is a sliced project. All of them carry the settings of the last accepted upper
arm print (marengo `hardware/designs/left-arm/prints/upper-arm/upper_arm.3mf`, released 2026-11-07). Only the parts and the
infill of the ring and the coupons are different.

## Before each plate

1. Load **white PETG**. Select the **Generic PETG** filament profile.
2. Fit the **0.4 mm High Flow** nozzle.
3. Fit the **Cool Plate SuperTack** plate, clean, with **no glue**.
4. Open the `.3mf` with **File > Open Project**, not Import. Don't move or rotate anything: the part is already the right way
   up.
5. If Bambu Studio asks whether to keep the project's settings or load the presets, **keep the project's settings**.

## Check these before you press Print

| Setting | Should read | Where |
| --- | --- | --- |
| Printer | Bambu Lab P2S, 0.4 nozzle, **High Flow** | top left |
| Plate | **Cool Plate SuperTack**, 70 °C | plate type |
| Filament | Generic PETG, nozzle 255 °C | filament |
| Process | 0.20 mm Standard | process |
| Walls | **6** | Strength > Walls |
| Walls, stub coupon | **3** (a fit coupon) | Strength > Walls |
| Sparse infill | **50% zig-zag** on the halves; **100%** on the ring and the key coupon; **15%** on the stub coupon | Strength > Sparse infill |
| Infill modifier | on each half, a part called **loaded_zones_100** under the object, at **100%** | object list |
| Supports | **on**, **tree(auto)**, style **Tree Hybrid**, threshold 45° | Support |
| Brim | halves and coupons: **outer only**, **5 mm**; ring: **none** (a brim flashes the key-slot flanks) | Others > Brim |

Anything that doesn't match: stop and tell me. Bambu Studio has reset saved settings on open before. Every value above is
also listed in the project as one we changed on purpose, which should stop that.

## Plates

| Order | File | Down on the plate | Time | Filament |
| --- | --- | --- | --- | --- |
| 1 | `upper_arm_organic_ring.3mf` | the RS02 face (smooth flat side), no brim | 56 min | 18.5 g |
| 2 | `upper_arm_organic_back.3mf` | the seam face | 5 h 09 min | 119 g |
| 3 | `upper_arm_organic_front.3mf` | the seam face | 4 h 35 min | 105 g |
| (test) | `upper_arm_organic_key_coupon.3mf` | the seam face, like the back half | 33 min | 10 g |
| (done) | `upper_arm_organic_stub_coupon.3mf` | both half-stubs, cut face down | 37 min | 6.4 g |

Times and weights are from Bambu Studio's own slice (2.09.01.70, R1, 2026-11-11), support and brim included.

**Stub coupon: done, 2026-11-11.** Joey printed it (3 walls, 15%) and a 6808 inner race fits perfectly on the two
half-stubs with the seam closed. No caliper reading was taken. The Ø40.0 stub stays as modelled. The coupon file is kept
for reference.

## After printing

- **Ring:** support only goes into the three 3 mm pockets on the bed face, beside the plug window and at the bottom. Those
  pockets clear the screw heads on the RS02's socket tabs, so pick out all the support, but they aren't fit faces.
- **Halves:** support fills the inside of the drum and the neck. All of that is hidden once the arm is closed: the slicer
  check found 0 mm² of support on a face you can see. Take it out in small pieces through the open seam.
- **Insert holes** (front half): clear them with a Ø4.0 drill by hand before pressing in the Ruthex M3 × 5.7 inserts.
- **Keys:** each key in the halves has two small crush ribs on its bearing side, 0.15 mm proud of a tight fit. Don't sand
  them off. The first time the ring goes in, it shaves them down to a fit with no play. The ring needs a firm push the first
  time, and comes out again for service with no tools. If it drops in loose the first time, tell me.
