FROM python:3.12.15-slim
WORKDIR /app
COPY requirements.snapshot.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
CMD ["python", "--version"]
