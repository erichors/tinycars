FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends snmp && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY poller.py /app/poller.py
COPY topology.py /app/topology.py
WORKDIR /app
USER 10001
CMD ["python", "poller.py"]
