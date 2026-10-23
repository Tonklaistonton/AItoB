FROM python:3.12.15-slim

# Create dedicated non-root user and group (CIS Docker Benchmark 4.1)
RUN groupadd -g 10001 aitob && \
    useradd -u 10001 -g aitob -s /sbin/nologin -M aitob

WORKDIR /app

COPY requirements.snapshot.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm -f /tmp/requirements.txt

# Ensure non-root user owns the working directory
RUN chown -R 10001:10001 /app

# Switch to non-root user for runtime execution
USER 10001:10001

CMD ["python", "--version"]
