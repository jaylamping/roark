# Roark

Roark is a humanoid robot in active development: an attempt to make mechanical and software engineering work together as one
project, which I will almost certainly never finish.

The goal is a fully autonomous, two-legged robot that can handle basic everyday tasks, which is more than can be said for its
creator.

And when the machines finally rise up and humanity finds itself at the bottom of the totem pole, I'm counting on the hours I've
put into the robo-community to get me an invite to the robo-cookout.

## This repo

The control software for Roark, a full-size humanoid robot: one realtime process on a Raspberry Pi 5 driving RobStride actuators over
five CAN buses, plus a simulated drive, agent tools and an operator UI.

- [TENETS.md](TENETS.md): how everything should work.
- [PLAN.md](PLAN.md): what gets built, in order.
- [conventions/](conventions/): how code, config, tests and procedures are written and reviewed.
- [cad/](cad/): the robot's CAD, versioned through Git LFS ([conventions/cad.md](conventions/cad.md)).
- Hardware docs and the legacy software live in the reference repo, [jaylamping/marengo](https://github.com/jaylamping/marengo).

## Build and check

The toolchain is pinned in `rust-toolchain.toml`; `rustup` installs it on first use. The checks also need
[cargo-nextest](https://nexte.st), [cargo-deny](https://github.com/EmbarkStudios/cargo-deny) and Python 3. Working on `cad/` also needs
[Git LFS](https://git-lfs.com) (`git lfs install` once per machine).

```bash
cargo install --locked cargo-nextest cargo-deny
```

Run what CI runs before every push:

```bash
./scripts/check.sh
```

Cross-build for the Pi with the distro's aarch64 GCC (`gcc-aarch64-linux-gnu` on Debian and Ubuntu):

```bash
cargo build --release --workspace --locked --target aarch64-unknown-linux-gnu
```
