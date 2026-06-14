# 05 — GitHub Repositories and External Code References

## Direct GitHub repository dependencies

Eva does **not** declare any GitHub-URL-based packages in `pyproject.toml`. There are no `git+https://...` requirements, no `.gitmodules`, and no packages installed from a GitHub fork. All dependencies are PyPI-resolved (`poetry.lock`).

## GitHub MCP — live repo access

Eva talks to GitHub via the **GitHub Copilot MCP server**, not the GitHub REST API directly.

- **Server URL:** `https://api.githubcopilot.com/mcp/`
- **Transport:** `streamable_http` (LangChain `MultiServerMCPClient`)
- **Auth header:** `Authorization: Bearer <token>`
- **Token source (preferred order):**
  1. **GitHub App installation token** — via `admin_app.services.codebase_indexer.github_app_auth.get_installation_token()` (uses `pygithub` and `PyJWT[crypto]` for JWT signing of the installation request).
  2. **PAT (Personal Access Token)** — `GITHUB_TOKEN` or `GH_SECRET_KEY` env.
- **Repo resolution:** `CODEBASE_REPO_URL` env (parsed by `parse_codebase_repo()` — accepts `https://github.com/owner/repo.git` or `git@github.com:owner/repo.git`). Repo defaults to `main` ref. The actual repo name is **not** hardcoded in Eva.
- **MCP tools used (by name):**
  - `search_code(query)` — keyword search.
  - `get_file_contents(owner, repo, path, ref="main")` — full file read.
  - `list_commits(owner, repo, path, sha, perPage=5)` — commit history.
  - `list_directory(owner, repo, path, ref)` — directory listing (falls back to `get_file_contents` if MCP tool unavailable).
  - `list_files(owner, repo, path, ref, maxResults)` — best-effort listing (falls back).
  - `get_repo_metadata(owner, repo)` — repo info (multiple candidate names tried for compat).

The GitHub Copilot MCP server is publicly available at the URL above; integration is documented by GitHub. Eva's choice to use MCP rather than the GitHub REST API directly means tool descriptions, paging shapes, and rate-limiting are handled by the MCP server, not by Eva.

## Other external code references

### Hugging Face / datasets

None. Eva does not pull any Hugging Face datasets, models, or benchmarks.

### External code copied or adapted

Searched for "adapted from", "based on", "Apache", "BSD", "MIT", "originally from" in the Eva source files — no third-party code excerpts found embedded in the Eva package. All code is original to Neurality.

### Internal cross-repo references

The `eval_agent` package references the four-repo Neurality codebase implicitly:
- `CODEBASE_REPO_URL` points to a GitHub repository (likely `Neurality/neurality_backend` or the monorepo equivalent) which Eva inspects via MCP for SRE investigations.
- `CODEBASE_REPO_ROOT` points to a local clone of that repo for `ripgrep`-based code search.
- The Qdrant collection `"sre_codebase"` (currently dormant) was populated by `celery_app.tasks.codebase_indexer_tasks` from the same repo.

### Knowledge files

The knowledge base is **internal** to this repo:
- `admin_app/services/eval_agent/knowledge/files/*.md` — legacy markdown sources
- `admin_app/services/eval_agent/knowledge/files_yaml/*.yaml` — authoritative YAML sources
- `admin_app/services/eval_agent/knowledge/skills/*.md` — SRE investigation playbooks

None of these reference external GitHub repos or open-source prompt libraries. They are hand-authored by the Neurality team.

## Summary

| Reference type | Count | Detail |
|---|---|---|
| GitHub `git+https://` deps | 0 | None |
| `.gitmodules` | 0 | None |
| External code copied | 0 | None found |
| Hugging Face datasets | 0 | None |
| Live GitHub via MCP | 1 server | `https://api.githubcopilot.com/mcp/` over Bearer auth |
| Internal Qdrant index of codebase | 1 collection | `sre_codebase`, dim 1536, currently disabled |

Eva's "external code" surface is effectively zero — its only runtime dependency on remote GitHub is the live MCP read of `CODEBASE_REPO_URL`.
