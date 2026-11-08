# Rust conventions

How Roark's Rust is written. [TENETS.md](../TENETS.md) says what is right, [architecture.md](architecture.md) says how the pieces fit, and this file says
how to write it in Rust. If the two
ever disagree, the tenets win and this file gets fixed. Every rule here exists because of a failure it prevents, named in its
"why". Most rules are enforced by the compiler, clippy or CI, so nobody has to judge Rust by eye.

Rules marked **(rt)** apply to the realtime crates: `robstride`, `can`, `safety`, `control` and the `runtime` binary.
Everything else (`api`, `telemetry`, `robot-cli`, `sim-drive`, the `ui/` bridge, `mcp/`) follows the general rules.

## 1. Toolchain and workspace

- **One Cargo workspace** at the repo root. Every crate inherits `[lints] workspace = true` and takes its dependency
  versions from `[workspace.dependencies]`, so one crate can't quietly differ from the rest.
- **Pinned stable toolchain** in `rust-toolchain.toml`: the current stable when the repo is set up, plus `rustfmt`, `clippy`
  and the Pi target. Bump it deliberately in its own PR, never as a side effect. No nightly features, no nightly-only
  rustfmt options.
- **Edition 2024.** `Cargo.lock` is committed. The Pi runs exactly what CI built.
- **Pi target:** `aarch64-unknown-linux-gnu`. Cross-compile from the dev machine or CI (pick one tool, such as
  `cargo-zigbuild` or `cross`, and write the command in the README), or build on the Pi. Either way, the same lockfile.
- **Every binary knows its build.** Embed the git commit (and a dirty flag) at build time. Log it at startup and write it into
  every MCAP file's metadata, because a log you can't tie to a commit is no use to the sim-to-real loop (tenet 6).

```toml
# rust-toolchain.toml
[toolchain]
channel = "1.NN.0"            # current stable at repo setup; bump in its own PR
components = ["rustfmt", "clippy"]
targets = ["aarch64-unknown-linux-gnu"]
```

```toml
# Cargo.toml (root)
[workspace]
resolver = "3"
members = ["crates/*", "bins/*"]   # match the crate layout in PLAN.md

[workspace.package]
edition = "2024"

[profile.release]
panic = "abort"               # see section 4
overflow-checks = true        # wrong arithmetic must stop the process, not command a drive
debug = "line-tables-only"    # readable backtraces from the Pi
lto = "thin"

[profile.dev]
panic = "abort"
```

## 2. Lints: the compiler is the first reviewer

Workspace-wide. CI runs `cargo clippy --workspace --all-targets -- -D warnings`, so a warning blocks a merge.

```toml
[workspace.lints.rust]
unsafe_code = "deny"                    # override per module only, with a reason (section 10)
unused_must_use = "deny"
missing_docs = "warn"                   # public items in library crates
unreachable_pub = "warn"
rust_2018_idioms = { level = "warn", priority = -1 }

[workspace.lints.clippy]
pedantic = { level = "warn", priority = -1 }
# no panics outside tests
unwrap_used = "deny"
expect_used = "deny"
panic = "deny"
todo = "deny"
unimplemented = "deny"
unreachable = "deny"
indexing_slicing = "deny"              # use .get(); a bad index is a panic
exit = "deny"
# no debugging leftovers; logs go through tracing
dbg_macro = "deny"
print_stdout = "deny"
print_stderr = "deny"
# numeric safety: casts and float compares are where scale bugs hide
cast_possible_truncation = "deny"
cast_sign_loss = "deny"
cast_possible_wrap = "deny"
cast_precision_loss = "warn"
float_cmp = "deny"
# silencing has to say why
allow_attributes = "deny"               # use #[expect(...)], which fails once the lint no longer fires
allow_attributes_without_reason = "deny"
mem_forget = "deny"
await_holding_lock = "deny"
large_stack_arrays = "deny"
large_stack_frames = "warn"
undocumented_unsafe_blocks = "deny"     # every unsafe block carries a // SAFETY: comment
```

