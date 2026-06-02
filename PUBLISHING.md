# Publishing torsor-helper to PyPI

The package is release-ready: `uv build` produces a clean wheel + sdist, the
console script (`torsor`) works from a clean install, and the name
`torsor-helper` is free on PyPI. Publishing is automated via **PyPI Trusted
Publishing** (OIDC) — **no API tokens are stored anywhere**.

## One-time setup (you must do this — it needs your PyPI account)

1. **Create the GitHub `pypi` environment** (once):
   GitHub repo → *Settings → Environments → New environment* → name it `pypi`.
   (Optionally add a required reviewer for extra safety.)

2. **Register the Trusted Publisher on PyPI** (once):
   Go to <https://pypi.org/manage/account/publishing/> → *Add a new pending publisher* and enter exactly:
   - **PyPI Project Name:** `torsor-helper`
   - **Owner:** `magnetoid`
   - **Repository name:** `torsor-helper`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi`

   This authorizes the repo's `publish.yml` workflow to upload `torsor-helper` with no secrets.

## Cutting a release (repeatable)

1. Bump the version in `src/torsor_helper/__init__.py` (e.g. `__version__ = "0.1.0"`); commit and push to `main`.
2. Tag and publish a GitHub Release:
   ```bash
   git tag v0.1.0 && git push origin v0.1.0
   gh release create v0.1.0 --title "v0.1.0" --notes-file CHANGELOG.md
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
