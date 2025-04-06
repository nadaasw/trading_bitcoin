from models import StrategyRequest
from trader import run_strategy_logic

async def start_strategy(req: StrategyRequest):
    result = await run_strategy_logic(req)
    return {"message": "전략 시작됨", "detail": result}