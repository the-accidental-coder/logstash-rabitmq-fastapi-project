FROM python:3.11-slim

WORKDIR /app

COPY seed.py .

RUN python -c "import sqlite3; print('sqlite3 OK:', sqlite3.sqlite_version)"

CMD ["python", "seed.py"]
