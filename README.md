# Splitwise Clone with CSV Import

A full-stack shared expense management application inspired by Splitwise, extended with a CSV import engine capable of detecting and handling anomalies in messy real-world expense data.

## Features

* JWT Authentication
* Group Management
* Dynamic Membership Changes
* Expense Tracking
* Equal, Unequal, Percentage and Shares Splits
* Balance Summaries
* Debt Simplification
* Settlements
* Expense Chat
* CSV Import Engine
* Import Anomaly Detection
* Import Reporting

## Tech Stack

Backend:

* Django
* Django REST Framework
* Django Channels
* PostgreSQL
* Redis
* SimpleJWT

Frontend:

* React
* TypeScript
* Vite
* Tailwind CSS
* Zustand
* React Query

## Setup

Backend:

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## AI Used

AI tools used:

* Antigravity
* ChatGPT

The developer reviewed, tested, and modified all generated output.

## Tests

* Backend Tests: 411 passing
* CSV Import Tests: 48 passing
