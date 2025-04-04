from fastapi import FastAPI
from strategy import StrategyRequest, start_strategy

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "OK"}

@app.post("/start-strategy")
def trigger_strategy(req: StrategyRequest):
    return start_strategy(req)