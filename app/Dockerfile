FROM python:3.11-alpine AS builder

WORKDIR /app

COPY requirements.txt .
RUN python -m venv venv
RUN venv/bin/pip install --upgrade pip
RUN venv/bin/pip install -r requirements.txt



FROM python:3.11-alpine
COPY main.py .
COPY --from=builder /app/venv /app/venv
ENV PATH="/app/venv/bin:$PATH"


EXPOSE 5000

CMD [ "python", "main.py" ]