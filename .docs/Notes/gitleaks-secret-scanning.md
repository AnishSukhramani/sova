# Gitleaks — Secret Scanning for Git Repos

> A regex-based scanner that blocks API keys, tokens, and credentials from entering git history. We wired it in as a pre-commit hook before Phase 2.

## Key Points

- **What it does:** scans staged changes (or full repo history) for ~150+ secret patterns — AWS keys, GitHub tokens, Slack webhooks, generic API keys, private keys, etc. ([gitleaks repo](https://github.com/gitleaks/gitleaks))
- **How detection works:** primary signal is regex pattern match; secondary signal is Shannon entropy (random-looking strings get flagged even if no rule matches exactly).
- **Two ways to run it:**
  - **Pre-commit hook** — fires automatically on `git commit`; blocks the commit if a finding appears in staged changes.
  - **Manual scan** — `gitleaks detect --source . --verbose` scans the entire git history including past commits.
- **Configuration via `.gitleaks.toml`** at repo root. Extends default rules via `[extend] useDefault = true` and lets you add allowlist regexes for known false positives.
- **Allowlist syntax changed in v8.25.0:** `[allowlist]` (singular) → `[[allowlists]]` (plural, allows multiple). Older syntax still works on most versions. ([config docs](https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml))
- **Allowlist scopes:** match by `regexes` (string content), `paths` (filename regex), `commits` (specific commit SHAs), or `stopwords`. Multiple criteria default to OR; use `condition = "AND"` to require all.
- **Default behavior on findings:** non-zero exit code → pre-commit hook aborts the commit. Override (rarely) with `git commit --no-verify`.
- **Speed:** scans Sova's full history in ~350ms. Lightweight enough to run on every commit without friction.

## How We Used It / Why It Matters

- After leaking a Google Maps key in a chat log, we wired in gitleaks before Phase 2 to make future leaks impossible-by-default.
- Install path: `brew install gitleaks` on host + `brew install pre-commit` + `pre-commit install` to wire the hook into `.git/hooks/`.
- `.pre-commit-config.yaml` references `https://github.com/gitleaks/gitleaks` at rev `v8.21.2`.
- First full scan found 27 findings — all in `Docs/` files, all false positives (5 documented placeholder strings + 22 expired AWS STS tokens captured in Perplexity research output).
- Resolved by writing `.gitleaks.toml` with two specific string-level allowlists. No history rewrite needed — the actual secrets were not real or already dead.
- Hook runs in <500ms; doesn't slow commits perceptibly.

## Key Terminology

- **SAST:** Static Application Security Testing — analyzing code without running it. Gitleaks is one kind of SAST.
- **Pre-commit hook:** a script git runs before finalizing a commit. Lives at `.git/hooks/pre-commit`. If it exits non-zero, the commit aborts.
- **Pre-commit framework:** the Python tool ([pre-commit.com](https://pre-commit.com/)) that manages multiple hooks via a YAML config. Different from the git "pre-commit hook" concept it builds on.
- **Shannon entropy:** a measure of randomness. High entropy = string looks like a generated secret. Used as a fallback when no pattern matches.
- **AWS STS token:** an `ASIA*`-prefixed AWS credential, short-lived (max 36h). Distinct from long-lived `AKIA*` IAM access keys.
- **Allowlist:** the list of known false positives gitleaks should ignore. Maps to `regexes`, `paths`, or `commits` in `.gitleaks.toml`.
- **Stopword:** a substring that, if present in a candidate secret, causes gitleaks to skip it (e.g., `EXAMPLE`, `TEST`).

## Explore Further

- [Official gitleaks repo](https://github.com/gitleaks/gitleaks) — README is the canonical reference; install instructions and rule list live here.
- [Default gitleaks.toml on GitHub](https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml) — read this to see what patterns ship by default. Useful when you wonder "why is this getting flagged?"
- [How to Implement Secret Scanning with Gitleaks (OneUptime)](https://oneuptime.com/blog/post/2026-01-25-secret-scanning-gitleaks/view) — clean walkthrough of the tool + pre-commit pattern.
- [Secret Scanning in CI pipelines using Gitleaks and Pre-commit Hook (DEV.to)](https://dev.to/sirlawdin/secret-scanning-in-ci-pipelines-using-gitleaks-and-pre-commit-hook-1e3f) — local hook + CI-side scanning combo.
- [Gitleaks for Enterprises (Rewanth Tammana)](https://blog.rewanthtammana.com/gitleaks-for-enterprises) — config customization at scale.
- [TruffleHog vs Gitleaks comparison (Jit)](https://www.jit.io/resources/appsec-tools/trufflehog-vs-gitleaks-a-detailed-comparison-of-secret-scanning-tools) — when to use each.
- [YouTube — Stop Leaking Secrets with Gitleaks (May 2025)](https://www.youtube.com/watch?v=FJRUXEP0fFw) — step-by-step visual walkthrough.
- [YouTube — Gitleaks install + test locally (Aug 2025)](https://www.youtube.com/watch?v=VB6yohnukGk) — short, recent.

## FAQs

**Q: Difference between gitleaks and TruffleHog?**
A: Gitleaks tells you a string *looks like* a secret (regex + entropy). TruffleHog tells you the secret *actually works* — it makes live API calls against each candidate to verify validity. Gitleaks is fast (~ms) and runs on every commit; TruffleHog is slower (~minutes) and better suited to periodic deep scans. Most mature teams run both. [Source](https://www.jit.io/resources/appsec-tools/trufflehog-vs-gitleaks-a-detailed-comparison-of-secret-scanning-tools)

**Q: Should I rewrite git history when gitleaks finds a real secret?**
A: Yes — but only after rotating the secret first. Order: (1) rotate the key at the provider, (2) remove the file or scrub the string from history with `git filter-repo` or BFG, (3) force-push (warns collaborators). Skipping step 1 means the key stays live in the public reflog even after history scrubbing.

**Q: What's the right way to allowlist a placeholder string?**
A: Use a **specific string** allowlist, not a broad pattern. Bad: `'''ASIA[A-Z0-9]+'''` (masks all future STS tokens). Good: `'''ASIA2F3EMEYEXE7PR6WM'''` (masks just this expired one). Smallest exception possible.

**Q: Can gitleaks scan files outside git?**
A: Yes — use `gitleaks dir` for a plain filesystem scan, or `gitleaks detect --no-git` to skip git history. The default `gitleaks detect` mode scans staged changes plus git log.

**Q: Why did the gitleaks hook miss a secret I committed?**
A: Three common reasons: (1) the pattern isn't in the default rule set — gitleaks covers ~150 patterns but not every conceivable secret format; (2) the secret was in a file matched by an existing allowlist entry; (3) the hook was bypassed with `--no-verify`. Audit your `.gitleaks.toml` if findings disappear unexpectedly.

**Q: How do I bypass the hook in a real emergency?**
A: `git commit --no-verify`. Do this ONLY for genuine emergencies — and only after manually inspecting the diff for secrets yourself. Habitual `--no-verify` defeats the entire safety net.

**Q: Does gitleaks work in CI?**
A: Yes — there's an official [gitleaks-action](https://github.com/gitleaks/gitleaks-action) GitHub Action. Recommended pattern: local pre-commit hook for fast feedback + CI scan as a backstop for anyone who bypassed the hook.

**Q: Why does my gitleaks scan take longer than expected?**
A: It scans the full git history by default, which scales with repo size. To scan only the latest commit: `gitleaks detect --log-opts="HEAD~1..HEAD"`. To scan only uncommitted changes: `gitleaks protect --staged`.

**Q: What's the relationship between `gitleaks` and the `pre-commit` framework?**
A: They're separate tools. `gitleaks` is the scanner binary. `pre-commit` (from pre-commit.com) is a Python tool that manages and runs hooks defined in `.pre-commit-config.yaml`. We use pre-commit to install + run gitleaks as part of `git commit`. You could also wire gitleaks directly to `.git/hooks/pre-commit` as a shell script, but the pre-commit framework gives you nicer ergonomics (multiple hooks, easy version pinning, easy updates via `pre-commit autoupdate`).
