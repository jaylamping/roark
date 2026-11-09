//! The `sim-drive` binary: `sim-drive [--skeleton <file>] [--seed <n>] [--bus <name>]...`. What it does and how to
//! run it: the crate README (`bins/sim-drive/README.md`).

#[cfg(target_os = "linux")]
fn main() -> Result<(), String> {
    linux::main()
}

#[cfg(not(target_os = "linux"))]
fn main() -> Result<(), String> {
    Err("sim-drive runs only on Linux, where vcan exists; see docs/dev-box.md".to_owned())
}

#[cfg(target_os = "linux")]
mod linux {
    use std::path::PathBuf;
    use std::sync::atomic::AtomicBool;

    use robstride::{Drive, Uid};
    use sim_drive::{SimDrive, serve};

    struct Args {
        skeleton: PathBuf,
        seed: u64,
        buses: Vec<String>,
    }

    fn args() -> Result<Args, String> {
        let mut args = Args {
            skeleton: PathBuf::from("config/skeleton.yaml"),
            seed: 0,
            buses: Vec::new(),
        };
        let mut it = std::env::args().skip(1);
        while let Some(flag) = it.next() {
            let mut value = || it.next().ok_or(format!("{flag} needs a value"));
            match flag.as_str() {
                "--skeleton" => args.skeleton = PathBuf::from(value()?),
                "--seed" => args.seed = value()?.parse().map_err(|e| format!("--seed: {e}"))?,
                "--bus" => args.buses.push(value()?),
                other => {
                    return Err(format!(
                        "unknown argument {other}; usage: sim-drive [--skeleton <file>] [--seed <n>] [--bus <name>]..."
                    ));
                }
            }
        }
        Ok(args)
    }

    pub(super) fn main() -> Result<(), String> {
        let args = args()?;
        let skeleton = skeleton::load(&args.skeleton).map_err(|e| e.to_string())?;
        let buses: Vec<_> = skeleton
            .buses
            .iter()
            .map(|b| b.name.as_str().to_owned())
            .filter(|name| args.buses.is_empty() || args.buses.contains(name))
            .collect();
        if let Some(missing) = args.buses.iter().find(|b| !buses.contains(b)) {
            return Err(format!(
                "{missing} is not a bus in {}",
                args.skeleton.display()
            ));
        }
        for bus in &buses {
            sim_drive::ensure_vcan(bus).map_err(|e| e.to_string())?;
        }
        let stop = AtomicBool::new(false);
        std::thread::scope(|scope| {
            let threads: Vec<_> = buses
                .iter()
                .zip(0u64..)
                .map(|(bus, n)| {
                    let mut drives = drives(&skeleton, bus, n, args.seed);
                    let stop = &stop;
                    std::thread::Builder::new()
                        .name(format!("sim-{bus}"))
                        // The binary schedules no faults, so nothing is ever injected.
                        .spawn_scoped(scope, move || serve(bus, &mut drives, stop, &mut |_| {}))
                        .map_err(|e| e.to_string())
                })
                .collect::<Result<_, _>>()?;
            for thread in threads {
                thread
                    .join()
                    .map_err(|_| "a bus thread panicked".to_owned())?
                    .map_err(|e| e.to_string())?;
            }
            Ok(())
        })
    }

    /// The drives the skeleton puts on `bus`. A drive without a commissioned UID gets one made from its bus and ID, so
    /// every simulated drive answers a type-0 query with something unique.
    fn drives(
        skeleton: &skeleton::Skeleton,
        bus: &str,
        bus_index: u64,
        seed: u64,
    ) -> Vec<SimDrive> {
        skeleton
            .limbs
            .iter()
            .flat_map(|limb| &limb.joints)
            .filter(|joint| joint.bus.as_ref().is_some_and(|b| b.as_str() == bus))
            .map(|joint| {
                let id = joint.id.get();
                let index = u8::try_from(bus_index).unwrap_or(u8::MAX);
                let uid = joint
                    .uid
                    .unwrap_or(Uid([b's', b'i', b'm', index, id, 0, 0, 0]));
                let drive_seed = seed ^ (bus_index << 8 | u64::from(id));
                SimDrive::new(Drive::new(joint.id, joint.actuator), uid, drive_seed)
            })
            .collect()
    }
}
