"""
run_regime_detector.py — Standalone runner for the HMM Market Regime Detector
Runs the HMM regime classifier for both crypto and equities, prints a console report,
and sends a consolidated status message via Telegram.
"""

import asyncio
import logging
import os
import sys
import httpx
from dotenv import load_dotenv

# Set up logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout
)
logger = logging.getLogger("RunRegimeDetector")

# Load environment
load_dotenv()

_TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8641189809")

async def _send_telegram(text: str) -> None:
    """Send a Telegram message (best-effort, never raises)."""
    if not _TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set; skipping Telegram notification.")
        return
    url = f"https://api.telegram.org/bot{_TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": _TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("Telegram notification sent successfully.")
            else:
                logger.error(f"Telegram notification failed: {resp.status_code} — {resp.text}")
    except Exception as exc:
        logger.error(f"Telegram notification exception: {exc}")

async def main() -> None:
    logger.info("Starting standalone Market Regime Detector...")
    
    from agents.regime_detector import RegimeDetector
    
    # 1. Run equities detector
    logger.info("Running Equities HMM Regime Detector...")
    equities_detector = RegimeDetector("equities-regime-detector", asset_class="equities")
    equities_summary = await equities_detector.analyze()
    
    # 2. Run crypto detector
    logger.info("Running Crypto HMM Regime Detector...")
    crypto_detector = RegimeDetector("crypto-regime-detector", asset_class="crypto")
    crypto_summary = await crypto_detector.analyze()
    
    # Compose console report
    print("\n" + "="*50)
    print("🤖 HMM MARKET REGIME DETECTION REPORT")
    print("="*50)
    print(f"Timestamp: {equities_summary.get('detected_at')}\n")
    
    print("📈 EQUITIES UNIVERSE")
    print(f"Overall Regime: {equities_summary.get('overall_regime')}")
    print(f"Recommendation: {equities_summary.get('strategy_recommendation')}")
    print("Symbol Details:")
    for sym, details in equities_summary.get("symbol_regimes", {}).items():
        print(f"  • {sym:5}: {details.get('regime'):8} (prob: {details.get('probability'):.4f})")
    print(f"Distribution  : {dict(equities_summary.get('regime_distribution', {}))}\n")
    
    print("📊 CRYPTO UNIVERSE")
    print(f"Overall Regime: {crypto_summary.get('overall_regime')}")
    print(f"Recommendation: {crypto_summary.get('strategy_recommendation')}")
    print("Symbol Details:")
    for sym, details in crypto_summary.get("symbol_regimes", {}).items():
        print(f"  • {sym:7}: {details.get('regime'):8} (prob: {details.get('probability'):.4f})")
    print(f"Distribution  : {dict(crypto_summary.get('regime_distribution', {}))}")
    print("="*50 + "\n")
    
    # Compose Telegram message
    tg_text = (
        "🎯 <b>HMM Market Regime Detection Report</b>\n\n"
        "📈 <b>EQUITIES</b>\n"
        f"Regime: <b>{equities_summary.get('overall_regime')}</b>\n"
        f"Recommendation: <i>{equities_summary.get('strategy_recommendation')}</i>\n"
        f"Distribution: {dict(equities_summary.get('regime_distribution', {}))}\n\n"
        "📊 <b>CRYPTO</b>\n"
        f"Regime: <b>{crypto_summary.get('overall_regime')}</b>\n"
        f"Recommendation: <i>{crypto_summary.get('strategy_recommendation')}</i>\n"
        f"Distribution: {dict(crypto_summary.get('regime_distribution', {}))}"
    )
    
    logger.info("Sending Telegram consolidated report...")
    await _send_telegram(tg_text)
    logger.info("Standalone Regime Detector run complete.")

if __name__ == "__main__":
    asyncio.run(main())
