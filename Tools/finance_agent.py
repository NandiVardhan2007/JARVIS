"""Finance Agent — stock and crypto tracking.

Uses yfinance for stocks and CoinGecko API for cryptocurrency prices.
Tracks a mock portfolio in SQLite.
"""

import logging
import os
import sqlite3
from typing import Optional
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "jarvis_memory", "finance.db"
)


def _ensure_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                quantity REAL NOT NULL,
                UNIQUE(symbol, asset_type)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS price_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                target_price REAL NOT NULL,
                direction TEXT NOT NULL
            )
        """)
        conn.commit()


_ensure_db()


@function_tool
async def get_stock_price(symbol: str) -> str:
    """
    Gets the current price and daily change for a stock ticker.

    Args:
        symbol: The stock ticker symbol (e.g., 'AAPL', 'MSFT').
    """
    logger.info(f"Getting stock price for: {symbol}")
    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        info = ticker.info

        # Handle cases where info is mostly empty or missing current price
        if not info or "currentPrice" not in info:
            # Try fetching recent history
            hist = ticker.history(period="1d")
            if hist.empty:
                return f"Could not retrieve price for {symbol}."
            price = hist["Close"].iloc[-1]
            return f"{symbol.upper()} is currently trading at ${price:.2f}"

        price = info.get("currentPrice")
        prev_close = info.get("previousClose")
        name = info.get("shortName", symbol)

        if price and prev_close:
            change = price - prev_close
            change_pct = (change / prev_close) * 100
            sign = "+" if change > 0 else ""
            return f"{name} ({symbol.upper()}): ${price:.2f} ({sign}{change:.2f}, {sign}{change_pct:.2f}%)"

        return (
            f"{name} ({symbol.upper()}): ${price:.2f}"
            if price
            else f"Price not available for {symbol}"
        )

    except ImportError:
        return "yfinance package is not installed."
    except Exception as e:
        logger.error(f"get_stock_price error: {e}")
        return f"Failed to get stock price: {e}"


@function_tool
async def get_crypto_price(coin_id: str) -> str:
    """
    Gets the current price and 24h change for a cryptocurrency.

    Args:
        coin_id: The CoinGecko ID of the coin (e.g., 'bitcoin', 'ethereum').
    """
    logger.info(f"Getting crypto price for: {coin_id}")
    try:
        import aiohttp

        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id.lower()}&vs_currencies=usd&include_24hr_change=true"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                resp.raise_for_status()
                data = await resp.json()

        if coin_id.lower() not in data:
            return f"Coin '{coin_id}' not found on CoinGecko. Make sure to use the ID, not the symbol (e.g. 'bitcoin' not 'btc')."

        price = data[coin_id.lower()]["usd"]
        change = data[coin_id.lower()].get("usd_24h_change", 0)

        sign = "+" if change > 0 else ""
        return f"{coin_id.title()}: ${price:,.2f} ({sign}{change:.2f}% 24h)"

    except Exception as e:
        logger.error(f"get_crypto_price error: {e}")
        return f"Failed to get crypto price: {e}"


@function_tool
async def portfolio_summary() -> str:
    """
    Displays the current portfolio holdings.
    """
    logger.info("Fetching portfolio summary")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                "SELECT symbol, asset_type, quantity FROM portfolio"
            ).fetchall()

        if not rows:
            return "Your portfolio is currently empty."

        lines = ["Portfolio Holdings:"]
        for sym, atype, qty in rows:
            lines.append(f"• {qty}x {sym.upper()} ({atype})")

        lines.append(
            "\nNote: Use get_stock_price or get_crypto_price to check current values."
        )
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"portfolio_summary error: {e}")
        return f"Failed to fetch portfolio: {e}"


@function_tool
async def add_to_portfolio(
    symbol: str, quantity: float, asset_type: str = "stock"
) -> str:
    """
    Adds a holding to the tracking portfolio.

    Args:
        symbol: The ticker or coin ID.
        quantity: The amount held.
        asset_type: 'stock' or 'crypto' (default 'stock').
    """
    logger.info(f"Adding to portfolio: {quantity} of {symbol} ({asset_type})")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """INSERT INTO portfolio (symbol, asset_type, quantity) 
                   VALUES (?, ?, ?)
                   ON CONFLICT(symbol, asset_type) 
                   DO UPDATE SET quantity = quantity + excluded.quantity""",
                (symbol.lower(), asset_type.lower(), quantity),
            )
            conn.commit()
        return f"Added {quantity} of {symbol.upper()} to your portfolio."
    except Exception as e:
        logger.error(f"add_to_portfolio error: {e}")
        return f"Failed to add to portfolio: {e}"


__all__ = [
    "get_stock_price",
    "get_crypto_price",
    "portfolio_summary",
    "add_to_portfolio",
]
