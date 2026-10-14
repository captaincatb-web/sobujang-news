from datetime import timedelta

import yfinance as yf


def get_quote(ticker: str) -> dict | None:
    try:
        hist = yf.Ticker(ticker).history(period="1mo")
    except Exception as e:
        print(f"[yfinance] '{ticker}' 조회 실패: {e}")
        return None

    if hist.empty:
        return None

    last_close = float(hist["Close"].iloc[-1])
    prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else last_close
    change_pct = (last_close - prev_close) / prev_close * 100 if prev_close else 0.0

    # 1주 전(마지막 거래일 기준 7일 전 이전의 마지막 종가) 대비 등락
    week_ago = hist[hist.index <= hist.index[-1] - timedelta(days=7)]
    week_close = float(week_ago["Close"].iloc[-1]) if not week_ago.empty else None
    week_change_pct = (last_close - week_close) / week_close * 100 if week_close else None
    return {
        "price": last_close,
        "prev_close": prev_close,
        "change_pct": change_pct,
        "week_close": week_close,
        "week_change_pct": week_change_pct,
    }


def format_price(ticker: str, price: float) -> str:
    if ticker.endswith((".KS", ".KQ")):
        return f"{price:,.0f}원"
    return f"${price:,.2f}"
