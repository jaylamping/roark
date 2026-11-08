# TypeScript and UI conventions

**Status:** proposed for Joey's review, 2026-11-08. Joey knows this side better than anyone, so treat the tooling choices
here as defaults he can overrule. The robot-specific rules (sections 3 to 5) are the part that matters most.

Applies to `ui/` and to `mcp/` if it's written in TypeScript. Both are clients of `api`
([architecture.md section 10](architecture.md#10-the-ui-and-agent-tools)): they show state and send requests, and can crash
without affecting motion (tenet 5).

## 1. Tooling

- **TypeScript strict:** `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`,
  `verbatimModuleSyntax`. `tsc --noEmit` runs in CI.
- **Lint:** ESLint flat config with `typescript-eslint`'s `strict-type-checked` and `stylistic-type-checked`, plus the React
  Hooks rules if the UI is React. Prettier for formatting, no style debates.
- **Build:** Vite. One package manager, pinned in `package.json` (`packageManager` field) with a committed lockfile.
- **Tests:** Vitest, Testing Library, MSW, Playwright, per [testing.md](testing.md) (rule 9 limits what the UI tests).
- **Dependencies:** few and maintained, same bar as Rust: every new one gets a reason line in its PR.

## 2. Types

- **`api` types are generated** from the Rust definitions, never hand-written or hand-copied (architecture.md section 10). A
  generated file is never edited by hand; CI checks it's up to date.
- **No `any`.** `unknown` at the edges, narrowed by the generated types or a schema check. `as` casts need a comment saying
  why they're safe.
- **Units in property names** for bare numbers (`positionRad`, `torqueNm`, `tempC`) per
  [units-and-frames.md](units-and-frames.md). If the generated types use snake_case from Rust, keep it rather than mapping.
- **Discriminated unions for states** (drive, limb, robot state, faults), with exhaustive `switch` checked by a `never`
  default. Adding a state on the Rust side then breaks the UI build in every place that must handle it.

## 3. Show what the robot reports, not what was asked

- **No optimistic UI for robot state.** After "enable" is clicked, the joint shows enabled only when `api` reports it enabled.
  Until then it shows "requested". **Why:** an optimistic update that's wrong tells the operator a drive is off when it's
  on.
- **Every live value shows its age,** and turns visibly stale past a threshold set from the data's expected rate. A lost
  connection greys out everything and says so; it never freezes the last numbers as if they were current.
- **Faults are never hidden.** A latched fault stays on screen until it's cleared through `api`. No auto-dismissing toasts for
  faults or stops.
- **Offline is a normal state** (tenet 1): unbuilt limbs and silent drives show as offline, not as errors.

## 4. Commands that move the robot

- The UI holds **no safety logic, limits or hardware facts.** It doesn't clamp, check limits or decide what's safe; `api` and
  the runtime do. The UI may show limits it got from `api`.
- **Commands that can move a motor** (enable, start a plan, clear a fault, change a target) need an explicit confirm step that
  names the joints affected. Stop needs no confirm and is reachable from every screen.
- **Every command shows its outcome:** accepted, refused (with the rule ID from [safety.md](safety.md)), or timed out. A
  command never fails silently.
- No keyboard shortcut or repeat-on-hold for anything that moves a motor, except stop.

## 5. Display

- **Angles in degrees on screen, radians everywhere else.** Convert at the last moment and always label the unit. Other units
  are shown as SI with the unit visible.
- **Times** from `api` are nanosecond stamps; show local time for people and relative age ("0.2 s ago") for live data.
- **Joint and limb names** come from `api` (the skeleton). The UI never hard-codes a joint list.

## 6. Structure

- **Components are views.** Data fetching and the `api` connection live in a small number of hooks or modules, not scattered
  through components.
- **One connection to `api`,** shared. Reconnects automatically with backoff and shows the connection state.
- **No global mutable store** beyond what the data really needs. Server state (what the robot reports) and UI state (what panel
  is open) are kept apart.
- Files stay small, as in Rust: a component file past a few hundred lines wants splitting.
