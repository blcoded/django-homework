# Shared Household Chores (V1)

A shared household operating system for roommates and shared apartments, featuring fair chore distribution and management.

## Getting Started

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

Install project dependencies using `uv`:

```bash
uv sync
```

### Environment Configuration

Copy the sample environment file:

```bash
cp .env.example .env
```

### Database Migrations

Apply initial Django migrations:

```bash
uv run python manage.py migrate
```

### Running Tests

Run the full test suite with `pytest`:

```bash
uv run pytest
```

Run a specific test file:

```bash
uv run pytest tests/test_home.py
```

Or run via Django's test runner:

```bash
uv run python manage.py test
```

### Development Server

Start the local Django development server:

```bash
uv run python manage.py runserver
```
