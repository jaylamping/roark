13. **`swkit.call()` fails on any member that returns a COM object** (`GetFirstDisplayDimension`): the object is
    callable, so `call()` calls it and gets "Member not found". 02-com.md rule 5 recommends `call()` without this
    limit. It cost D3 a launch.
14. **04-export.md gives no tolerance for "STL sits in the model frame".** On a round part the facets fall up to
    0.08 mm inside the true box; a strict comparison reports a good export as bad.

## Files

Pictures (each opened and looked at after it was made):
`pictures/d1_buck_mount.png`, `d1_assembly_idea_a.png`, `d1_board_out.png`, `d1_mount_on_rail.png`,
`d1_idea_b_snap.png`, `d2_housing_upper.png`, `d2_housing_lower.png`, `d2_pair.png`, `d2_pair_open.png`,
`d3_part_one.png`, `d3_part_two.png`.

