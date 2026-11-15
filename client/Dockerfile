FROM python:3.13-slim as base

RUN useradd --create-home client
USER client
WORKDIR /client
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY *.py .

FROM base AS runtime
CMD ["python", "main.py"]