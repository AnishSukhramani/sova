# Sova — Claude Project Rules

## Project Context

- **Project:** Sova — Django backend (replacing a legacy JavaScript-based system)
- **Developer:** Junior developer learning Django and backend engineering
- **Goal:** Build a modular, scalable Django backend. Teach as we build.
- **Environment:** Single environment (local). Foundation should support multi-env later but don't add that complexity now.
- **Database:** Local PostgreSQL (user has PGAdmin 4 installed)

## Ground Rules

### Git — HARD RULE

- DO NOT run any Git action commands under any circumstance.
- This includes: `git init`, `git add`, `git commit`, `git push`, `git pull`, `git checkout`, `git switch`, `git branch`, `git merge`, `git rebase`, `git reset`, `git stash`, `git restore`, `git worktree`
- Read-only Git commands are allowed: `git log`, `git diff`, `git status`, `git show`, `git branch --list`
- The developer handles all Git operations themselves.

### Architectural Patterns

- Do NOT enforce any architectural patterns without first explaining them and getting buy-in.
- Always explain WHY before suggesting a pattern.
- The developer may override suggestions due to time constraints — respect that.

### Communication Style

- Developer is a junior learning to think like a senior engineer.
- Explain technical concepts in simple language — practical, not academic.
- No padding, no unnecessary filler text. Be crisp.
- When introducing a technical term, define it briefly inline.

### Code Philosophy

- Modular, surgical, no bloat.
- Don't add features or abstractions beyond what was asked.
- Don't add error handling for impossible scenarios.
- Don't create helpers for one-time use.

## Custom Commands

- `/tldr` — TLDR explanation of a concept. No code changes, no Git.
- `/mentor` — Deep teaching session based on what we discussed. No code changes, no Git.
- `/take-notes` — Create a markdown note in the `/Notes` folder. No code changes, no Git.
- `/brainstorm` — Senior engineer brainstorm mode with web research. No code changes, no Git.
- `/blog` — Document the session as a professional engineering blog entry, saved to `/Docs/case-study/`.

## Notes Folder

All session notes live in `/Notes/`. Files are markdown, named descriptively in kebab-case.