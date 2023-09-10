import asyncio
import json
import threading
from uuid import uuid4
from functools import wraps
from typing import Callable, Dict

from fastapi import WebSocket

import tasks
from app.utils.thread import run_in_thread


class WebSocketMessageHandler:
    def __init__(self):
        self.message_handlers: Dict[str, Callable] = {}

    def message_handler(self, message_type: str):
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)

            self.message_handlers[message_type] = wrapper
            return wrapper

        return decorator

    async def handle_message(self, websocket: WebSocket, data: Dict):
        try:
            print(f"Received message: {data}")

            msg_id = data.pop("id", None)
            if not msg_id:
                msg_id = str(uuid4())
            message_type = data.pop("type", None)
            if not message_type:
                raise ValueError("Message type not found")

            handler = self.message_handlers.get(message_type)
            if not handler:
                raise ValueError(
                    f"No handler found for message type '{message_type}'"
                )

            return await handler(websocket, msg_id, data)
        except Exception as e:
            print(f"Error handling message: {e}")
            await websocket.send_json(
                {"type": "error", "id": msg_id, "message": str(e)}
            )

    async def run_forever(self, websocket: WebSocket):
        workers = []
        while True:
            try:
                if websocket.client_state == 2:
                    await websocket.close()
                    break
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=1
                )
                data = json.loads(data)
                if data.get("type") == "complete":
                    break
                worker = threading.Thread(
                    target=run_in_thread,
                    args=(
                        self.handle_message,
                        websocket,
                        data,
                    ),
                )
                workers.append(handler)
                worker.start()
            except asyncio.TimeoutError:
                await asyncio.sleep(0.1)
        for worker in workers:
            worker.join()


handler = WebSocketMessageHandler()


@handler.message_handler("greet")
async def greet(websocket: WebSocket, msg_id: str, data: Dict):
    await websocket.send_json(
        {
            "type": "response",
            "id": msg_id,
            "message": f"Hello, {data['name']}!",
        }
    )


@handler.message_handler("tasks")
async def run_tasks(websocket: WebSocket, msg_id: str, data: Dict):
    task_name = data.pop("name")

    task_func = getattr(tasks, task_name, None)
    if not task_func:
        raise ValueError(f"Task '{task_name}' not found")

    result = task_func(**data)
    if websocket.client_state != 2:
        await websocket.send_json(
            {
                "type": "response",
                "id": msg_id,
                "message": result(blocking=True),
            }
        )
    else:
        print("Client disconnected, not sending response")
