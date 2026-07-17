import os
import json
import logging
import asyncio
import httpx
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

import nats

from hermes.base_agent import HermesAgent

logger = logging.getLogger("HermesNewsCollector")

class NewsCollector(HermesAgent):
    def __init__(self):
        super().__init__(
            name="hermes_news_collector",
            interval_seconds=300,
            market_hours_only=False
        )
        self.finnhub_key = os.getenv("FINNHUB_API_KEY")
        self.crypto_symbols = os.getenv("CRYPTO_SYMBOLS", "BTC,ETH").split(",")
        
        self.reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
        self.reddit_client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        self.reddit_user_agent = os.getenv("REDDIT_USER_AGENT", "DisruptingAlpha/1.0")

    async def _fetch_finnhub(self, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        articles = []
        if not self.finnhub_key:
            return articles
            
        endpoints = [
            ("general", f"https://finnhub.io/api/v1/news?category=general&token={self.finnhub_key}"),
            ("forex", f"https://finnhub.io/api/v1/news?category=forex&token={self.finnhub_key}")
        ]
        
        for symbol in self.crypto_symbols:
            endpoints.append((f"crypto-{symbol}", f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={datetime.now(timezone.utc).strftime('%Y-%m-%d')}&to={datetime.now(timezone.utc).strftime('%Y-%m-%d')}&token={self.finnhub_key}"))

        for source_tag, url in endpoints:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                for item in data:
                    ts = item.get("datetime")
                    pub_date = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc)
                    articles.append({
                        "id": f"fh_{item.get('id')}",
                        "headline": item.get("headline", ""),
                        "summary": item.get("summary", ""),
                        "url": item.get("url", ""),
                        "source": f"finnhub_{source_tag}",
                        "published_at": pub_date.isoformat(),
                    })
            except Exception as e:
                logger.error(f"Finnhub fetch error for {source_tag}: {e}")
                
        return articles

    async def _fetch_reddit(self) -> List[Dict[str, Any]]:
        articles = []
        if not self.reddit_client_id or not self.reddit_client_secret:
            return articles
            
        try:
            import asyncpraw
            reddit = asyncpraw.Reddit(
                client_id=self.reddit_client_id,
                client_secret=self.reddit_client_secret,
                user_agent=self.reddit_user_agent
            )
            
            subreddits = ["wallstreetbets", "investing", "stocks", "CryptoCurrency"]
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(hours=2)
            
            for sub_name in subreddits:
                subreddit = await reddit.subreddit(sub_name)
                async for post in subreddit.hot(limit=50):
                    if post.score <= 50:
                        continue
                    pub_date = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
                    if pub_date < cutoff:
                        continue
                        
                    articles.append({
                        "id": f"rd_{post.id}",
                        "headline": post.title,
                        "summary": getattr(post, "selftext", "")[:500],
                        "url": f"https://reddit.com{post.permalink}",
                        "source": f"reddit_{sub_name}",
                        "published_at": pub_date.isoformat(),
                    })
            
            await reddit.close()
        except Exception as e:
            logger.error(f"Reddit fetch error: {e}")
            
        return articles

    async def _fetch_stocktwits(self, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        articles = []
        symbols = ["IWM", "SPY", "QQQ", "BTC.X", "ETH.X"]
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=2)
        
        for symbol in symbols:
            try:
                url = f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                
                messages = data.get("messages", [])
                for msg in messages:
                    pub_str = msg.get("created_at")
                    if not pub_str: continue
                    pub_date = datetime.strptime(pub_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    if pub_date < cutoff:
                        continue
                        
                    articles.append({
                        "id": f"st_{msg.get('id')}",
                        "headline": msg.get("body", "")[:100],
                        "summary": msg.get("body", ""),
                        "url": f"https://stocktwits.com/message/{msg.get('id')}",
                        "source": f"stocktwits_{symbol}",
                        "published_at": pub_date.isoformat(),
                    })
            except Exception as e:
                logger.error(f"StockTwits fetch error for {symbol}: {e}")
                
        return articles

    async def run_cycle(self) -> None:
        async with httpx.AsyncClient(timeout=15.0) as client:
            finnhub_articles = await self._fetch_finnhub(client)
            stocktwits_articles = await self._fetch_stocktwits(client)
            
        reddit_articles = await self._fetch_reddit()
        
        all_articles = finnhub_articles + reddit_articles + stocktwits_articles
        
        if not all_articles:
            return

        # Fetch last 2 hours from DB for deduplication
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        db_url = f"{self.supabase_url}/rest/v1/hermes_news_feed"
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
        }
        
        existing_ids = set()
        existing_urls = set()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    db_url, 
                    headers=headers, 
                    params={"created_at": f"gt.{cutoff}", "select": "id,url"}
                )
                resp.raise_for_status()
                for row in resp.json():
                    existing_ids.add(row.get("id"))
                    existing_urls.add(row.get("url"))
        except Exception as e:
            logger.error(f"Failed to fetch existing articles from DB: {e}")
            return

        crypto_keywords = ["crypto", "bitcoin", "btc", "ethereum", "eth", "coinbase", "binance", "blockchain"]
        
        nc = None
        try:
            nc = await nats.connect(os.getenv("NATS_URL", "nats://localhost:4222"))
            js = nc.jetstream()
        except Exception as e:
            logger.error(f"Failed to connect to NATS JetStream: {e}")

        new_records = []
        for a in all_articles:
            if a["id"] in existing_ids or a["url"] in existing_urls:
                continue
                
            text_to_check = (a["headline"] + " " + a["summary"]).lower()
            asset_class = "equities"
            if any(k in text_to_check for k in crypto_keywords):
                asset_class = "crypto"
                
            a["asset_class"] = asset_class
            a["nats_subject"] = f"news.{asset_class}"
            a["published_to_nats"] = False
            
            # Publish to NATS
            if nc:
                try:
                    payload = {
                        "id": a["id"],
                        "headline": a["headline"],
                        "summary": a["summary"],
                        "url": a["url"],
                        "source": a["source"],
                        "published_at": a["published_at"],
                        "asset_class": asset_class,
                        "raw_sentiment": None
                    }
                    await js.publish(a["nats_subject"], json.dumps(payload).encode())
                    a["published_to_nats"] = True
                except Exception as e:
                    logger.error(f"Failed to publish {a['id']} to NATS: {e}")
            
            new_records.append(a)
            existing_ids.add(a["id"])
            existing_urls.add(a["url"])
            
        if new_records:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        db_url,
                        headers={**headers, "Content-Type": "application/json", "Prefer": "resolution=ignore-duplicates"},
                        json=new_records
                    )
                    resp.raise_for_status()
            except Exception as e:
                logger.error(f"Failed to insert new articles to DB: {e}")

        if nc:
            await nc.close()
