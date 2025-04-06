from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class StrategyRequest(BaseModel):
    loss_cut: float               # 손절 기준 (%)
    take_profit: float            # 익절 기준 (%)
    timeout_minutes: int          # 포지션 감시 최대 시간 (분)
    duration_minutes: int         # 전체 전략 실행 시간 (분)
    invest_ratio: float           # 예: 30.0 → 30%
    candidates: list[str]         # 매수 후보 종목 리스트