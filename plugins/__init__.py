#(©)Codexbotz
#@iryme

from aiohttp import web

async def web_server():
    web_app = web.Application(client_max_size=30000000)
    
    # Import routes inside function to avoid circular imports
    from .route import routes
    web_app.add_routes(routes)
    
    return web_app
