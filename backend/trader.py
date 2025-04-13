import os
import time
import pyupbit
from dotenv import load_dotenv
from datetime import datetime, timedelta
from models import StrategyRequest
from log_stream import send_log
import asyncio
from notify import send_telegram_message
load_dotenv()

access_key = os.getenv("UPBIT_ACCESS_KEY")
secret_key = os.getenv("UPBIT_SECRET_KEY")

# 전략 실행 함수
async def run_strategy_logic(req: StrategyRequest):
    upbit = pyupbit.Upbit(access_key, secret_key)

    await send_log("[전략 시작]")
    send_telegram_message("[전략 시작]")
    await send_log(f"손절: {req.loss_cut}%, 익절: {req.take_profit}%, 후보 수: {len(req.candidates)}")

    last_market = None  # 직전 매수 종목
    end_time = datetime.now() + timedelta(minutes=req.duration_minutes)
    while datetime.now() < end_time:
        # top = get_top_rising_coin(req.candidates, min_movement=-1.5)
        top = get_candidate_by_yangbong_strategy(req.candidates)
        if not top:
            await send_log("[패스] 조건을 만족하는 종목이 없음 (1.5% 이상 변동 없음)")
            await asyncio.sleep(60)
            continue

        # 현재가가 당일 고가/저가와 같다면 패스
        df_day = pyupbit.get_ohlcv(top['market'], interval='day', count=1)
        await send_log(f"[패스] {df_day}")
        if df_day is None or df_day.empty:
            await send_log(f"[스킵] {top['market']}의 일봉 데이터를 불러오지 못했거나 비어있습니다.")
            await asyncio.sleep(60)
            continue# 현재가가 당일 고가/저가와 같다면 패스
        
        high = df_day['high'].iloc[-1]
        low = df_day['low'].iloc[-1]
        now_price = top['price']

        # 현재가가 고가 또는 저가일 경우 패스
        if abs(now_price - high) < 1e-6 or abs(now_price - low) < 1e-6:
            label = "고가" if abs(now_price - high) < 1e-6 else "저가"
            await send_log(f"[패스] 현재가가 당일 {label}와 동일 → 매수 보류")
            await asyncio.sleep(60)
            continue

        # 고저 범위 기준으로 ±5% 내외 조건 추가
        range_gap = high - low
        lower_bound = low + range_gap * 0.05
        upper_bound = high - range_gap * 0.05

        if not (lower_bound <= now_price <= upper_bound):
            await send_log(f"[패스] 현재가가 고저 범위의 ±5% 바깥 영역 → 매수 보류 (현재가: {now_price:.2f}, 허용 범위: {lower_bound:.2f} ~ {upper_bound:.2f})")
            await asyncio.sleep(60)
            continue

        await send_log(f"\n[매수 후보] {top['market']} | 현재가: {top['price']}")

        krw_balance = get_balance("KRW", upbit)
        if krw_balance < 5100:
            await send_log(f"[❌ 매수 스킵] 잔고 부족: {krw_balance} KRW")
            continue

        budget = krw_balance * (req.invest_ratio / 100) * 0.98
        await send_log(f"[계산된 매수 금액] 보유 KRW: {krw_balance} → {budget}원 매수 시도")

        try:
            await send_log(f"👉 매수 요청 시도 중: {top['market']} {budget:.0f} KRW")
            now = datetime.now().strftime('%H:%M:%S')
            send_telegram_message(f"[{now}] 🟢 매수 시도: {top['market']}, 금액: {budget:.0f} KRW")
            order = upbit.buy_market_order(top['market'], budget)
            await send_log(f"[매수 요청] {top['market']} {budget:.0f} KRW | 주문 결과: {order}")
        except Exception as e:
            await send_log(f"[❌ 매수 실패] 에러: {e}")
            continue

        bought_at = top['price']
        entry_time = datetime.now()

        await monitor_position(top['market'], bought_at, req, entry_time, upbit)

    send_telegram_message("✅ 자동매매 전략이 종료되었습니다.")
    return {"status": "전략 종료 (지정 시간 소진)"}

