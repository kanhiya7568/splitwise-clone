# Splitwise Clone

A full-stack expense sharing application inspired by Splitwise.

## Features

### Authentication

* User Registration
* User Login
* JWT Authentication
* Token Refresh
* Logout with Refresh Token Blacklisting

### Groups

* Create Groups
* View Groups
* Invite Members
* Remove Members
* Group Details

### Expenses

* Create Expenses
* Edit Expenses
* Delete Expenses
* Expense History
* Expense Filtering

### Split Types

* Equal Split
* Unequal Split
* Percentage Split
* Shares Split

### Balances

* Group-wise Balances
* Overall Balances
* Simplified Debt View

### Settlements

* Record Settlements
* Settlement History

### Expense Chat

* Real-time messaging using WebSockets
* Message History
* Soft Delete Messages

---

## Tech Stack

### Backend

* Django
* Django REST Framework
* PostgreSQL
* Django Channels
* Redis
* SimpleJWT

### Frontend

* React
* TypeScript
* Vite
* Tailwind CSS
* Zustand
* React Query
* Axios

---

## Test Summary

Backend automated tests passing:

* Authentication
* Groups
* Expenses
* Balances
* Debt Simplification
* Settlements
* Chat

**Total: 411 tests passed**

---

## Setup

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## Deployment

Frontend: Vercel

Backend: Render

---

## GitHub Repository

https://github.com/kanhiya7568/splitwise-clone

---

## Author

Kanhiya Singh
