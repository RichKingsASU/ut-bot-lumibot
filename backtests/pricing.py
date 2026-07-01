"""
Black-Scholes fallback pricer.

Used ONLY where real historical option data is unavailable (per task: Alpaca
options history starts ~Feb 2024 and, in restricted environments, may be
unreachable entirely). Reconstructs an option premium from the underlying,
time-to-expiry and an IV estimate (RVX-proxy). Every trade priced this way is
labeled ``priced_via="bs"`` in the output.

Greeks note: real Alpaca data captures theta/IV drift automatically; the BS
path captures theta through the shrinking time-to-expiry passed on each bar and
IV through :func:`iv_estimate`.
"""

from __future__ import annotations

import math

try:
    from py_vollib.black_scholes import black_scholes as _bs
    _HAVE_VOLLIB = True
except Exception:  # pragma: no cover
    _HAVE_VOLLIB = False


def _bs_fallback(flag: str, S: float, K: float, t: float, r: float, sigma: float) -> float:
    """Closed-form Black-Scholes if py_vollib is unavailable."""
    if t <= 0 or sigma <= 0:
        intrinsic = (S - K) if flag == "c" else (K - S)
        return max(0.0, intrinsic)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    Nd1 = 0.5 * (1 + math.erf(d1 / math.sqrt(2)))
    Nd2 = 0.5 * (1 + math.erf(d2 / math.sqrt(2)))
    if flag == "c":
        return S * Nd1 - K * math.exp(-r * t) * Nd2
    return K * math.exp(-r * t) * (1 - Nd2) - S * (1 - Nd1)


def bs_price(S: float, K: float, t_years: float, iv: float, r: float,
             option_type: str) -> float:
    """Black-Scholes theoretical price. option_type: 'call' | 'put'."""
    flag = "c" if option_type == "call" else "p"
    t = max(t_years, 0.0)
    if t <= 0 or iv <= 0:
        intrinsic = (S - K) if flag == "c" else (K - S)
        return max(0.0, intrinsic)
    if _HAVE_VOLLIB:
        try:
            return max(0.0, float(_bs(flag, S, K, t, r, iv)))
        except Exception:
            pass
    return max(0.0, _bs_fallback(flag, S, K, t, r, iv))


def iv_estimate(base_iv: float, S: float, K: float, t_years: float) -> float:
    """RVX-proxy IV with a light moneyness skew and short-dated term bump.

    A crude but honest stand-in for a real IV surface: near-dated options carry
    a small vol premium and OTM strikes a small skew. Documented as a proxy in
    the Assumptions block.
    """
    moneyness = abs(math.log(max(S, 1e-9) / max(K, 1e-9)))
    skew = 1.0 + 1.5 * moneyness              # steeper wings
    term = 1.0 + max(0.0, (0.05 - t_years)) * 2.0  # bump under ~2 weeks
    return max(0.05, base_iv * skew * term)