def get_top_20_coins():
    tickers = pyupbit.get_tickers(fiat="KRW")
    volumes = []

    for ticker in tickers:
        try:
            df = pyupbit.get_ohlcv(ticker, interval="day", count=1)
            volume = df.iloc[-1]["volume"]
            close = df.iloc[-1]["close"]
            trade_amount = volume * close
            volumes.append((ticker, trade_amount))
        except:
            continue

    sorted_list = sorted(volumes, key=lambda x: x[1], reverse=True)
    top_20 = [item[0] for item in sorted_list[:20]]
    return top_20

def get_top_rising_coin(markets: list[str], min_movement: float = -3.5):
    result = []

    for market in markets:
        df = pyupbit.get_ohlcv(market, interval="minute3", count=2)
        if df is None or len(df) < 2:
            continue

        prev_close = df.iloc[-2]["close"]
        current_price = df.iloc[-1]["close"]
        change_rate = (current_price - prev_close) / prev_close * 100

        if change_rate <= min_movement:
            result.append({
                "market": market,
                "rate": change_rate,
                "price": current_price
            })

    result.sort(key=lambda x: x["rate"], reverse=True)
    return result[0] if result else None

def get_candidate_by_yangbong_strategy(markets: list[str]) -> dict | None:
    count = 0
    for market in markets:
        df = pyupbit.get_ohlcv(market, interval="minute3", count=10)
        time.sleep(1)
        if df is None or len(df) < 10:
            send_log("정보가 부족합니다.")
            continue
        count += 1
        recent = df.iloc[-4:-1]
        if not all(row["close"] > row["open"] for _, row in recent.iterrows()):
            continue

        max_change = max((row["close"] - row["open"]) / row["open"] * 100 for _, row in recent.iterrows())
        if max_change >= 2.5:
            send_log("변동폭이 큰 양봉이 있습니다.")
            continue

        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma10'] = df['close'].rolling(window=10).mean()

        ma5_now = df['ma5'].iloc[-1]
        ma10_now = df['ma10'].iloc[-1]
        ma5_prev = df['ma5'].iloc[-2]
        ma10_prev = df['ma10'].iloc[-2]

        if abs(ma5_prev - ma10_prev) < 1.5 and ma5_now > ma10_now and ma5_prev < ma10_prev:
            current_price = df.iloc[-1]["close"]
            return {"market": market, "price": current_price}
    send_log(f"{count}개수 검사 중 ...")
    return None

async def monitor_position(market: str, entry_price: float, req: StrategyRequest, entry_time: datetime, upbit):
    await send_log("[모니터링 시작] 익절/손절 조건 감시 중...")

    while True:
        current_price = pyupbit.get_current_price(market)
        if not current_price:
            await asyncio.sleep(1)
            continue

        change = (current_price - entry_price) / entry_price * 100
        elapsed = (datetime.now() - entry_time).total_seconds() / 60

        await send_log(f"현재가: {current_price}, 수익률: {change:.2f}%, 경과: {elapsed:.1f}분")

        if change >= req.take_profit:
            amount = get_balance(market, upbit)
            if amount:
                upbit.sell_market_order(market, amount)
                send_telegram_message(f"💰 익절 매도 완료: {market} / 수익률: {change:.2f}%")
                last_balance = get_balance("KRW", upbit)
                await send_log(f"[익절 매도] {market} 전량 매도 금액: {last_balance}")
                await asyncio.sleep(60)
            break
        elif change <= req.loss_cut:
            amount = get_balance(market, upbit)
            if amount:
                upbit.sell_market_order(market, amount)
                send_telegram_message(f"🔻 손절 매도 완료: {market} / 수익률: {change:.2f}%")
                last_balance = get_balance("KRW", upbit)
                await send_log(f"[손절 매도] {market} 전량 매도 금액: {last_balance}")
                await asyncio.sleep(60)
            break
        elif elapsed >= req.timeout_minutes:
            amount = get_balance(market, upbit)
            if amount:
                upbit.sell_market_order(market, amount)
                send_telegram_message(f"⏱️ 시간초과 매도 완료: {market} /  수익률: {change:.2f}%")
                last_balance = get_balance("KRW", upbit)
                await send_log(f"[시간초과 매도] {market} 전량 매도 금액: {last_balance}")
                await asyncio.sleep(60)
            break

        await asyncio.sleep(10)

def get_balance(market: str, upbit):
    symbol = market.split("-")[1] if market.startswith("KRW-") else market
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == symbol:
            return float(b['balance'])
    return 0
