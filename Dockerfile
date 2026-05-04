FROM python:3.13-alpine

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY config.yaml .

RUN mkdir -p /app/sync_state

EXPOSE 5000

CMD ["python", "-m", "app"]
