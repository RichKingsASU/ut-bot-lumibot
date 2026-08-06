FROM python:3.11-slim

WORKDIR /app

COPY docker/sentiment-scorer/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "run_sentiment_scorer.py"]
