#!/usr/bin/env python3
"""
End-to-end dry-run test for the options trade cycle.

Tests:
  1. Mock a LONG signal at SPY ~580.00
  2. Select ATM call contract (0DTE)
  3. Buy-to-open in paper mode
  4. Wait 5 seconds
  5. Sell-to-close
  6. Print trade summary with P&L

Usage:
  python scripts/test_trade_cycle.py

Requires ALPACA_API_KEY, ALPACA_API_SECRET, ALPACA_BASE_URL in .env or env vars.
"""

import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from strategies.options_executor import (
    get_underlying_price,
    select_atm_contract,
    get_option_quote,
    buy_to_open,
    sell_to_close,
    has_open_position,
    get_open_position,
    open_position,
)


def main():
    print("=" * 60)
    print("  OPTIONS TRADE CYCLE — END-TO-END DRY RUN")
    print("=" * 60)

    # Verify credentials are set (never print actual keys)
    api_key = os.getenv("ALPACA_API_KEY", "")
    base_url = os.getenv("ALPACA_BASE_URL", "")
    print(f"\nBase URL: {base_url}")
    print(f"API Key set: {'YES' if api_key else 'NO'}")
    if not api_key:
        print("ERROR: ALPACA_API_KEY not set. Create a .env file.")
        sys.exit(1)

    underlying = "SPY"

    # ── Step 1: Get underlying price ─────────────────────────────────────
    print(f"\n[1] Fetching {underlying} price...")
    try:
        price = get_underlying_price(underlying)
        print(f"    {underlying} = ${price:.2f}")
    except Exception as e:
        print(f"    ERROR fetching price: {e}")
        print("    Using mock price $580.00 for contract selection test")
        price = 580.00

    # ── Step 2: Select ATM contract ──────────────────────────────────────
    print(f"\n[2] Selecting ATM CALL contract (0DTE)...")
    try:
        contract = select_atm_contract(underlying, price, "call")
        if contract:
            print(f"    Symbol:     {contract.get('symbol')}")
            print(f"    Strike:     ${float(contract.get('strike_price', 0)):.2f}")
            print(f"    Expiration: {contract.get('expiration_date')}")
            print(f"    Type:       {contract.get('type', 'call')}")
        else:
            print("    No contract found — market may be closed or no 0DTE available")
            print("    Aborting trade cycle test.")
            sys.exit(0)
    except Exception as e:
        print(f"    ERROR selecting contract: {e}")
        sys.exit(1)

    # ── Step 3: Fetch option quote ───────────────────────────────────────
    contract_symbol = contract.get("symbol", "")
    print(f"\n[3] Fetching quote for {contract_symbol}...")
    try:
        quote = get_option_quote(contract_symbol)
        print(f"    Bid:  ${quote['bid']:.2f}")
        print(f"    Ask:  ${quote['ask']:.2f}")
        print(f"    Mid:  ${quote['mid']:.2f}")
    except Exception as e:
        print(f"    ERROR fetching quote: {e}")
        sys.exit(1)

    # ── Step 4: Buy-to-open ──────────────────────────────────────────────
    print(f"\n[4] Executing BUY-TO-OPEN (LONG, 1 contract)...")
    try:
        entry_order = buy_to_open(
            underlying=underlying,
            direction="LONG",
            qty=1,
            underlying_price=price,
            current_rsi=55.0,
        )
        if entry_order:
            print(f"    Order ID:    {entry_order.get('id', 'N/A')}")
            print(f"    Status:      {entry_order.get('status', 'N/A')}")
            print(f"    Fill Price:  ${float(entry_order.get('filled_avg_price', 0)):.2f}")
        else:
            print("    Entry order failed or was rejected.")
            sys.exit(1)
    except Exception as e:
        print(f"    ERROR during buy_to_open: {e}")
        sys.exit(1)

    # ── Verify position state ────────────────────────────────────────────
    print(f"\n    Position open: {has_open_position()}")
    if has_open_position():
        pos = get_open_position()
        print(f"    Contract:    {pos.get('contract_symbol')}")
        print(f"    Direction:   {pos.get('direction')}")
        print(f"    Entry Price: ${pos.get('fill_price', 0):.2f}")
        print(f"    Qty:         {pos.get('qty')}")

    # ── Step 5: Wait 5 seconds ───────────────────────────────────────────
    print("\n[5] Waiting 5 seconds before exit...")
    time.sleep(5)

    # ── Step 6: Sell-to-close ────────────────────────────────────────────
    print(f"\n[6] Executing SELL-TO-CLOSE...")
    try:
        exit_order = sell_to_close(exit_reason="test_cycle")
        if exit_order:
            status = exit_order.get("status", "N/A")
            print(f"    Order ID:    {exit_order.get('id', 'N/A')}")
            print(f"    Status:      {status}")
            if status == "expired_worthless":
                print(f"    P&L:         ${exit_order.get('pnl', 0):.2f}")
            else:
                exit_price = float(exit_order.get("filled_avg_price", 0))
                print(f"    Exit Price:  ${exit_price:.2f}")
        else:
            print("    Exit order failed.")
    except Exception as e:
        print(f"    ERROR during sell_to_close: {e}")

    # ── Step 7: Trade Summary ────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  TRADE SUMMARY")
    print("=" * 60)
    if entry_order and exit_order:
        entry_fill = float(entry_order.get("filled_avg_price", 0))
        if exit_order.get("status") == "expired_worthless":
            exit_fill = 0.0
            pnl = exit_order.get("pnl", 0)
        else:
            exit_fill = float(exit_order.get("filled_avg_price", 0))
            pnl = (exit_fill - entry_fill) * 100  # 1 contract = 100 shares
        print(f"  Contract:    {contract_symbol}")
        print(f"  Direction:   LONG CALL")
        print(f"  Entry:       ${entry_fill:.2f}")
        print(f"  Exit:        ${exit_fill:.2f}")
        print(f"  P&L:         ${pnl:.2f}")
    else:
        print("  Trade cycle incomplete — see errors above.")

    print(f"\n  Position cleared: {not has_open_position()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
