FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml alembic.ini ./
COPY alembic/ alembic/
RUN pip install --no-cache-dir .

COPY src/ src/

CMD ["python", "-m", "orchestrator.main"]
