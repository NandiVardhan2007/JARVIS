import time
import asyncio
import os
import sys
import types
from unittest.mock import MagicMock

os.environ['DISPLAY'] = ':0'

# Need to patch vlc before importing
module = types.ModuleType("vlc")
module.Instance = MagicMock()
sys.modules["vlc"] = module

import Tools.system_control

async def run_blocking():
    start = time.time()

    task = asyncio.create_task(Tools.system_control.use_smart_clipboard("test", "paste_item", 5))

    # In a non-blocking asyncio setup, this loop should execute many times during the sleep
    iterations = 0
    while not task.done():
        await asyncio.sleep(0.01)
        iterations += 1

    print(f"Iterations of the event loop that ran concurrently: {iterations}")

    await task
    return time.time() - start

async def run_test():
    import sys
    sys.modules['pyautogui'] = MagicMock()

    duration = await run_blocking()
    print(f"Total Duration: {duration:.4f} seconds")

asyncio.run(run_test())
