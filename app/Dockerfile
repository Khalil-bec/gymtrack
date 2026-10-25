FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN python -m venv venv
RUN venv/bin/pip install --upgrade pip
RUN venv/bin/pip install -r requirements.txt



FROM python:3.11-slim
WORKDIR /app
COPY main.py .
COPY --from=builder /app/venv /app/venv
ENV PATH="/app/venv/bin:$PATH"


EXPOSE 5000

CMD [ "python", "main.py" ]