```toml
# clippy.toml
allow-unwrap-in-tests = true
allow-expect-in-tests = true

# Each entry says why. Bans that apply only to the realtime crates (reading the clock, sleeping) go in that crate's own
# clippy.toml, because time is passed in there (architecture.md section 9).
disallowed-methods = [
  { path = "std::panic::catch_unwind", reason = "we run panic = abort; a caught panic leaves a half-alive process" },
  { path = "std::sync::mpsc::channel", reason = "unbounded; use a bounded queue so overload is visible" },
  { path = "crossbeam_channel::unbounded", reason = "unbounded; use bounded() with a defined full behaviour" },
]
```

```toml
# clippy.toml in robstride, safety and control
disallowed-methods = [
  { path = "std::time::Instant::now", reason = "time is passed in by the loop so tests can step it" },
  { path = "std::time::SystemTime::now", reason = "wall clock is for logs only, and not in these crates" },
  { path = "std::thread::sleep", reason = "the loop owns timing; these crates never wait" },
]
```

The realtime crates also turn on `clippy::wildcard_enum_match_arm` and `clippy::as_conversions` in their `lib.rs`.

- **Silence a lint only with `#[expect(lint, reason = "...")]`** on the smallest item that needs it, never on a whole
  crate. The reason says why this case is safe, for example `reason = "id is masked to 8 bits on the line above"`.
- **Never edit the lint table to make a PR pass.** Changing it is its own PR, with a reason.
- **Why:** agents write code that compiles but panics (`unwrap`), truncates (`as u16`) or compares floats exactly. Lints
  catch all three before a reviewer has to.

## 3. Types carry meaning

- **Newtypes for units and identities**, at least: `Radians`, `RadPerSec`, `NewtonMeters`, `Amps`, `Celsius`, `DeviceId(u8)`,
  `BusName`, `JointName`. Construction checks the range. Arithmetic is implemented only where it makes physical sense.
  **Why:** a swapped velocity and torque argument, or a degrees-for-radians slip, compiles fine with bare `f64` and moves
  an arm.
- **Parse, don't validate.** The `skeleton` crate turns the YAML into checked types once, at startup: limits ordered, caps
  inside the drive model's range, IDs unique per bus, every bus named. Nothing downstream re-checks or handles "maybe
  invalid" config. A bad skeleton stops the process before any bus opens, with an error naming the joint and field.
- **Enums for states, exhaustive matches.** Drive state, limb state and fault kinds are enums. In the realtime crates a
  `match` on them never uses `_`, so adding a state forces every handler to decide what to do with it.
- **Make illegal transitions unrepresentable where it's cheap.** Example: enabling a drive takes a `PreflightPassed` value
  that only `safety`'s preflight can create, so an enable without a preflight doesn't compile. Use this at the safety seams;
  don't build typestate machinery anywhere else.
- **Floats:** `f64` for host math. Convert to the drive's integer encoding in one place, the codec (section 7).
- **`bool` parameters are banned in public functions.** `set_mode(Mode::Mit)`, not `set(true)`.

## 4. Errors and panics

- **Libraries return typed errors**: one `thiserror` enum per crate, with variants that say what happened and fields that
  say where (bus, device ID, joint, parameter). No `Box<dyn Error>`, no `String` errors in libraries.
- **`anyhow` only in binaries and tools**, at the top level, with `.context("...")` on each step.
- **Never drop a `Result`.** No `let _ = fallible();`, no `.ok()` to discard an error in a safety or CAN path. If ignoring an
  error is correct, write why on the line above.
- **Drive faults are data, not errors.** A drive reporting overcurrent is a valid reply that the `safety` crate acts on. An
  `Err` means our code or the bus failed: a malformed frame, a socket error, a missed deadline.
- **Panics end the process, on purpose.** `panic = "abort"` in every profile. **Why:** with unwinding, a panic kills only one
  bus thread and leaves the rest of the process half alive, still sending. Aborting kills everything. Then the drives' CAN
  host-loss timeout stops them, and systemd runs the independent `disable` (tenet 3). A dead process is a known state;
  a half-alive one is not.
- **Install a panic hook in `runtime`** that writes the panic message, thread name and location to stderr (the journal)
  before the abort. It must not lock, allocate much or touch the CAN socket.
