FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi==0.110.0 uvicorn[standard]==0.27.1

COPY server.py .

CMD ["python", "server.py"]