FROM python:3.12-slim

RUN groupadd -g 10001 aitob && \
    useradd -u 10001 -g aitob -s /bin/sh -m aitob

WORKDIR /app
RUN mkdir -p /app/data && chown -R aitob:aitob /app

COPY line_service.py /app/line_service.py
RUN chown -R aitob:aitob /app

USER aitob
EXPOSE 8003

CMD ["python", "-u", "line_service.py"]
