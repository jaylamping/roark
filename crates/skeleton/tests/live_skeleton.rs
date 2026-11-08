//! The committed skeleton loads. This is the only test that reads `config/skeleton.yaml`, and it asserts no values from
//! it (testing.md rule 3): the hardware side changes them, and a value test would go red for no software reason.

use std::path::Path;

/// Guards: safety - the runtime refuses to start on an invalid skeleton (architecture.md section 5), so the committed file must pass every loader check.
#[test]
fn committed_skeleton_loads() {
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../config/skeleton.yaml");
    let result = skeleton::load(&path);
    assert!(
        result.is_ok(),
        "{}",
        result.err().map(|e| e.to_string()).unwrap_or_default()
    );
}
