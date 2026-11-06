FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py matcher.py ./
EXPOSE 8081
# single process (no --reload/--workers) so OTel Operator Python injection works
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8081"]
