from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from strategy import StrategyRequest, start_strategy
from trader import get_top_20_coins
from fastapi.middleware.cors import CORSMiddleware
from log_stream import log_queue
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "OK"}

# 연결된 클라이언트 저장용
connected_clients = []

@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    print("✅ 클라이언트 연결됨")

    try:
        while True:
            log = await log_queue.get()
            await websocket.send_text(log)
    except Exception as e:
        print(f"❌ WebSocket 종료: {e}")
    finally:
        connected_clients.remove(websocket)

@app.post("/start-strategy")
async def trigger_strategy(req: StrategyRequest):  # <-- ✅ async 추가
    return await start_strategy(req)               # <-- ✅ await 추가

@app.get("/top-coins")
def top_coins():
    result = {"top_coins": get_top_20_coins()}
    print(result)
    return result