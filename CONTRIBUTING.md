# Contributing to FloodSafe

Thank you for your interest in contributing to FloodSafe, a nonprofit flood monitoring platform.

## License

By contributing to FloodSafe, you agree that your contributions will be licensed under the **GNU Affero General Public License v3.0** (AGPL-3.0). See the [LICENSE](LICENSE) file for details.

## How to Contribute

### Reporting Bugs

1. Check existing [issues](https://github.com/aniru888/floodsafe-mvp/issues) to avoid duplicates
2. Open a new issue with:
   - Clear title describing the bug
   - Steps to reproduce
   - Expected vs actual behavior
   - Screenshots if applicable

### Suggesting Features

Open an issue with the `enhancement` label describing:
- The problem you're trying to solve
- Your proposed solution
- Alternative approaches you've considered

### Submitting Code

1. Fork the repository
2. Create a feature branch from `master`
3. Make your changes following our code standards (below)
4. Test your changes thoroughly
5. Submit a pull request

### Code Standards

- **TypeScript**: No `any` types. Define proper interfaces.
- **Python**: Follow PEP 8. Use type hints.
- **Frontend**: React 18 + Tailwind CSS. Components in `apps/frontend/src/components/`.
- **Backend**: FastAPI with layered architecture (`api/` -> `domain/services/` -> `infrastructure/`).
- **Testing**: All changes must pass `npx tsc --noEmit` and `npm run build`.

### Pull Request Process

1. Ensure your PR has a clear description of what changed and why
2. All quality gates must pass (TypeScript, build, tests)
3. PRs require review from a maintainer (@aniru888)
4. Keep PRs focused — one feature or fix per PR

## Code of Conduct

Be respectful and constructive. FloodSafe is a social good project — we welcome contributors of all backgrounds and experience levels.

## Questions?

Open an issue or reach out to the maintainers.
