# Contributing to KnowDecay Engine

Thank you for your interest in contributing. Please note the project's proprietary license before submitting any patches.

## Getting Started
1. Fork the repository.
2. Clone your fork locally.
3. Set up the development environment.

## Development Environment
- Use Docker (`docker compose up`) for the easiest setup.
- Alternatively, use local Python 3.11+ and PostgreSQL 16.

## Code Style
We use **Ruff** for linting and formatting. Configuration is in `pyproject.toml`.
- Run linting: `ruff check .`
- Run formatting check: `ruff format --check .`
- Auto-fix issues: `ruff format .` and `ruff check --fix .`

## Testing
We have 1219+ tests that must pass.
- Run tests: `make test` or `pytest tests/ -v --tb=short`
- Ensure required environment variables (`APP_ENV=testing`, `JWT_SECRET_KEY`) are set.

## Git Workflow
1. Branch from `develop`.
2. Write descriptive commit messages.
3. Submit a Pull Request to `develop`.

## Pull Request Requirements
- All tests pass.
- Lint passes (no Ruff errors).
- Documentation (API reference, etc.) updated if changing APIs or architecture.

## Code Review Process
- PRs require at least one approval from a core maintainer.
- CI pipeline must pass completely.

## Documentation Standards
When altering any API routes in `app/api/` or schemas in `app/schemas/`, update `docs/API_REFERENCE.md`. If altering infrastructure, update `docs/INFRASTRUCTURE.md` or `docs/DEPLOYMENT.md`.

## License
**Proprietary / All Rights Reserved**
By contributing, you agree that your contributions are subject to the project's proprietary license and all rights are assigned to the project owners.
