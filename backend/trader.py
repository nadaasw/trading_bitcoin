import os
import time
import pyupbit
from dotenv import load_dotenv
from datetime import datetime, timedelta
from models import StrategyRequest
from log_stream import send_log
import asyncio

load_dotenv()

access_key = os.getenv("UPBIT_ACCESS_KEY")
secret_key = os.getenv("UPBIT_SECRET_KEY")
upbit = pyupbit.Upbit(access_key, secret_key)

# 전략 실행 함수
async def run_strategy_logic(req: StrategyRequest):
    await send_log("[전략 시작]")
    await send_log(f"손절: {req.loss_cut}%, 익절: {req.take_profit}%, 후보 수: {len(req.candidates)}")

    end_time = datetime.now() + timedelta(minutes=req.duration_minutes)
    while datetime.now() < end_time:
        # 후보 중 가장 급등한 코인 선택 (1.5% 이상만 필터링)
        top = get_top_rising_coin(req.candidates, min_movement=1.5)
        if not top:
            await send_log("[패스] 조건을 만족하는 종목이 없음 (1.5% 이상 변동 없음)")
            await asyncio.sleep(60)  # 1분 후 재시도
            continue

        await send_log(f"\n[매수 후보] {top['market']} | 변동률: {top['rate']:.2f}% | 현재가: {top['price']}")

        # 자산의 일부 비율로 매수 금액 계산
        krw_balance = get_balance("KRW")
        budget = krw_balance * (req.invest_ratio / 100)
        await send_log(f"[계산된 매수 금액] 보유 KRW: {krw_balance} → {budget}원 매수 시도")

        # 실매수 실행
        order = upbit.buy_market_order(top['market'], budget)
        await send_log(f"[매수 요청] {top['market']} {budget:.0f} KRW | 주문 결과: {order}")

        bought_at = top['price']
        entry_time = datetime.now()

        # 매도 감시
        await monitor_position(top['market'], bought_at, req, entry_time)

    return {"status": "전략 종료 (지정 시간 소진)"}

# 거래대금 기준 상위 20개 코인 조회 API
def get_top_20_coins():
    tickers = pyupbit.get_tickers(fiat="KRW")
    volumes = []

    for ticker in tickers:
        try:
            df = pyupbit.get_ohlcv(ticker, interval="day", count=1)
            volume = df.iloc[-1]["volume"]
            close = df.iloc[-1]["close"]
            trade_amount = volume * close  # 거래대금
            volumes.append((ticker, trade_amount))
        except:
            continue

    sorted_list = sorted(volumes, key=lambda x: x[1], reverse=True)
    top_20 = [item[0] for item in sorted_list[:20]]
    return top_20

# 후보 중 가장 급등률 높은 코인 선택 (최소 변동률 필터)
def get_top_rising_coin(markets: list[str], min_movement: float = 1.5):
    result = []

    for market in markets:
        df = pyupbit.get_ohlcv(market, interval="minute5", count=2)
        if df is None or len(df) < 2:
            continue

        prev_close = df.iloc[-2]["close"]
        current_price = df.iloc[-1]["close"]
        change_rate = (current_price - prev_close) / prev_close * 100

        # 최소 변동률 필터 적용
        if abs(change_rate) >= min_movement:
            result.append({
                "market": market,
                "rate": change_rate,
                "price": current_price
            })

    result.sort(key=lambda x: x["rate"], reverse=True)
    return result[0] if result else None

# 익절/손절 감시 및 실매도
async def monitor_position(market: str, entry_price: float, req: StrategyRequest, entry_time: datetime):
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
            amount = get_balance(market)
            if amount:
                upbit.sell_market_order(market, amount)
                await send_log(f"[익절 매도] {market} 전량 매도")
            break
        elif change <= req.loss_cut:
            amount = get_balance(market)
            if amount:
                upbit.sell_market_order(market, amount)
                await send_log(f"[손절 매도] {market} 전량 매도")
            break
        elif elapsed >= req.timeout_minutes:
            amount = get_balance(market)
            if amount:
                upbit.sell_market_order(market, amount)
                await send_log(f"[시간초과 매도] {market} 전량 매도")
            break

        await asyncio.sleep(5)  # 5초 간격으로 확인

# 보유 수량 조회
def get_balance(market: str):
    symbol = market.split("-")[1] if market.startswith("KRW-") else market
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == symbol:
            return float(b['balance'])
    return 0
