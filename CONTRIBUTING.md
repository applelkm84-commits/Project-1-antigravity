# Contributing

Contributions that make Antigravity simpler, safer, or easier to adopt are welcome.

## Before opening a pull request

- Keep changes narrowly scoped.
- Add or update tests for behavioral changes.
- Update documentation when commands or workflow behavior change.
- Do not add telemetry, network calls, or new runtime dependencies without explaining why they are necessary.
- Never commit secrets, private customer data, proprietary prompts, or credentials.

## Development

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e . pytest
pytest
```

## Issues

A useful issue includes:

- the problem or workflow friction;
- the expected behavior;
- a minimal example when possible;
- whether the issue affects correctness, safety, token usage, or developer experience.

## Pull requests

Please describe:

1. what changed;
2. why the change is needed;
3. how it was verified;
4. any compatibility or security implications.

By contributing, you agree that your contribution is licensed under the MIT License.
