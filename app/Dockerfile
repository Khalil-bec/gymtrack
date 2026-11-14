FROM python:3.11-alpine AS builder

WORKDIR /app

COPY requirements.txt .
RUN python -m venv /opt/venv
RUN /opt/venv/bin/pip install --upgrade pip
RUN /opt/venv/bin/pip install -r requirements.txt



FROM python:3.11-alpine
WORKDIR /app
COPY main.py .
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
EXPOSE 5000
RUN adduser -D -S appuser
USER appuser

CMD [ "python", "main.py" ]