#(©)Codexbotz
#@iryme

from aiohttp import web
from .route import routes

# No need to import specific modules if they're loaded elsewhere
# The Bot.on_message decorators will register automatically

async def web_server():
    web_app = web.Application(client_max_size=30000000)
    web_app.add_routes(routes)
    return web_app
