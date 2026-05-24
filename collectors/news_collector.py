import asyncio
import os
import sys
import logging
import hashlib
import httpx
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

from collectors.base_collector import BaseCollector

logger = logging.getLogger("NewsCollector")

# Smart docker/localhost detection
IS_DOCKER = os.path.exists("/.dockerenv")
DEFAULT_NATS_URL = "nats://nats:4222" if IS_DOCKER else "nats://localhost:4222"

class NewsCollector(BaseCollector):
    def __init__(self, nats_url: str = DEFAULT_NATS_URL):
        super().__init__(nats_url)
        load_dotenv()
        self.finnhub_key = os.getenv("FINNHUB_API_KEY", "placeholder_finnhub_api_key")
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        # Deduplication cache (set of URL hashes)
        self.seen_url_hashes = set()
        
        # RSS Feeds to poll
        self.rss_feeds = {
            "Cointelegraph": "https://cointelegraph.com/rss",
            "Decrypt": "https://decrypt.co/feed",
            "BitcoinMagazine": "https://bitcoinmagazine.com/.rss/full/"
        }
        
        self.http_client = httpx.AsyncClient(timeout=15.0)

    def _get_url_hash(self, url: str) -> str:
        return hashlib.md5(url.strip().encode("utf-8")).hexdigest()

    async def _init_seen_hashes(self):
        """Pre-populate seen URL hashes from Supabase to prevent duplicate inserts across restarts."""
        if not self.supabase_url or not self.supabase_key:
            logger.warning("[NEWS] Supabase credentials missing. Deduplication will be in-memory only.")
            return
            
        try:
            logger.info("[NEWS] Loading existing articles from Supabase for deduplication...")
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
            }
            resp = await self.http_client.get(
                f"{self.supabase_url}/rest/v1/news_articles?select=url",
                headers=headers,
                timeout=10.0
            )
            if resp.status_code == 200:
                data = resp.json()
                for article in data:
                    url = article.get("url")
                    if url:
                        self.seen_url_hashes.add(self._get_url_hash(url))
                logger.info(f"[NEWS] Loaded {len(self.seen_url_hashes)} seen article hashes.")
            else:
                logger.warning(f"[NEWS] Failed to load articles from Supabase ({resp.status_code}): {resp.text[:200]}")
        except Exception as e:
            logger.error(f"[NEWS] Error loading articles from Supabase: {e}")

    async def _write_to_supabase(self, article: dict):
        """Write article to Cloud Supabase news_articles table."""
        if not self.supabase_url or not self.supabase_key:
            return
            
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        try:
            # Table fields: id (auto), title, url, source, published_at, summary, sentiment_score, created_at (auto)
            row = {
                "title": article["title"],
                "url": article["url"],
                "source": article["source"],
                "published_at": article["published_at"],
                "summary": article["summary"],
                "sentiment_score": None  # Placeholder for Phase 3 scoring
            }
            
            resp = await self.http_client.post(
                f"{self.supabase_url}/rest/v1/news_articles",
                headers=headers,
                json=row,
                timeout=10.0
            )
            if resp.status_code not in (200, 201):
                logger.warning(f"[NEWS] Supabase insert failed ({resp.status_code}): {resp.text[:200]}")
        except Exception as e:
            logger.error(f"[NEWS] Supabase insert error: {e}")

    async def poll_finnhub(self):
        """Poll Finnhub API for crypto news."""
        if not self.finnhub_key or "placeholder" in self.finnhub_key:
            logger.warning("[NEWS] Finnhub API key is placeholder. Skipping Finnhub polling.")
            return

        try:
            logger.info("[NEWS] Polling Finnhub for crypto news...")
            url = f"https://finnhub.io/api/v1/news?category=crypto&token={self.finnhub_key}"
            resp = await self.http_client.get(url)
            if resp.status_code == 200:
                articles = resp.json()
                new_count = 0
                for item in articles:
                    # Finnhub keys: headline, url, source, datetime, summary
                    title = item.get("headline", "").strip()
                    url_str = item.get("url", "").strip()
                    source = item.get("source", "").strip() or "Finnhub"
                    summary = item.get("summary", "").strip()
                    ts = item.get("datetime", 0)
                    
                    if not url_str or not title:
                        continue
                        
                    url_hash = self._get_url_hash(url_str)
                    if url_hash in self.seen_url_hashes:
                        continue
                        
                    self.seen_url_hashes.add(url_hash)
                    new_count += 1
                    
                    published_at = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
                    
                    article = {
                        "title": title,
                        "url": url_str,
                        "source": source,
                        "published_at": published_at,
                        "summary": summary
                    }
                    
                    # 1. Publish to NATS
                    await self.publish("news.crypto", article)
                    
                    # 2. Write to Supabase
                    await self._write_to_supabase(article)
                    
                logger.info(f"[NEWS] Finnhub poll complete. Discovered {new_count} new articles.")
            else:
                logger.error(f"[NEWS] Finnhub API returned status {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.error(f"[NEWS] Error polling Finnhub: {e}")

    async def poll_rss(self):
        """Poll RSS feeds."""
        logger.info("[NEWS] Polling RSS feeds...")
        for source, url in self.rss_feeds.items():
            try:
                # Add User-Agent to avoid blockage
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                resp = await self.http_client.get(url, headers=headers)
                if resp.status_code != 200:
                    logger.warning(f"[NEWS] RSS Feed {source} returned {resp.status_code}")
                    continue
                    
                root = ET.fromstring(resp.text.encode("utf-8"))
                channel = root.find("channel")
                if channel is None:
                    continue
                    
                new_count = 0
                for item in channel.findall("item"):
                    title = item.findtext("title", "").strip()
                    url_str = item.findtext("link", "").strip()
                    summary = item.findtext("description", "").strip() or item.findtext("summary", "").strip()
                    pub_date = item.findtext("pubDate", "").strip()
                    
                    if not url_str or not title:
                        continue
                        
                    url_hash = self._get_url_hash(url_str)
                    if url_hash in self.seen_url_hashes:
                        continue
                        
                    self.seen_url_hashes.add(url_hash)
                    new_count += 1
                    
                    # Parse standard pubDate string or fallback to now
                    try:
                        # Standard RSS date example: Sun, 24 May 2026 02:08:44 +0000
                        # We keep pubDate as string or parse it to standard isoformat if possible
                        published_at = pub_date
                    except Exception:
                        published_at = datetime.now(timezone.utc).isoformat()
                        
                    article = {
                        "title": title,
                        "url": url_str,
                        "source": source,
                        "published_at": published_at,
                        "summary": summary
                    }
                    
                    # 1. Publish to NATS
                    await self.publish("news.crypto", article)
                    
                    # 2. Write to Supabase
                    await self._write_to_supabase(article)
                    
                logger.info(f"[NEWS] RSS Feed {source} poll complete. Discovered {new_count} new articles.")
            except Exception as e:
                logger.error(f"[NEWS] Error polling RSS Feed {source}: {e}")

    async def _finnhub_loop(self):
        while self._running:
            try:
                await self.poll_finnhub()
            except Exception as e:
                logger.error(f"[NEWS] Error in Finnhub poll loop: {e}")
            await asyncio.sleep(5 * 60) # 5 minutes

    async def _rss_loop(self):
        while self._running:
            try:
                await self.poll_rss()
            except Exception as e:
                logger.error(f"[NEWS] Error in RSS poll loop: {e}")
            await asyncio.sleep(10 * 60) # 10 minutes

    async def run(self):
        self._running = True
        
        # Connect NATS
        await self.connect()
        
        # Load existing seen articles from DB for exact deduplication
        await self._init_seen_hashes()
        
        # Start loops in parallel tasks
        asyncio.create_task(self._finnhub_loop())
        asyncio.create_task(self._rss_loop())
        
        # Keep running
        while self._running:
            await asyncio.sleep(1)

    async def stop(self):
        self._running = False
        logger.info("[NEWS] Stopping News Collector...")
        await self.http_client.aclose()
        await self.disconnect()
        logger.info("[NEWS] News Collector stopped.")
