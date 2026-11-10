FROM python:3.13-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends libicu76 libfontconfig1 \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY deskew_ocr.py latency.py benchmark.py ./
COPY samples/skewed-scan.pdf samples/
# Download the OCR models into the image once, so a fresh container (or a
# serverless cold start) does not download them before its first document.
ARG NUTRIENT_OCR_LANGUAGES=eng
ENV NUTRIENT_OCR_LANGUAGES=$NUTRIENT_OCR_LANGUAGES
RUN python deskew_ocr.py samples/skewed-scan.pdf /tmp/warmup.pdf && rm /tmp/warmup.pdf
ENTRYPOINT ["python"]
CMD ["latency.py"]
