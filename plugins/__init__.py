#(©)Codeflix_Bots
# Support @rohit_1888 on Tg

from aiohttp import web
from .route import routes

# Import all plugin modules
from .start import *
from .channel_post import *
from .link_generator import *
from .admin import *
from .sequence_batch import *  # Add this line
from .callbacks import *
from .database import *

async def web_server():
    web_app = web.Application(client_max_size=30000000)
    web_app.add_routes(routes)
    return web_app
