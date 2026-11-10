# Documentation conventions

**Status:** proposed for Joey's review, 2026-11-08.

Docs exist so an agent or a person new to the repo knows within minutes what every piece does (tenet 7), and so nobody has to
ask Joey the same question twice. They are also the easiest thing in a repo to let rot, which is how the legacy stack ended up
with ADRs and agent guides that described code that no longer existed. These rules keep them few, current and true.

## 1. Which doc holds what

| Doc | Holds | Doesn't hold |
|---|---|---|
| [TENETS.md](../TENETS.md) | How every change is judged | How to build anything |
| [PLAN.md](../PLAN.md) | What to build, in order, and the software-side facts and values it needs | Code style |
| `conventions/` | How code, config, tests and procedures are written and reviewed | Values (link PLAN, the skeleton or STATUS.md instead) |
| [architecture.md](architecture.md) | The map: processes, crates, seams, data flows | Per-crate detail |
| Crate `README.md` (the crate doc, through `include_str!`) | What the crate does, what it must never do, what it talks to, how to use it, with an example that runs ([rust.md section 11](rust.md#11-shape-and-readability-tenet-7)) | The map (link [architecture.md](architecture.md)), tutorials |
| `config/skeleton.yaml` | Joint facts, each with a source comment ([skeleton.md](skeleton.md)) | Schema docs (those are on the loader) |
| [STATUS.md](https://github.com/jaylamping/marengo/blob/main/hardware/STATUS.md) (marengo) | Hardware state and facts | Software decisions |
| [hardware/power-board/](../hardware/power-board/README.md) | The power board's design of record: schematic, layout, parts, and what software must do for it | Software decisions |
| README.md | What the repo is, how to build and run, links to the above | Anything that changes often |

PLAN's "Which file wins" table settles conflicts.

## 2. One fact, one place

A number, name, ID, limit or rule is written down once and linked from everywhere else. If you're about to copy a value into a
doc, link to where it lives instead. **Why:** two copies drift, and the reader can't tell which one is stale (tenet 2). This
applies to these convention pages too: they link PLAN for values.

## 3. Describe what exists

- Docs describe what exists and what was decided, not what might be built (tenet 4). "Later we could..." is deleted.
- A doc that's no longer true is fixed or deleted **in the PR that made it untrue**, not in a later clean-up.
- No ADR folder by default. A decision is recorded where it applies (PLAN, a convention page, the crate README) with the date
  and who decided. If a decision really needs its own page (rare: a trade-off that will be questioned again), it gets one
  short page with the options, the choice and the reason, and is deleted when the code it describes is.
- No per-folder `AGENTS.md` files or agent-only guides. Agents read the same docs as people: CLAUDE.md points them here.

## 4. How to write

- **Plain English, short sentences.** Write for a capable reader who is new to this repo and possibly to Rust.
- **Rules come with their reason.** A **Why:** line after any rule that isn't obvious. A rule without a reason gets ignored the
  first time it's inconvenient, and can't be judged when circumstances change.
- **Tables for facts and comparisons, lists for steps, prose for reasoning.**
- **Link, don't paste.** Link files by relative path in this repo and by full GitHub URL into marengo. A crate `README.md` is
  the exception: it is also rendered by `cargo doc`, where relative links break, so it links by full GitHub URL.
- **Dates are absolute** (2026-11-08), and decisions name who made them ("Joey, 2026-11-08").
- **Names say what things do** (tenet 7). No codenames, no robot name except the skeleton's `name:`, no limb names for things
  that aren't limb-specific (tenet 1).
- **Comments in code say why, not what** ([rust.md section 11](rust.md#11-shape-and-readability-tenet-7)). Magic numbers cite a
  manual section, a bench session or a tenet.

## 5. TODOs have an owner

A `TODO` in code or docs is written `TODO(name)` or links an issue. A bare `TODO` fails CI. **Why:** an ownerless `TODO` is a
wish nobody will grant; with a name or an issue it's tracked work, or it gets deleted. (rerun enforces this in CI.)

## 6. Keeping the map current

[architecture.md](architecture.md) is updated in the same PR as any change listed in its section 11 (a new process, crate,
dependency edge, queue, `api` message or owner of state). A reviewer who sees one of those without a map change asks for it.

## 7. Milestone sweep

At the end of each milestone, alongside the test sweep in [testing.md rule 10](testing.md#rule-10-delete-tests-as-eagerly-as-you-add-them):
read every doc in the repo once, and fix or delete anything that's no longer true. PLAN calls for the same sweep over the
legacy docs before the old stack is deleted.
