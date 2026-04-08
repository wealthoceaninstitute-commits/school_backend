# Smart School FastAPI Backend

Role-based FastAPI backend starter for the Smart School Flutter app.

## Features
- JWT login
- student, parent, teacher, admin roles
- parent -> multiple children
- student timetable, results, homework, attendance
- teacher classes + attendance save
- notices
- SQLite by default, PostgreSQL-ready through DATABASE_URL

## Quick start

```bash
python -m venv .venv
```

Windows:
```bash
.venv\Scripts\activate
```

macOS/Linux:
```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Docs:
- http://127.0.0.1:8000/docs

Demo users, password = `123456`
- student1
- student2
- parent1
- teacher1
- admin1
