FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY *.py ./
RUN useradd --create-home --uid 10001 app
USER app

FROM base AS checks
USER root
COPY requirements-dev.txt pyproject.toml ./
COPY tests ./tests
RUN python -m pip install --no-cache-dir -r requirements-dev.txt
USER app
CMD ["python", "-m", "pytest", "-p", "no:cacheprovider"]

FROM base AS runtime
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).close()"]
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
