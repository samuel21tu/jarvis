import json
import urllib.request
import asyncio
import websockets

async def test():
    req = urllib.request.Request("http://localhost:9222/json")
    with urllib.request.urlopen(req) as response:
        pages = json.loads(response.read())
        
    page = next(p for p in pages if p['url'] == "http://192.168.1.92:8080/")
    ws_url = page['webSocketDebuggerUrl']
    
    async with websockets.connect(ws_url) as ws:
        # Enable console
        await ws.send(json.dumps({"id": 1, "method": "Console.enable"}))
        await ws.send(json.dumps({"id": 2, "method": "Runtime.enable"}))
        # Wait for messages for a bit
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                print(msg)
        except asyncio.TimeoutError:
            pass

asyncio.run(test())
