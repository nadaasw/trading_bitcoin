import os
import time
import pyupbit
import asyncio
from dotenv import load_dotenv
from datetime import datetime, timedelta
import requests

load_dotenv()

access_key = os.getenv("UPBIT_ACCESS_KEY")
secret_key = os.getenv("UPBIT_SECRET_KEY")
telegram_token = os.getenv("TELEGRAM_TOKEN")
telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram(msg: str):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    data = {"chat_id": telegram_chat_id, "text": msg}
    try:
        requests.post(url, data=data)
    except:
        pass


def get_candidate_by_yangbong_strategy(markets):
    for market in markets:
        df = pyupbit.get_ohlcv(market, interval="minute3", count=10)
        time.sleep(1)
        if df is None or len(df) < 10:
            continue

        recent = df.iloc[-2:]
        if not all(row["close"] > row["open"] for _, row in recent.iterrows()):
            continue

        max_change = max((row["close"] - row["open"]) / row["open"] * 100 for _, row in recent.iterrows())
        if max_change >= 2.5:
            continue

        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma10'] = df['close'].rolling(window=10).mean()

        ma5_now = df['ma5'].iloc[-1]
        ma10_now = df['ma10'].iloc[-1]
        ma5_prev = df['ma5'].iloc[-2]
        ma10_prev = df['ma10'].iloc[-2]

        if abs(ma5_prev - ma10_prev) < 1.5 and ma5_now > ma10_now and ma5_prev < ma10_prev:
            price = df.iloc[-1]["close"]
            return {"market": market, "price": price}
    return None

def get_top_1min_movement(markets: list[str], min_movement: float = 1.0) -> dict | None:
    result = []

    for market in markets:
        df = pyupbit.get_ohlcv(market, interval="minute1", count=2)
        if df is None or len(df) < 2:
            continue

        prev = df.iloc[-2]["close"]
        curr = df.iloc[-1]["close"]
        rate = (curr - prev) / prev * 100
        if abs(rate) >= min_movement:
            result.append({
                "market": market,
                "rate": rate,
                "price": curr
            })

    result.sort(key=lambda x: abs(x["rate"]), reverse=True)
    return result[0] if result else None

def get_balance(market: str, upbit):
    if market == "KRW":
        for b in upbit.get_balances():
            if b['currency'] == "KRW":
                return float(b['balance'])
        return 0

    symbol = market.split("-")[1] if "-" in market else market
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == symbol:
            return float(b['balance'])
    return 0


async def monitor_position(upbit, market, entry_price, take_profit, loss_cut, timeout_min):
    start = datetime.now()

    while True:
        now = datetime.now()
        elapsed = (now - start).total_seconds() / 60
        price = pyupbit.get_current_price(market)
        if not price:
            await asyncio.sleep(3)
            continue

        change = (price - entry_price) / entry_price * 100
        send_telegram(f"{market} 현재 수익률: {change:.2f}% / 경과: {elapsed:.1f}분")

        if change >= take_profit or change <= loss_cut or elapsed >= timeout_min:
            amount = get_balance(market, upbit)
            if amount > 0:
                upbit.sell_market_order(market, amount)
                reason = "익절" if change >= take_profit else "손절" if change <= loss_cut else "시간초과"
                send_telegram(f"🚨 {reason} 매도: {market} / 수익률: {change:.2f}%")
            break

        await asyncio.sleep(30)


async def main():
    upbit = pyupbit.Upbit(access_key, secret_key)

    send_telegram("🔔 자동매매 봇 시작됨")

    duration_minutes = 20
    timeout_minutes = 3
    invest_ratio = 100
    take_profit = 1.5
    loss_cut = -0.9
    candidates = pyupbit.get_tickers(fiat="KRW")

    end_time = datetime.now() + timedelta(minutes=duration_minutes)

    while datetime.now() < end_time:
        #candidate = get_candidate_by_yangbong_strategy(candidates)
        candidate = get_top_1min_movement(candidates, min_movement=1.5)
        if not candidate:
            send_telegram("조건 만족 종목 없음. 60초 대기")
            await asyncio.sleep(60)
            continue

        krw = get_balance("KRW", upbit)
        if krw < 5100:
            send_telegram("💸 매수 실패: 잔고 부족")
            await asyncio.sleep(60)
            continue

        budget = krw * (invest_ratio / 100) * 0.98
        market = candidate["market"]
        price = candidate["price"]

        try:
            order = upbit.buy_market_order(market, budget)
            send_telegram(f"🟢 매수 시도: {market} / 금액: {budget:.0f}")
        except Exception as e:
            send_telegram(f"❌ 매수 실패: {e}")
            await asyncio.sleep(60)
            continue

        await monitor_position(upbit, market, price, take_profit, loss_cut, timeout_minutes)

    send_telegram("✅ 자동매매 봇 종료됨")


if __name__ == "__main__":
    asyncio.run(main())