- **Assertions stay on in release.** Check invariants with `assert!` at the seams (a pre-condition on entry, the matching
  post-condition on exit), not `debug_assert!`. In the realtime path a broken invariant ends the process and the drives time
  out; never log-and-continue (no "recover and carry on" macros). Expected bad input, such as a malformed frame, is an
  `Err`, not an assertion.
- **Put a limit on everything.** Every loop, queue, retry, buffer and wait has a stated upper bound, taken from the skeleton
  or a named constant. "Until it answers" is not a bound.
- **`Drop` is not a safety mechanism.** It doesn't run on abort, `SIGKILL`, OOM kill or power loss. Nothing safety-critical
  may depend on a destructor running. The drive timeout and the systemd `disable` are the safety path; a clean `Drop` is
  only a courtesy.

## 5. Ownership and threads

- **One owner per piece of state.** The bus thread owns its socket and its drives' state. Others get snapshots or send
  requests over channels. **Why:** shared mutable state behind `Arc<Mutex<_>>` is the most common way Rust code becomes
  slow, deadlock-prone and impossible to reason about.
- **(rt) No `Mutex`, `RwLock` or `Condvar` shared between a realtime thread and anything else.** A realtime thread waiting on
  a lock held by a low-priority thread is priority inversion: the tick misses its deadline because the UI is busy. Hand-offs
  go through lock-free single-producer, single-consumer queues (`rtrb`, per PLAN section 3), one per direction.
- **`Arc<Mutex<_>>` outside the realtime crates is allowed but suspect.** Prefer a single owning thread or task with a
  channel. If you add one, the PR says why a channel won't do.
- **Fighting the borrow checker means the ownership design is wrong.** Restructure who owns what. Don't paper over it with
  `.clone()`, `Rc<RefCell<_>>` or `'static` lifetimes.
- **Async only at the edges.** `tokio` is fine in `api`, the UI bridge, `mcp/` and the recorder's file and network I/O. Never
  block inside async code (no `std::thread::sleep`, no blocking file or socket calls); use `spawn_blocking` or a plain thread.
  The realtime side never awaits anything: it talks to async code only through `rtrb` queues or bounded channels.
- **Every thread is named** (`std::thread::Builder::name`), so panics, logs and `top -H` show which bus or job it is.
- **Every thread has an explicit stop path**: a shared `AtomicBool` or a stop message, checked each loop.

## 6. The realtime loop (rt)

PLAN section 3 sets the design: one process, one blocking thread per bus, SCHED_FIFO, pinned, memory locked, 250 Hz. In code:

- **No async in the realtime crates.** No `tokio`, no `async fn`, no `block_on`. Plain `std::thread` with the blocking
  `socketcan` socket.
- **No allocation after startup.** Allocate every buffer, queue and table before the first tick: `Vec::with_capacity` sized
  from the skeleton, fixed arrays, `rtrb` queues with fixed capacity. Inside the tick: no `Vec` growth, `String`, `format!`,
  `Box::new` or `HashMap` inserts. **Why:** the allocator can take a lock or fault in a page, and that shows up as a late
  motor command. Lock memory (`mlockall`) at startup, after allocation.
- **No I/O but CAN in the tick.** No file writes, no `tracing` calls, no stdout. The tick pushes structured events onto an
  `rtrb` queue; the `telemetry` thread turns them into logs and MCAP records.
- **Absolute deadlines.** Sleep until the next tick's absolute time on the monotonic clock, not `thread::sleep(period)`,
  which drifts by however long the tick took. Count missed deadlines, never skip them silently.
- **Measure the loop on every run.** Each run records tick duration and jitter (a histogram or percentiles) to MCAP and
  metrics. The sim-drive CI job fails if p99 tick time goes over budget. This is the alarm that the realtime code is
  degrading.
- **Bounded work per tick.** Every loop inside the tick has a fixed upper bound from the skeleton (drives on this bus) or a
  constant. No `while` loops that wait for a reply without a deadline.

## 7. The codec is sans-IO (rt)

- **`robstride` does no I/O, no allocation and no clock reads.** Pure functions: command plus drive model in, CAN frame out;
  frame in, typed reply or error out. It should build with `#![no_std]` (`core` only). That isn't required, but it proves
  the crate has no hidden I/O.
