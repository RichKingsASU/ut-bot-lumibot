FROM python:3.11-slim

WORKDIR /app

COPY docker/news-collector/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "run_news_collector.py"]
