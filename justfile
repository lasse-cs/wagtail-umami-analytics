# List available commands
default:
    @just --list

# Run the test suite, optionally passing pytest args
test *args:
    uv run pytest {{args}}

# Run Ruff lint checks
lint:
    uv run ruff check

# Format Python code with Ruff
format:
    uv run ruff format

# Run the example Wagtail project
dev address="127.0.0.1:8000":
    uv run python example/manage.py runserver {{address}}

# Run management command for the example project
manage *args:
    uv run example/manage.py {{args}}

# Open a Django shell for the example project
shell:
    uv run example/manage.py shell

import? ".justfile.local"
