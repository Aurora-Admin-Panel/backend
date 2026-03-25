import asyncio
import threading
import random
import time
from aiohttp import ClientSession

# Coroutine to simulate async work
async def fetch_url(session, url):
    async with session.get(url) as response:
        text = await response.text()
        print(f"Fetched content from {url}")
        return text

# Function to be executed in worker threads
def worker_thread(task_id):
    async def worker_async_loop():
        async with ClientSession() as session:
            url = f'https://jsonplaceholder.typicode.com/todos/{random.randint(1, 200)}'
            await fetch_url(session, url)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(worker_async_loop())
    loop.close()
    print(f"Worker {task_id} completed")

# Producer async loop
async def producer_async_loop():
    workers = []
    for _ in range(50):
        task_id = random.randint(1, 100)
        print(f"Producer: Creating worker thread for task {task_id}")
        worker = threading.Thread(target=worker_thread, args=(task_id,))
        worker.start()
        workers.append(worker)
    for worker in workers:
        worker.join()

if __name__ == "__main__":
    try:
        asyncio.run(producer_async_loop())
    except KeyboardInterrupt:
        print("Terminating the program")
