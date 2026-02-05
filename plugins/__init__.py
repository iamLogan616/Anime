# __init__.py in plugins folder
from aiohttp import web
from .route import routes
from . import (
    start,
    channel_post,
    link_generator,
    # Add this line for flink command
    flink_command
)

async def web_server():
    web_app = web.Application(client_max_size=30000000)
    web_app.add_routes(routes)
    return web_app

# Export all handlers
__all__ = [
    'start',
    'channel_post', 
    'link_generator',
    'flink_command'
]
