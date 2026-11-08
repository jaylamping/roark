# Testing conventions

**Status:** proposed for Joey's review, 2026-11-08. This file expands
[tenet 6, "No pointless tests"](../TENETS.md#6-measure-automate-close-the-loop) into rules an agent can follow and a reviewer
can check. Rust style in general lives in [rust.md](rust.md); this file is only about tests.

Each rule says **why** it exists, because a rule without its reason gets ignored the first time it is inconvenient. Where it
helps, there is a comparison to the JavaScript world (Jest/Vitest, React Testing Library).

## Why this file exists: what went wrong last time

The legacy stack in [marengo](https://github.com/jaylamping/marengo) ended up with about **1,500 Rust tests and 90 UI test
files** for one arm. In the safety crate (`davout`), the `tests/` folder alone was 13,900 lines next to 22,000 lines of code it
tested, and one file (`physical_reference.rs`) was 3,000 lines with 67 tests. Reading through them, the same problems show up
again and again:

| What we saw | Example in marengo | Why it hurt |
|---|---|---|
| Tests written as proof that a PR did its job, named after the work package | `berthier/src/loop_wp_d_tests.rs` ("Phase B / WP-D evidence for the fixes"), `"Base UI lint gate (PR8)"` | The PR is long gone; the test stays forever and nobody knows what failure it guards |
| Several files circling one behaviour | `limit_restore_atomicity.rs`, `limit_restore_reference.rs`, `limit_restore_reference_atomicity.rs`; `reference_observed_mismatch.rs` and `reference_observed_busy_mismatch.rs` | Every change to that code broke a dozen tests at once, so agents became afraid to touch it (the opposite of tenet 4) |
| Tests pinned to one limb and to live config values | `const JOINT: &str = "right_shoulder_pitch"`, `master_config_accepts_right_five_dof_joints`, `elbow_alias_resolves_right_bench_joint` | Breaks tenet 0. Adding a limb or changing a limit in config broke tests that had nothing to do with the change |
| Tests that read source files as text | a Vitest test that globbed `ui/**` source and regex-searched imports; several Rust tests reading `.rs`/script files | A linter's job done badly. Belongs in clippy, cargo-deny or ESLint config |
| Tests of library behaviour | `normalize_sorts_and_dedups` | Proves `Vec::sort` works. It always will |
| Tests of UI layout shells | `chart-section-skeleton.test.tsx`, `sidebar-panel-shell.test.tsx` | Break on every visual change, never catch a motion or safety bug |
| Timing by sleeping | about 70 `sleep` calls in test folders | Slow, and flaky on a loaded machine; flaky tests teach everyone to ignore red |

None of these tests were *wrong* one at a time. Each was a reasonable "add a test for what I just did". The problem is the
default: when every change adds tests and nothing ever removes them, the suite grows faster than the code, and the suite itself
becomes the thing nobody dares to touch.

So the default flips: **a test has to earn its place, and has to keep earning it.**

## Rule 1: every test names the failure it guards

A test may exist only if it guards one of these four things (straight from tenet 6). Each test starts with a one-line doc
comment saying which one, in this form:

| Guard | Doc comment | What it points at |
|---|---|---|
| A bug we actually hit | `/// Guards: bug - <one line>, <link to issue, PR or log>` | The real failure, so a reader can judge if it can still happen |
| A safety rule | `/// Guards: safety - <rule>` | A row in [PLAN.md item 6](../PLAN.md#6-safety-the-three-layers-tenet-3) / tenet 3 |
| A protocol contract | `/// Guards: protocol - <frame or parameter>, <manual and page>` | The RobStride manual, or the `api` contract between the runtime and its clients |
| A number a loop depends on | `/// Guards: number - <what>, <where it is used>` | A scale, limit, timing or fitted constant some loop relies on |

```rust
/// Guards: safety - refuse enable when canTimeout reads back 0 (PLAN item 6, drive layer).
#[test]
fn enable_is_refused_when_can_timeout_is_disabled() { ... }
```

**Why:** if you can't fill in that line, the test doesn't guard anything, and it is exactly the kind that piled up last time.
The line also tells a future reader when the test can be deleted: when the rule, the bug's code path or the contract is gone,
so is the test. A CI check (see "Automated checks") refuses any test without a `Guards:` line.

Not on the list, on purpose: "coverage", "the file was touched", "proves the PR works", "documents how to call the function".
Coverage numbers are not tracked at all. In JS terms: no `--coverage` thresholds, no "every component gets a test file".

## Rule 2: one rule, one test (or one table)

Each guarded thing gets **one** test. If it needs many inputs, that's one table-driven test, not many tests.

```rust
/// Guards: protocol - MIT scales per model, RobStride manuals (RS00 p.?, RS02 p.?, RS03 p.?, RS04 p.?).
#[test]
fn mit_scales_match_the_manuals() {
    let cases = [
        // (model, max velocity rad/s, max torque N·m)
        (Model::Rs02, 44.0, 17.0),
        (Model::Rs03, 20.0, 60.0), // ±20 rad/s measured on the bench, see the bug note in the codec docs
        // ...
    ];
    for (model, vel, torque) in cases {
        let s = model.mit_scale();
        assert_eq!((s.vel_max, s.torque_max), (vel, torque), "{model:?}");
    }
}
```

(The numbers above are placeholders to show the shape. Real values come from the manuals and the lifted bench notes, PLAN item 2.)

**Why:** this is `test.each` in Jest. One table is easy to read as a spec, easy to extend with one line when the manual adds a
model, and when the rule changes you edit one place. Five near-identical tests for one rule are five places to update and five
red lines in CI for one bug. Before adding a test, search for an existing one that guards the same rule and add a row to it.

## Rule 3: tests are for the whole robot, never one limb

- No test names a specific limb, joint, bus or ID unless the thing under test is truly limb-specific hardware data (tenet 1).
- Tests that need a robot build one from a **small inline skeleton** in the test (or one shared test fixture describing all
  five limbs), never from the live `config/skeleton.yaml`.
- The only test that reads the live skeleton is the one that checks **it loads and passes validation**. It never asserts a
  value from it.

**Why:** the live skeleton is edited by the hardware side whenever a part changes (tenet 2). If tests assert its values, every
hardware change turns CI red for no software reason, and someone "fixes" the test by copying the new number in, which proves
nothing. Tests written around `right_shoulder_pitch` are how the old code ended up shaped like one arm. A fixture with all five
limbs, some of them offline, keeps every test honest about tenet 0 and tests the "unbuilt limb is just offline" path for free.

## Rule 4: test through the seam, not the insides

Test a crate through what it exposes to other crates: the codec's encode/decode functions, the skeleton loader, the safety
checks, the `api` messages. Don't test private helpers, and don't make something `pub` just to test it.

**Why:** the inside of a crate should be free to change without touching tests (that freedom is the point of tenet 7's clear
seams). Tests on private helpers break on every refactor while the behaviour stays the same, so they cost work and catch
nothing. React Testing Library's "test what the user sees, not the component's state" is the same idea: here, "the user" is
the next crate over.

## Rule 5: don't mock what we own; use the simulated drive

- The codec (`robstride`) is pure: bytes in, typed frames out, and back. Test it with plain values, no fakes needed. Writing it
  this way ("sans-IO") is what makes it cheap to test.
- Code that talks to buses is tested against **`sim-drive` on `vcan`**, the same way the runtime runs (PLAN item 4). No
  hand-written mock CAN socket, no mock `Supervisor`.
- Fakes are fine only at the edge of the world we don't control: the filesystem, a real hardware device. Time isn't faked at
  all; it's passed in as an argument (rule 6).

**Why:** a mock only knows what its author believed the real thing does, so a test against a mock proves the code agrees with
that belief, not with the drive. The legacy code grew whole simulated owners (`Supervisor::from_simulation`) that every test had
to set up, and they drifted from the real thing. `sim-drive` is a single fake that speaks the real protocol through the real
codec, is shared by every test and by humans at the bench, and is checked against real drives. One good fake beats fifty
mocks. In JS terms: prefer one MSW-style fake server over `jest.mock` in every file.

## Rule 6: no sleeping, no wall clock

- Code that depends on time (the 50 ms drive timeout, "3 missed replies", the 250 Hz tick, temperature pauses) takes its time
  as an argument: the loop reads `Instant::now()` once per tick and passes it in. Logic never reads the clock itself, so a test
  passes in whatever times it wants. No `Clock` trait: a trait needs two real implementors ([rust.md](rust.md)), and a plain
  argument does the job.
- Tests never call `thread::sleep` to wait for something. A tick-driven test calls `tick()` N times; a sim test waits on an
  event with a deadline, not a fixed nap.
- Fault injection in `sim-drive` is deterministic: a fault happens at tick N or after frame M, never "sometimes". Random
  inputs use a fixed seed printed on failure.

**Why:** a test that sleeps 100 ms to "let the loop run" is slow when it passes and random when the machine is busy. A flaky
test is worse than none, because it trains everyone, agents included, to rerun until green and ignore red. This does the job of
`jest.useFakeTimers()` in Rust, only simpler: you control time, so a 50 ms timeout test runs in microseconds and gives the same answer every
time.

## Rule 7: a bug gets its test before its fix

When a real bug turns up (on the bench, in sim, in a log), first write a test that fails because of it, then fix the code and
watch the test pass. The `Guards: bug` line links to the issue, PR or log that showed it.

**Why:** this proves the test actually detects the bug (a test written after the fix often passes either way), and the link
keeps the story with the code. These are the most valuable tests we'll have: every one of them is a failure that really
happened to this robot.

## Rule 8: the bench is not a test suite

Tests on real drives are **procedures run by `robot-cli` or the test-stand runner**, logged to MCAP, judged by a script, and
run by a person or an agent on purpose (PLAN items 5, 7 and 9). They are never `cargo test`, never run in CI, and never run
automatically.

**Why:** there are no spare actuators. A test that can move a motor must be something someone chose to start, with the E-stop in
reach, not something that fires because an agent typed `cargo test` on the Pi. It also keeps `cargo test` safe to run anywhere,
including a laptop with no CAN hardware. (`cargo test` here means any of our test commands, including `cargo nextest run`.)

## Rule 9: the UI tests only what could move the robot

The operator UI is a client of `api` and can crash without affecting motion (tenet 5). Its tests cover only logic that decides
what gets sent: the confirm step before enable, refusing a command when the robot state is stale, showing a fault that must not
be hidden. No tests for layout, styling, skeleton loaders, snapshots or "it renders".

**Why:** this is where 90 test files came from last time. Layout tests break on every visual tweak and guard nothing physical.
If the dashboard looks wrong, you see it; if it sends an enable without a confirm, you might not. Test the second kind only.

## Rule 10: delete tests as eagerly as you add them

- When the code, rule or contract a test guards is deleted or changed, the test is deleted or changed **in the same PR**.
- A test that keeps needing edits for refactors and has never caught a real problem is a deletion candidate. Say so in the PR.
- At the end of each milestone, sweep the suite: every test still has a true `Guards:` line, or it goes.

**Why:** tests are code, and tenet 4's "speculative code is deleted" applies to them too. A test whose reason has gone is not
"extra safety", it is a tripwire for the next person. Git history keeps it if it's ever needed again.

## Rule 11: no ignored tests, no expected panics

- **No `#[ignore]`** and no skipped Vitest/Playwright tests (`it.skip`, `test.fixme`) on `main`. A test that can't pass yet
  either isn't merged, or asserts today's (wrong) behaviour with a `FIXME(<issue link>)` comment, so it goes red the day the
  behaviour changes.
- **No `#[should_panic]`.** Test the error value the code returns. Panicking is not an API.
- **Assert exact values** (`assert_eq!` on the whole value), not "contains" or "is ok". A loose assertion passes on the wrong
  answer.

**Why:** an ignored test is a test nobody runs, which is worse than no test because it looks like coverage. rust-analyzer bans
both outright; rerun asks for `assert_eq!` over `contains` for the same reason.

## Rule 12: the suite has a time budget

- `cargo nextest run` (unit and integration) finishes in **under 30 seconds** on a laptop. Each test gets a slow warning at 5 s
  and is killed at 60 s (`.config/nextest.toml`).
- The sim suite on `vcan` finishes in **under 5 minutes** in CI. Simulated time runs as fast as the code allows, never at wall
  speed.
- A test that needs longer is a sign it's testing too much at once. Split it, or make it a scheduled job (fuzzing, mutation
  testing), not a PR gate.

**Why:** a fast suite gets run before every push; a slow one gets skipped, and then it guards nothing. rust-analyzer keeps its
whole suite under about 30 s; Materialize aims for PR checks under 10 minutes that catch 95 % of bugs.

## How big the suite should be

The four guards put a natural ceiling on the count. For milestone 1, roughly:

| Crate / bin | What gets tested | Rough count |
|---|---|---|
| `skeleton` | Live skeleton loads; one table of invalid skeletons, one row per validation rule (duplicate ID, limit outside hard stop, unknown bus...) | 2 to 5 |
| `robstride` | One table test per frame type, vectors from the manuals; round-trip encode/decode; the lifted bench facts (ID layout, MIT scales, TX allowlist) | 10 to 20 |
| `can` | Tick schedule and silence detection with times passed in by the test; scan and set-ID against `sim-drive` | 5 to 10 |
| `safety` | One unit test per host rule and drive preflight check in PLAN item 6; one `sim-drive` test per fault the sim can inject | 20 to 30 |
| `control`, `dynamics` | Numbers loops depend on (gravity terms, calibration fit on a known synthetic set) and bugs hit | a handful each |
| `telemetry`, `api` | The `api` message contract; MCAP output readable by the replay tool | a handful each |
| `ui/` | Rule 9 only | a handful |

That's on the order of **a hundred tests for the whole robot at milestone 1**, not fifteen hundred for one arm. Later
milestones should add few tests, because they add drives, not code paths (PLAN, "Milestones"). If a crate's count runs well past
its row, stop and ask whether its tests are guarding rules or restating code.

These numbers are a review signal, not a hard cap. CI prints the count per crate on every PR, and a PR that adds tests says in
its description what each new one guards.

## Tools and methods, per language

Joey asked for the current, industry-accepted way of testing in every language we use (2026-11-08). The rules above decide
**whether** a test should exist; this section decides **how** it's written and run. Everything here is mainstream and widely
used, not a niche pick. The overall shape is the common one: static checks catch the most for the least effort, then fast unit
and property tests, then a smaller layer of integration tests against the simulated drive, then a very few end-to-end checks.
In embedded and robotics terms, `sim-drive` is our **software-in-the-loop (SIL)** layer and the bench is **hardware-in-the-loop
(HIL)**, which stays manual (rule 8).

### Static checks come first (every language)

The compiler, type checker and linters are the cheapest tests there are, so they run before any test and a PR can't merge with
them red: `cargo fmt --check`, `cargo clippy` (with the deny list in [rust.md](rust.md)), `cargo deny` for dependencies,
`tsc --noEmit` and ESLint for `ui/`, `ruff` for any Python, `shellcheck` for shell scripts.

**Why:** Rust's type system and TypeScript's strict mode already rule out whole classes of bugs (null, wrong units if we type
them, missing match arms). A test that only re-checks what the compiler guarantees is pointless by rule 1.

### Rust

| Need | Tool | How we use it | Why this one |
|---|---|---|---|
| Test runner | **cargo-nextest** (`cargo nextest run`) | The default runner locally and in CI. Doc examples still run with `cargo test --doc` | The de facto runner for serious Rust projects: each test in its own process (one crash or hang can't take down others), per-test timeouts that catch a hung loop, clear failure output, retries reported as flaky instead of hidden. **Retries are off by default** (`retries = 0`); a flaky test is fixed, not retried |
| Example tests | built-in `#[test]` and `assert_eq!` | Rules 1 to 7 | It's the standard; no extra framework (no "describe/it" DSL crate) |
| Property tests | **proptest** | Codec round-trips (`decode(encode(x)) == x` for any valid frame), skeleton validation never panics on any input, safety checks hold for any command stream. One property test counts as one test and needs a `Guards:` line | Instead of a few hand-picked inputs, it tries hundreds of generated ones and shrinks a failure to the smallest case. Like `fast-check` in JS. For a codec this catches far more than example tests, with fewer of them |
| Fuzzing | **cargo-fuzz** (libFuzzer) | One fuzz target on the frame decoder: bytes off the bus must never panic or hang it. Run on demand and before each milestone, not on every PR | Everything on the bus is outside input. A decoder panic in the realtime thread would stop the robot. Fuzzing is the standard tool for "this parser must survive anything" |
| Mutation testing | **cargo-mutants** | At each milestone sweep (rule 10), run it on `robstride`, `safety` and `can`. A mutant that survives means a rule isn't really guarded; one that's killed by many tests points at duplicates | It checks that tests actually *catch* bugs, by deliberately breaking the code and seeing if anything goes red. It measures what coverage only pretends to |
| Unsafe and concurrency | **Miri**; **loom** only if we write our own lock-free code | Miri on any crate with `unsafe` | We plan to use `rtrb` rather than write lock-free code, so loom is likely never needed (tenet 4) |
| Timing budgets | **criterion** benchmarks (or `divan`) | Codec encode/decode and one control tick, so a slowdown is seen before the Pi misses its 250 Hz budget. Benchmarks are measurements, not tests, and live in `benches/` | Tenet 6: numbers come from measurement. Real jitter is still measured on the Pi (PLAN item 5) |
| Snapshots | **insta**, rarely | Only where the output *is* a contract a person reviews, such as the `api` schema. Never to freeze arbitrary internal output | Snapshot tests are easy to write and easy to rubber-stamp; the review of the snapshot diff is the whole value |

Not used: code coverage tools as a gate (rule 1), mocking frameworks such as `mockall` (rule 5).

### TypeScript (`ui/`, and `mcp/` if it's TypeScript)

| Need | Tool | How we use it | Why this one |
|---|---|---|---|
| Test runner | **Vitest** | All unit and component tests | The current standard for Vite projects: Jest-compatible API, native TypeScript and ESM, fast watch mode |
| Components | **React Testing Library** with **user-event** (assuming the UI stays React) | Only rule 9's cases: query by role and label the way an operator would, click with `user-event`, assert on what is sent to `api` | Tests behaviour, not markup, so styling changes don't break it |
| The `api` | **MSW** (Mock Service Worker), with handlers built from the `api` types | One shared fake `api`, so components are tested against the real message shapes | The same idea as rule 5: one fake at the network edge instead of `vi.mock` in every file |
| Time | Vitest fake timers (`vi.useFakeTimers()`) | Staleness and timeout logic | Rule 6 |
| End to end | **Playwright** | A few smoke flows against the real UI and `runtime` on `sim-drive`: connect, see drives online and offline, the enable confirm, a fault shown and not auto-cleared | The standard for browser end-to-end tests. Kept to a handful because they are the slowest and most brittle layer |

Not used: Jest (Vitest replaces it), Enzyme (dead), snapshot tests of components, coverage thresholds.

### Python (fitting and analysis scripts, if any)

If the test-stand fitting or calibration scripts (PLAN items 7 and 9) are Python, they use **pytest**, with **Hypothesis** for
property tests (the Python twin of proptest). The main test for a fitting script is a known synthetic data set: generate data
from known friction and inertia values, fit, and check the fit recovers them within tolerance. That one test is a `Guards:
number` test for every constant the sim gets from that script.

### Workflows and CI

- **CI** (GitHub Actions) runs, in order: static checks, `cargo nextest run`, doc tests, the sim suite on a Linux runner with
  `vcan` loaded, `ui/` Vitest, then the Playwright smoke flows. Fail fast: a red static check stops the run.
- **Flaky tests are bugs.** nextest reports a test that passed only on retry as flaky; that test gets fixed or deleted within a
  day, never left on retry.
- **Scripts that agents run** (rule 8 procedures, loops from tenet 6) get the same treatment as code: a dry-run mode against
  `sim-drive`, and that dry run is how they're tested.

## Where tests live and how they run

| Kind | Where | Runs with | Runs where |
|---|---|---|---|
| Unit (pure logic: codec, skeleton checks, safety rules as functions) | `#[cfg(test)] mod tests` at the bottom of the file under test | `cargo nextest run` | Everywhere, including a Mac laptop. Whole run in seconds |
| Integration (a crate's public API, more than one module) | `crates/<name>/tests/<behaviour>.rs`, named after the behaviour, never after a PR or phase | `cargo nextest run` | Everywhere |
| Sim (the runtime against `sim-drive` on `vcan`, fault injection) | `bins/runtime/tests/` or one sim test crate | a separate command (for example `just test-sim`) | Linux with `vcan` ([the dev box](../docs/dev-box.md)), and CI |
| Bench (real drives) | `robot-cli` procedures and the test-stand runner, not test code | a person or agent, on purpose | The Pi, on the bench. Never CI |

**Why the split:** Rust has a built-in convention (`mod tests` in the file for small checks, `tests/` for the public API), so we
use it rather than inventing one. Keeping sim tests behind their own command keeps the plain test run fast and runnable on any
machine; keeping bench work out of the test runner entirely is rule 8. One file per *behaviour*, not per PR, means you find the
test by what it guards.

Keep test helpers small and inside the test file or one `tests/common/` module per crate. A test should read top to bottom
without opening three helper files.

## Automated checks

These run in CI so the rules don't depend on anyone remembering them:

1. **`Guards:` line check.** A small script fails CI if any test (`#[test]`, a proptest block, a Vitest `it`/`test`, a
   Playwright `test`, a pytest `test_` function) lacks a `Guards: bug|safety|protocol|number - ...` comment directly above
   it. Doc examples, fuzz targets and benchmarks are exempt: they aren't tests.
2. **Test count report.** CI prints tests per crate and the change from `main`, so growth is visible on every PR.
3. **No sleeping in tests.** CI fails on `thread::sleep` or `tokio::time::sleep` in Rust test code, and on real `setTimeout` waits in `ui/` tests.
4. **No source-text tests.** Rules about code shape (banned imports, `unwrap` in the runtime, dependency bans) live in clippy,
   cargo-deny and ESLint config, never in a test that reads files as strings.

## Checklist for an agent adding a test

1. Which guard is it: bug, safety, protocol or number? If none, don't write it.
2. Is there already a test for this rule? Add a row to it instead.
3. Does it name a limb, joint, bus or ID, or read the live skeleton for a value? Use a fixture instead.
4. Does it touch private items, mock our own code, or sleep? Rework it through the public seam, `sim-drive`, or by passing the time in.
5. Could it move a real motor? Then it's a bench procedure, not a test.
6. Did this PR delete or change code that other tests guard? Delete or change those tests too.
7. Wrote several tests in one go (agents especially)? Prune to the ones that each guard something different. Pinocchio's
   contribution rules ask for exactly this.

## Sources

What other maintained projects say on the same points, read 2026-11-08:

- rerun TESTING.md: "Test behavior that could plausibly break. Don't add tests for one case out of many that all work the same
  way." https://github.com/rerun-io/rerun/blob/main/TESTING.md
- probe-rs CONTRIBUTING: "avoid tautology. Tests that just describe the implementation bloat up a PR."
  https://github.com/probe-rs/probe-rs/blob/master/CONTRIBUTING.md
- ros2_rust CONTRIBUTING: "Avoid writing tests that simply restate the definition of a function."
  https://github.com/ros2-rust/ros2_rust/blob/main/docs/CONTRIBUTING.md
- rust-analyzer style guide (no `#[ignore]`, no `#[should_panic]`, data-driven tests through one `check` helper) and matklad's
  "How to Test" (sans-IO, fast suite, test features not code):
  https://github.com/rust-lang/rust-analyzer/blob/master/docs/book/src/contributing/style.md,
  https://matklad.github.io/2021/05/31/how-to-test.html
- TigerBeetle deterministic simulation (seed plus commit replays any failure): https://github.com/tigerbeetle/tigerbeetle/blob/main/docs/internals/vopr.md
- dora-rs test ratings (Contract, Smoke, Structural) and test tiers: https://github.com/dora-rs/dora/blob/main/docs/testing-capabilities.md
- uv and probe-rs nextest profiles (slow timeouts, hardware tests filtered out, serial groups):
  https://github.com/astral-sh/uv/blob/main/.config/nextest.toml, https://github.com/probe-rs/probe-rs/blob/master/.config/nextest.toml
- zenoh codec fuzzing and malformed-input tests: https://github.com/eclipse-zenoh/zenoh/tree/main/commons/zenoh-codec
- PX4 evidence rule (SITL test, or a log for hardware-only changes): https://github.com/PX4/PX4-Autopilot/blob/main/CONTRIBUTING.md
- Grafana testing style (Testing Library `*ByRole`, `user-event`; Playwright without mocks):
  https://github.com/grafana/grafana/blob/main/contribute/style-guides/testing.md
- Pinocchio AI policy (prune excess AI-written tests): https://github.com/stack-of-tasks/pinocchio/blob/main/CONTRIBUTING.md

Where projects disagree, this page sides with the robot: Tokio "avoids unit tests" in favour of integration tests, which suits a
library's API but not a sans-IO codec; dora asks for TDD on every change, which is how suites grow out of control; zenoh retries
failing tests twice by default, which hides timing bugs.
