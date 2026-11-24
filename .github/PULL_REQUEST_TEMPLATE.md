## Summary

<!-- Describe the change and its motivation. -->

## Linked issue

<!-- Link an issue, or write "None". -->

## Verification checklist

- [ ] `backend/venv/bin/python -m ruff check backend`
- [ ] `backend/venv/bin/python -m pytest -v backend/tests`
- [ ] `node --check extension/*.js`
- [ ] No secrets, `.env`, generated databases/indexes, or compiled binaries are committed.
- [ ] Documentation and tests are updated where needed.
