+++
link = "upper_arm"
region = "upper-arm"

[[print]]
part = "upper arm, one piece (now the clamshell master, upper_arm_clam_master_left)"
revision = "draft 2"
cad = "marengo db71b23b"
date = "2026-11-08"
printer = "P2S, 0.4 mm high flow"
material = "PETG"
plate = "Cool Plate Super Tack"
settings = "6 walls, 50% with 100% modifiers on the hoop, seat, corners and hub (3MF marengo 612b5e08); tree supports; laid flat"
mass_g = 202
mass_sliced_g = 229.0
fit = ["RS02 seats well, except its housing tab: the tab lip interferes by about 1 mm (Joey: \"fits great except for this tab bit\"); the CAD shows 0.84 mm against the vendor model"]
surface = ["Rough outer skin on every supported face", "Support trapped in the enclosed cavity, nearly impossible to clear through the small door"]
post_work = "none recorded"
action = "Clamshell redesign printed upright with no trap door, lighter; RS02 seat pocket run through to the face"
action_commit = "marengo a6315f0c; roark PR #28 (draft 3)"
source = "Joey in the left-arm thread, 2026-11-08 around 02:13Z, with photos in that thread; mass_sliced_g is the draft 3 README's re-slice on the same process"

[[lesson]]
id = "rs02-housing-tab"
applies_to = ["rs02"]
text = "The RS02 housing tab lip reached about 1 mm into the printed seat of the one-piece upper arm. Check printed seats against the vendor RS02 model including the tab (gate interference check, list the RS02 under mates), and run seat pockets through to the face."

[[lesson]]
id = "slicer-mass-high"
applies_to = ["upper-arm", "forearm"]
text = "Bambu Studio's mass estimate read 13% high on the one-piece upper arm (229.0 g sliced, 202 g weighed). Until more prints are logged, expect weighed mass of about 0.88 x sliced for PETG arm links at these settings."
+++

# Upper arm: print log

What each printed revision of the upper arm taught us. Format and rules:
[conventions/part-lifecycle.md](../../../conventions/part-lifecycle.md) section 4. Newest first.

## Draft 2, one piece (marengo db71b23b), 2026-11-08

Backfilled 2026-11-09 from the left-arm thread; the photos are in that thread, not in the repo.

- **Mass:** 202 g on the scale; the slicer said 229.0 g. Joey: too heavy.
- **Fit:** the RS02 seats well, except its housing tab lip, which interferes by about 1 mm.
- **Surface:** printed lying flat, every supported outer face came out rough, and support got trapped in the enclosed
  cavity behind the small door.
- **What it changed:** the rules to print outer faces clean and to make enclosed links fastened clamshells (Joey
  2026-11-08 02:13Z), and the draft 3 clamshell in [cad/upper-arm/README.md](../../upper-arm/README.md).
