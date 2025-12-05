FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

FROM base AS api
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS streamlit
CMD ["streamlit", "run", "src/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]

FROM base AS pipeline
CMD ["python", "-m", "src.territory_pipeline"]
