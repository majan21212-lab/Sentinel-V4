FROM python:3.11-slim

WORKDIR /app

# Install dependencies (if any)
# COPY requirements.txt .
# RUN pip install -r requirements.txt

COPY main.py .

# Expose health check port
EXPOSE 8080

CMD ["python", "main.py"]
