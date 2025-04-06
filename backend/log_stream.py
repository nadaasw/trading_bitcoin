# log_stream.py

import asyncio

log_queue = asyncio.Queue()

async def send_log(message: str):
    await log_queue.put(message)