- **Reject non-finite values before encoding.** In Rust, `f64 as u16` saturates and turns `NaN` into `0`, and in an MIT-mode
  scale `0` means the most negative position, speed or torque in the range. So: check `is_finite()` first and return an
  error, then clamp to the model's range, then convert with explicit rounding. One function does this, used by every
  encoder.
- **Every protocol constant cites its source**: manual name, version and section or table, for example
  `// RS03 manual 261013, section 4.1.2: type 1 frame layout`. Constants live in one table per frame type, not inline.
- **The 29-bit extended ID layout is built and parsed in exactly one place**, with `const fn`s, and checked against the
  manuals' worked examples in tests.
- **Test vectors are tables**: every manual example and every captured real frame that taught us something (RECONCILIATION's
  hard-won list), as `(input, expected bytes)` rows. Add property tests (`proptest`) for round trips and clamping. These are
  the "protocol contract" tests tenet 6 allows.

## 8. Tests

How we test, what earns a test and what doesn't, lives in [testing.md](testing.md). Two Rust-specific notes only:
`unwrap`/`expect` are fine in tests (`clippy.toml` allows them), and a `trait` added only so a mock can exist is the kind of
abstraction section 11 forbids.

## 9. Dependencies

- **Few, boring, maintained.** Every new dependency gets one line in its PR: what it does that we shouldn't write, and why
  this one.
- **(rt) Realtime crates take only** `socketcan`, `rtrb` and `thread-priority`, plus small, pure crates such as `thiserror`.
  Anything else in a realtime crate needs a reason in the PR. No allocation, copy or added latency on the hot path without a
  written reason agreed in the PR.
- **`cargo deny check`** in CI: licences, security advisories, banned or duplicate crates. `deny.toml` denies wildcard
  versions, unknown registries and git sources. Every advisory ignore carries a reason and a `Review: YYYY-MM` date, and is
  re-checked by then. Unused dependencies are removed (`cargo machete` or similar).
- **Turn off default features you don't use** (`default-features = false`) for anything pulled into the realtime crates.
- **Never add a dependency to get past a compile error.** Understand the error first.

## 10. Unsafe and OS calls

- **`unsafe_code` is denied workspace-wide.** The expected exceptions are the few OS calls the realtime setup needs, such as
  locking memory and absolute-deadline sleep, if no safe crate covers them. They live in one small module in `runtime` (or
  `can`), behind safe functions.
- **Every `unsafe` block has a `// SAFETY:` comment** saying which invariants make it sound, and the module carries
  `#[expect(unsafe_code, reason = "...")]`.
- **No `unsafe` for speed.** Nothing in this robot at 250 Hz needs it.

## 11. Shape and readability (tenet 7)

- **Each crate's `lib.rs` (or `main.rs`) opens with a `//!` header**: what it is for, what it must never do, and what it talks
  to. Example for `can`: "Owns every CAN socket. Must never: allocate in the tick, take a lock shared with non-realtime code,
  or let anyone but the runtime transmit. Talks to: `robstride` (encode and decode), `safety` (checks every command), the
  `rtrb` queues to `api` and `telemetry`."
- **Concrete types first.** A trait only when two real implementations exist today. Generics only to remove real
  duplication. No `Box<dyn Trait>` where an enum works. **Why:** layered abstractions are the fastest way to make code an
  agent can't learn in minutes.
- **Actuator differences are data.** RS00, RS02, RS03 and RS04 differ by a table of scales and limits, not by types or
  traits. No generic "any actuator" or "any limb" framework (tenet 1).
- **No builders, factories or dependency-injection containers.** Structs with public fields or a plain `new`.
- **Files stay small.** Aim under 600 lines, hard cap 800 (CI checks it); functions around 60 lines. A long file means a
  concept wants its own module.
- **Small public surface.** Default to private, then `pub(crate)`. A `pub` item is a promise to other crates.
- **`macro_rules!` only for tables** (such as the frame or parameter table), never to hide control flow. No procedural macros
  of our own.
- **No speculative code.** No `#[expect(dead_code)]` for "we'll need it later", no unused feature flags, no empty extension
  points (tenet 4).
