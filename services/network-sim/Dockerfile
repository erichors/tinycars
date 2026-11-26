FROM python:3.11-slim

RUN pip install --no-cache-dir snmpsim==1.2.2 pysmi==1.6.2

RUN useradd --system --uid 10001 --create-home snmpsim
WORKDIR /app
COPY start.py /app/start.py

USER 10001
EXPOSE 8080 1161/udp 1162/udp 1163/udp 1164/udp 1165/udp 1166/udp 1167/udp 1168/udp 1169/udp

ENTRYPOINT ["python", "/app/start.py"]
