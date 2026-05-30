# Code Conventions

## Naming
- Functions and variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private/internal helpers: leading underscore (`_helper`)

## Type Hints and Docstrings
- Add type hints for public helpers and service interfaces
- Keep route handlers readable; annotate helpers and reusable logic first
- Add concise docstrings to public functions and classes

## Error Handling
- Validate input early and return structured JSON errors
- Prefer explicit status codes (`400`, `401`, `403`, `404`, `409`)
- Log unexpected exceptions with context before returning `500`

## Logging
- Use module-level loggers: `logger = logging.getLogger(__name__)`
- Avoid `print()` in backend runtime code
- Include IDs/context in log statements (user/config/schedule ids)

## API Style
- Use Flask blueprints by domain in `app/routes`
- Keep route logic thin; move reusable logic to `services` or `utils`
- Mutating endpoints should emit audit entries where applicable

## Formatting and Linting
- Black line length: `100`
- isort profile: `black`
- Flake8 checks in pre-commit before commits
- Run locally:
  - `python -m black backend`
  - `python -m isort backend`
  - `python -m flake8 backend/app`

## Imports
- Prefer absolute package-relative imports inside `backend.app`
- Keep fallback imports only where script-execution compatibility is required