- **Comments say why, not what.** Every magic number cites a manual section, a bench log or a tenet.
- **`rustfmt` defaults.** No custom style debates. `cargo fmt --check` in CI.

## 12. Logging in code (tenet 8)

- **`tracing`** for structured events, outside the realtime threads. One set of field names everywhere: `bus`, `device_id`,
  `joint`, `limb`, `mode`, `fault`, `session`. Values are typed fields, not interpolated strings:
  `info!(joint = %j, bus = %b, "drive enabled")`.
- **Levels mean something.** `error`: an operator or agent must look. `warn`: degraded but handled (a late reply, a retry).
  `info`: state changes and operator actions. `debug`/`trace`: per-frame detail, off by default and never needed for replay,
  because MCAP holds the frames.
- **No `println!`/`eprintln!`** (clippy denies them). CLIs print results through one output function, so they can also emit
  JSON for agents.

## 13. CI gates

Every PR, before merge:

1. `cargo fmt --all --check`
2. `cargo clippy --workspace --all-targets -- -D warnings`
3. `cargo test --workspace` (unit, codec vectors, property tests)
4. `cargo deny check`
5. Shape checks, one small script: crate dependencies only point the way [architecture.md](architecture.md) section 3
   allows (read from `cargo metadata`), and no source file passes 800 lines
6. Release build for `aarch64-unknown-linux-gnu`
7. The sim-drive suite on `vcan`: fault injection and the tick-timing budget (section 6)

One local command runs 1 to 5 (a `just check` recipe or a small script; pick one and name it in the README), so an agent can
run exactly what CI runs before pushing.

## 14. Smells to question in a PR

You don't need to read Rust fluently to review it. Each row maps a Rust smell to the JavaScript habit it resembles and the
question to ask.

| You see | It's like (JS) | Ask |
|---|---|---|
| `.unwrap()`, `.expect(`, `panic!`, `todo!` outside tests | Uncaught promise rejections | What happens when this fails mid-motion? (clippy should already block it) |
| `Arc<Mutex`, `RwLock`, `Rc<RefCell` piling up | A global store everyone mutates | Who owns this data? Never in `can`, `robstride`, `safety`, `control` |
| `.clone()` in a loop, or many in one change | Deep-copying to dodge a bug | Was ownership decided, or dodged? |
| `async`, `tokio`, `.await` in a realtime crate | Heavy sync work on the main thread | Why is the realtime path waiting on anything? |
| `Box<dyn ...>`, a new `trait` with one implementation, generics everywhere | A six-layer HOC or provider pyramid | Are there two real implementations today? |
| `unsafe` | `eval` | Where is the `SAFETY:` comment, and why can't a safe crate do it? |
| `#[expect(...)]` with a weak reason, or edits to the lint table | `// eslint-disable-next-line` | Why is the warning wrong here? |
| `as u8`, `as u16`, `as i16` near motor values | `parseInt` on untrusted input | What happens with NaN, or a value out of range? |
| `let _ =` on something that returns `Result` | A floating promise with no `catch` | Where does this error go? |
| `format!`, `String`, `Vec::new()`, `tracing` inside the tick | Allocating inside a render loop | Can this happen once at startup instead? |
| A new crate, or a new dependency without a reason line | A new npm package for one function | What does it replace, and is it maintained? |
| A file passing 600 lines | A 1,500-line component | What concept can be split out? |
| A bare `f32`/`f64` in a signature for a physical value | `any` | Which unit is this? Use the newtype |

## 15. Rules for agents

- Run the local check command (section 13) before every push. Don't push red.
- **Check the API before calling it.** Agents invent crate methods. Read docs.rs for the exact version in `Cargo.lock`, and
  compile early and often.
- Don't copy legacy patterns. The marengo repo is for facts and bench lessons only.
- When the borrow checker refuses, change the ownership, not the lifetimes. Cloning to make it compile is a design smell,
  not a fix.
- Never weaken a lint, a test or a CI step to get green. If a rule is wrong, say so in the PR and change it on purpose.
- Don't add a dependency, trait, generic, macro or crate unless the change needs it today.
- When unsure whether something belongs in a realtime crate, it doesn't. Put it on the non-realtime side of the queue.
