# Git, commits and pull requests

**Status:** proposed for Joey's review, 2026-11-08. Who merges and what needs Joey's review is set in
[PLAN "Repo, toolchain, CI and deploy"](../PLAN.md#repo-toolchain-ci-and-deploy); this page is how work gets there.

## 1. Branches

- `main` is always green and always deployable to the Pi. Nobody pushes to it directly; everything lands by PR.
- One branch per piece of work, short-lived, named for what it does: `can-silence-detection`, `skeleton-loader`. Agents may
  use their tool's branch naming.
- Rebase or merge `main` into your own branch as you like before review. Never rewrite history on someone else's branch.

**Why:** a short branch is easy to review and rarely conflicts. A long-lived branch turns into a second codebase.

## 2. Commits

- **Subject line:** imperative, under about 72 characters, says what changes: `Stop the limb after three missed replies`.
  An optional area prefix is fine when it helps (`can: stop after three missed replies`).
- **Body:** why the change is needed and anything a reviewer can't see in the diff (the bench session, the manual page, the
  bug). Wrap around 72 columns.
- **One logical change per commit.** Formatting-only changes go in their own commit.
- No generated files, build output, logs, MCAP sessions or secrets in git. Large bench logs live outside the repo; commits
  cite them by session ID.

**Why:** `git log` and `git blame` are how the next person (or agent) learns why a line exists. "fix stuff" teaches nothing.

## 3. Pull requests

- **Small.** Aim for a PR a reviewer can read in one sitting: one behaviour, one crate where possible, a few hundred lines of
  change. A large change goes in as a stack of PRs, each green on its own. **Why:** review quality drops fast with size;
  safety-relevant code needs real reading, not skimming.
- **Don't mix kinds.** Skeleton value changes, safety rule changes, refactors and features each go in their own PR. A refactor
  PR changes no behaviour.
- **The description says:**
  1. What changes and why, in a few sentences, with the PLAN item or tenet it serves.
  2. How it was checked: the local check command, the `vcan` run, a bench session ID if any.
  3. Anything the reviewer must look at closely (a safety rule, a loosened threshold, a new dependency with its reason line,
     a new seam per [architecture.md section 11](architecture.md#11-changing-the-shape)).
  4. Which tests were added or removed, and what each new one guards ([testing.md](testing.md)).
- **CI green before review.** Don't ask for review on red. Never weaken a lint, test or CI step to get green
  ([rust.md section 15](rust.md#15-rules-for-agents)).
- **Docs move with the code.** If the change moves a seam, renames something, or makes a convention untrue, the same PR
  updates the doc ([docs.md](docs.md)).

## 4. Review

- Joey merges (PLAN). Changes to `robstride`, `can`, `safety` or skeleton values need his review.
- Reviews by agents are welcome as a first pass. They don't replace Joey's review where PLAN requires it.
- Review comments are answered in the thread: fixed (with the commit), or why not. Resolve threads when done.
- Prefer squash-merge for small PRs so `main` reads as one commit per change; a stack of meaningful commits may be
  merged as-is.

## 5. Agents

- Work on a branch, open a PR, never push to `main`.
- Run the local check command before every push ([rust.md section 13](rust.md#13-ci-gates)).
- Keep the PR to what was asked. Spotted something else? Note it in the PR description or open an issue, don't fold it in.
- End commit messages with the attribution lines your tool requires.
