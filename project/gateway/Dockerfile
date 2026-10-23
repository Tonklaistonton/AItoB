FROM python:3.12.15-slim

RUN groupadd -g 10001 aitob && \
    useradd -u 10001 -g aitob -s /bin/false aitob

WORKDIR /app
COPY . /app

USER aitob
EXPOSE 8000

CMD ["python", "-u", "gateway.py"]
