"""Upper-arm clamshell file names in cad/ (conventions/cad.md section 4), keyed by the job names the scripts use."""
from pathlib import Path

CAD = Path(__file__).resolve().parents[2]
PARTS = CAD / 'upper-arm'
EXPORTS = CAD / 'exports' / 'upper-arm'
SIM = CAD / '_sim' / 'upper-arm'        # FEA models and results (gitignored)
GATE = CAD / '_wip' / 'arm-gate'         # mesh gate and support check output (gitignored)
MASTER = 'upper_arm_clam_master_left'
EXPORT = {
    'upper': 'upper_arm_shell_front_left',     # Z > 6, the front (flexion) half
    'lower': 'upper_arm_shell_back_left',      # Z < 6, the back half, all screw heads
    'ring': 'upper_arm_elbow_ring_left',
    'hub': 'upper_arm_hub_left',
    'clip': 'upper_arm_loop_clip_left',
    'carrier': 'upper_arm_spring_carrier_left',
}
