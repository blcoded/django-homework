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

### Demonstration Household Seed Script

Populate a comprehensive, realistic demo household with 4 roommates, active recurring chores, 8 weeks of historical completion logs, personal streaks, milestone badges, chore suggestions, active swaps, and scheduled absences:

```bash
uv run python manage.py seed_demo_household --clear
```

**Demo Household Credentials:**
- **Household Name:** `Baker Street 221B` (Invite Code: `BAKER-221B`)
- **Default Password for all demo accounts:** `Pass1234!`
- **Roommates:**
  - `alice@example.com` (Alice Smith)
  - `bob@example.com` (Bob Jones)
  - `charlie@example.com` (Charlie Brown)
  - `dana@example.com` (Dana Scully)

### Background Periodic Tasks Runner

Execute background activation checks, deadline missed-transitions, and reminder notifications synchronously:

```bash
uv run python manage.py run_periodic_tasks
```

### End-to-End Integration Tests

Run the complete end-to-end integration test suite verifying the seed command and full roommate lifecycle:

```bash
uv run pytest tests/test_demo_e2e.py
```

### Frontend Next.js Web Application

The frontend is built with Next.js App Router, Tailwind CSS, and Lucide icons in `frontend/`:

```bash
cd frontend
npm install
npm run dev
```

Run frontend unit and component tests:

```bash
cd frontend
npm test
```

Build production bundle:

```bash
cd frontend
npm run build
```

