import pyupbit
import time
from datetime import datetime, timedelta
from models import StrategyRequest

# 전략 실행 함수
def run_strategy_logic(req: StrategyRequest):
    print("[전략 시작]")
    print(f"손절: {req.loss_cut}%, 익절: {req.take_profit}%, 후보 수: {len(req.candidates)}")

    end_time = datetime.now() + timedelta(minutes=req.duration_minutes)
    while datetime.now() < end_time:
        # 후보 중 가장 급등한 코인 선택 (1.5% 이상만 필터링)
        top = get_top_rising_coin(req.candidates, min_movement=1.5)
        if not top:
            print("[패스] 조건을 만족하는 종목이 없음 (1.5% 이상 변동 없음)")
            time.sleep(60)  # 1분 후 재시도
            continue

        print(f"\n[매수 후보] {top['market']} | 변동률: {top['rate']:.2f}% | 현재가: {top['price']}")

        # TODO: 실제 매수 요청 → 모의 매수로 대체
        bought_at = top['price']
        entry_time = datetime.now()

        # 매도 감시
        monitor_position(top['market'], bought_at, req, entry_time)

    return {"status": "전략 종료 (지정 시간 소진)"}

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

# 익절/손절 감시

def monitor_position(market: str, entry_price: float, req: StrategyRequest, entry_time: datetime):
    print("[모니터링 시작] 익절/손절 조건 감시 중...")

    while True:
        current_price = pyupbit.get_current_price(market)
        if not current_price:
            time.sleep(1)
            continue

        change = (current_price - entry_price) / entry_price * 100
        elapsed = (datetime.now() - entry_time).total_seconds() / 60

        print(f"현재가: {current_price}, 수익률: {change:.2f}%, 경과: {elapsed:.1f}분")

        if change >= req.take_profit:
            print(f"[익절] {change:.2f}% 수익으로 매도")
            break
        elif change <= req.loss_cut:
            print(f"[손절] {change:.2f}% 손실로 매도")
            break
        elif elapsed >= req.timeout_minutes:
            print(f"[시간초과] {req.timeout_minutes}분 안에 체결 조건 미충족 → 매도")
            break

        time.sleep(5)  # 5초 간격으로 확인
