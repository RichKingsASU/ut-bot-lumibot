import os
import httpx
import logging
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv('/home/k2/ut-bot-lumibot/.env')
logger = logging.getLogger("SentimentVelocity")

class SentimentVelocity:
    def __init__(self):
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

    async def calculate(self, asset_class: str, lookback_hours: int = 24) -> dict:
        if not self.supabase_url or not self.supabase_key:
            return self._default_result()

        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
        }
        
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=lookback_hours)
        midpoint = now - timedelta(hours=lookback_hours / 2)

        try:
            url = f"{self.supabase_url}/rest/v1/news_articles"
            params = {
                "asset_class": f"eq.{asset_class}",
                "created_at": f"gt.{cutoff.isoformat()}",
                "select": "sentiment_score,created_at",
                "order": "created_at.asc"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers, params=params)
                
            if resp.status_code != 200:
                logger.error(f"Failed to fetch news_articles: {resp.status_code}")
                return self._default_result()
                
            rows = resp.json()
            if not rows:
                return self._default_result()

            first_half = []
            second_half = []
            
            for r in rows:
                created_at = datetime.fromisoformat(r['created_at'].replace('Z', '+00:00'))
                val = r.get('sentiment_score')
                score = float(val) if val is not None else 0.0
                if created_at < midpoint:
                    first_half.append(score)
                else:
                    second_half.append(score)

            first_sentiment = sum(first_half) / len(first_half) if first_half else 0.0
            second_sentiment = sum(second_half) / len(second_half) if second_half else (first_sentiment if first_half else 0.0)
            
            # If we don't have data in one of the halves, try to extrapolate or just be stable
            if not first_half and second_half:
                first_sentiment = second_sentiment
            elif first_half and not second_half:
                second_sentiment = first_sentiment
                
            velocity = second_sentiment - first_sentiment
            
            if velocity > 0.1:
                trend = 'IMPROVING'
                confidence_modifier = 10
            elif velocity < -0.1:
                trend = 'DETERIORATING'
                confidence_modifier = -10
            else:
                trend = 'STABLE'
                confidence_modifier = 0

            return {
                "current_sentiment": second_sentiment,
                "velocity": velocity,
                "trend": trend,
                "confidence_modifier": confidence_modifier
            }

        except Exception as e:
            logger.error(f"Error calculating sentiment velocity: {e}")
            return self._default_result()

    def _default_result(self) -> dict:
        return {
            "current_sentiment": 0.0,
            "velocity": 0.0,
            "trend": "STABLE",
            "confidence_modifier": 0
        }
