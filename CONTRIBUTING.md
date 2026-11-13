# Contributing to AI RED TEAM

- All work stays on Kali; the Windows machine is an external, authorized lab target only.
- Run the backend with Python 3.13 (`make test` / `make start`); do not rebuild the venv casually.
- Never commit secrets — `backend/.env` is gitignored. Use `backend/.env.example` as the template.
- Preserve the Safety Gateway, Execution Registry, kill switch and audit; do not add attack capabilities or bypass authorization.
- Keep commits small and scoped. Run `make test typecheck build` before pushing.
