# Contributing to faithful

Thank you very much for wanting to contribute! I really appreciate any contribution you would like to make, whether it's a PR or a bug report.

## Dev setup

```bash
git clone https://github.com/a9lim/faithful
cd faithful
pip install -e ".[dev]"
```

The `dev` extra pulls in ruff, pytest, build, twine, and all three backend SDKs (openai, google-genai, anthropic), so the test suite can import every backend module.

If you want only one backend, the per-backend extras are `[openai]`, `[gemini]`, and `[anthropic]`. The openai-compatible backend uses the `openai` package, so `[openai]` covers both.

## Lint

CI runs `ruff check .` on every PR. Please run it locally first:

```bash
ruff check .
ruff check . --fix    # auto-fix what's fixable
```

## Tests

```bash
pytest tests/ -v
```

All tests run on CPU; no Discord or LLM provider is contacted.

If you add a new backend or a new verb, please add tests in the same style as the existing ones in `tests/`.

## PRs

- Please don't bump the version in your PR unless you want a release. The PyPI publish workflow is triggered by a version bump on `main`.
- If you touched a backend, please mention which provider and model you tested against in the PR description.
- If you touched the wizard, doctor, or onboarding flows, please run them end to end before opening the PR.
- Small PRs are easier to review than big ones. If you're unsure, please open an issue first so we can sketch it together.

## Questions

Please open an issue or reach out to me. For anything security-sensitive, please see [SECURITY.md](SECURITY.md).
