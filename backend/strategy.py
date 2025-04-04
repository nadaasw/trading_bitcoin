from models import StrategyRequest
from trader import run_strategy_logic

def start_strategy(req: StrategyRequest):
    result = run_strategy_logic(req)
    return {"message": "전략 시작됨", "detail": result}