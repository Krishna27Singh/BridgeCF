# Contributing to BridgeCF

Thanks for helping improve BridgeCF. Small, focused pull requests are welcome.

## Local development

1. Install Python 3.11+, a C++17 compiler, `make`, and Node.js.
2. Set up the Python environment and dependencies:

   ```bash
   python3 -m venv backend/venv
   source backend/venv/bin/activate
   python -m pip install -r backend/requirements.txt
   ```

3. Build the native graph engine:

   ```bash
   make -C backend
   ```

4. Configure a provider in `backend/.env` (copy `backend/.env.example`; never commit the resulting `.env`). To try the API, ingest a small catalog and start the server:

   ```bash
   cd backend
   ./venv/bin/python -m app.scripts.build_knowledge_base --limit 1000
   ./venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

5. To load the extension locally, open `chrome://extensions/`, enable **Developer mode**, choose **Load unpacked**, and select this repository's `extension/` folder. Set the API Base URL in the popup to `http://127.0.0.1:8000`.

## Verification

Run the backend checks, extension syntax check, and deterministic offline evaluation from the repository root:

```bash
backend/venv/bin/python -m ruff check backend
backend/venv/bin/python -m pytest -v backend/tests
node --check extension/*.js
PYTHONPATH=backend backend/venv/bin/python -m evals.run_evals --mode offline
```

The live evaluation calls the configured LLM provider and should be run deliberately:

```bash
PYTHONPATH=backend backend/venv/bin/python -m evals.run_evals --mode live
```

## Branches and commits

Use descriptive branch prefixes:

- `feat/` for user-facing capabilities
- `fix/` for bug fixes
- `chore/` for maintenance
- `docs/` for documentation

Use [Conventional Commits](https://www.conventionalcommits.org/) because Release Please uses commit messages to determine release versions and changelog entries. Examples:

```text
feat(extension): add keyboard-accessible hint accordions
fix(backend): handle missing FAISS vectors during retrieval
docs: clarify local setup
```

## Pull request checklist

- [ ] Explain the problem and the approach; link a related issue when available.
- [ ] Keep changes focused and preserve existing API and extension contracts.
- [ ] Run Ruff, the backend test suite, extension JavaScript syntax checks, and offline evaluations where relevant.
- [ ] Add or update tests for behavior changed by the pull request.
- [ ] Update user-facing documentation when behavior or setup changes.
- [ ] Confirm no secrets, generated databases/indexes, or compiled binaries are included.

Never commit `.env`, `bridgecf.db`, `vector_database.index`, or compiled `.so` binaries.
