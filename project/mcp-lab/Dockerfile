FROM python:3.12.15-slim

RUN groupadd -g 10001 aitob && \
    useradd -u 10001 -g aitob -s /bin/false aitob

WORKDIR /app

COPY requirements.snapshot.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

USER aitob
CMD ["python", "--version"]
