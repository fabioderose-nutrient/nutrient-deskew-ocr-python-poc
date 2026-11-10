FROM python:3.13-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends libicu76 libfontconfig1 \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY deskew_ocr.py latency.py benchmark.py ./
COPY samples/skewed-scan.pdf samples/
ENTRYPOINT ["python"]
CMD ["latency.py"]
