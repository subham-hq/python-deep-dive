import asyncio

from aiohttp import web


async def handler(request: web.Request) -> web.Response:
    await asyncio.sleep(0.05)  # 50 ms delay
    return web.Response(text="OK")


app = web.Application()
app.router.add_get("/", handler)

if __name__ == "__main__":
    web.run_app(app, host="127.0.0.1", port=8000)
