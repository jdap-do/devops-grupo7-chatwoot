FROM python:3.13.11-alpine

WORKDIR /app
RUN pip install --no-cache-dir prometheus-client==0.23.1
COPY exporter.py /app/exporter.py
USER 65534:65534
EXPOSE 8000
CMD ["python", "-B", "/app/exporter.py"]
