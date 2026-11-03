FROM python:3.13.11-alpine
WORKDIR /app
RUN mkdir /data && chown 65534:65534 /data
COPY receiver.py /app/receiver.py
USER 65534:65534
EXPOSE 8080
CMD ["python", "-B", "/app/receiver.py"]
