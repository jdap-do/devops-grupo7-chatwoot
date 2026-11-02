FROM python:3.12.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY gateway.py .
USER 10001:10001
EXPOSE 8080 9100
CMD ["python", "gateway.py"]
