# Publishing torsor-helper to PyPI

The package is release-ready: `uv build` produces a clean wheel + sdist, the
console script (`torsor`) works from a clean install, and the name
`torsor-helper` is free on PyPI. Publishing is automated via **PyPI Trusted
Publishing** (OIDC) — **no API tokens are stored anywhere**.

## One-time setup (you must do this — it needs your PyPI account)

**Register the Trusted Publisher on PyPI** (once):
Go to <https://pypi.org/manage/account/publishing/> → *Add a new pending publisher* and enter exactly:
- **PyPI Project Name:** `torsor-helper`
- **Owner:** `magnetoid`
- **Repository name:** `torsor-helper`
- **Workflow name:** `publish.yml`
- **Environment name:** *(leave blank — the workflow uses no deployment environment)*

This authorizes the repo's `publish.yml` workflow to upload `torsor-helper` with no secrets. (If you'd rather use a GitHub `pypi` environment for protection rules, add `environment: pypi` back to `publish.yml` and set the Environment name field to `pypi` here — both must match.)

> **Until this is done, every release fails the same way, and the failure reads like a success.**
> The OIDC exchange *works* — the token is accepted — and the upload then returns `400 Non-user
> identities cannot create new projects`, with the real explanation inside an HTML body the log
> prints as wrapped prose. The `verify` job is green, the wheel builds, the wheel installs and
> runs; only the last step fails. v0.6.0 and v0.8.0 both failed here.
>
> After registering the pending publisher, re-run the failed job instead of cutting a new tag:
> ```bash
> gh run rerun <run-id> --failed        # gh run list --workflow publish.yml
> ```

## Cutting a release (repeatable)

1. Bump the version in `src/torsor_helper/__init__.py` (e.g. `__version__ = "0.1.0"`); commit and push to `main`.
2. Tag and publish a GitHub Release:
   ```bash
   git tag v0.1.0 && git push origin v0.1.0
   # Slice just this version's section — the whole CHANGELOG is ~40 KB and
   # attaching it makes the release page unreadable.
   python - <<'EOF' > /tmp/notes.md
   import pathlib
   s = pathlib.Path("CHANGELOG.md").read_text()
   start = s.index("## [0.1.0]")
   print(s[start:s.index("\n## [", start + 1)].strip())
   EOF
   gh release create v0.1.0 --title "v0.1.0" --notes-file /tmp/notes.md
   ```
3. The **Publish to PyPI** workflow runs automatically (build → OIDC upload). Watch it under the repo's *Actions* tab.
4. Verify: `uvx torsor-helper@latest --help` (or `pipx run torsor-helper`).

## Manual fallback (token-based, if you skip Trusted Publishing)

```bash
uv build
uv publish --token "pypi-XXXX"     # or: export UV_PUBLISH_TOKEN=pypi-XXXX; uv publish
```
Create a token at <https://pypi.org/manage/account/token/> (scope it to the project after the first upload).

> Tip: do a dry run against **TestPyPI** first — register the same trusted publisher at
> <https://test.pypi.org/manage/account/publishing/> and `uv publish --publish-url https://test.pypi.org/legacy/`.
