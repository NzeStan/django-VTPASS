# Contributing

```bash
git clone https://github.com/NzeStan/django-vtpass
cd django-vtpass
pip install -e ".[test]"
pytest
flake8 vtpass tests
tox            # full Django/Python matrix
```

Guidelines:

- Never make a real HTTP call in tests. Mock VTpass with `responses` (see `tests/conftest.py`).
- Any change that moves money needs tests for success, failure, pending and reversal.
- Money is always `Decimal`. Never use floats.
- New settings go in `vtpass/settings.py` `DEFAULTS` and in `docs/configuration.md`.
- Model changes need a migration: `DJANGO_SETTINGS_MODULE=tests.settings django-admin makemigrations vtpass`.
  Keep migrations loadable on Django 4.2 (use `vtpass.models.base.check_constraint`).

## Releasing

1. Bump `vtpass/__init__.py` `__version__` and update `docs/changelog.md`.
2. `python -m build && twine check dist/*`
3. `twine upload dist/*`
