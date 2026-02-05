from aiohttp import web
from plugins import web_server
import asyncio
import pyromod.listen
from pyrogram import Client
from pyrogram.enums import ParseMode
import sys
from datetime import datetime
#rohit_1888 on Tg
from config import *


name ="""
 BY CODEFLIX BOTS
"""


class Bot(Client):
    def __init__(self):
        super().__init__(
            name="Bot",
            api_hash=API_HASH,
            api_id=APP_ID,
            plugins={
                "root": "plugins"
            },
            workers=TG_BOT_WORKERS,
            bot_token=TG_BOT_TOKEN
        )
        self.LOGGER = LOGGER
        self.db_channel = None
        self.secondary_channel = None  # New: Secondary channel

    async def start(self):
        await super().start()
        usr_bot_me = await self.get_me()
        self.uptime = datetime.now()

        # Primary channel setup
        try:
            db_channel = await self.get_chat(CHANNEL_ID)
            self.db_channel = db_channel
            test = await self.send_message(chat_id = db_channel.id, text = "Test Message - Primary Channel")
            await test.delete()
            self.LOGGER(__name__).info(f"Primary DB Channel Loaded: {db_channel.title}")
        except Exception as e:
            self.LOGGER(__name__).warning(e)
            self.LOGGER(__name__).warning(f"Make Sure bot is Admin in DB Channel, and Double check the CHANNEL_ID Value, Current Value {CHANNEL_ID}")
            self.LOGGER(__name__).info("\nBot Stopped. Join https://t.me/CodeflixSupport for support")
            sys.exit()

        # Secondary channel setup (if provided)
        if SECONDARY_CHANNEL_ID:
            try:
                secondary_channel = await self.get_chat(SECONDARY_CHANNEL_ID)
                self.secondary_channel = secondary_channel
                test2 = await self.send_message(chat_id=secondary_channel.id, text="Test Message - Secondary Channel")
                await test2.delete()
                self.LOGGER(__name__).info(f"Secondary DB Channel Loaded: {secondary_channel.title}")
            except Exception as e:
                self.LOGGER(__name__).warning(f"Secondary Channel Error: {e}")
                self.LOGGER(__name__).warning("Secondary channel not loaded, but bot will continue with primary only.")
                self.secondary_channel = None
        else:
            self.LOGGER(__name__).info("No secondary channel configured.")

        self.set_parse_mode(ParseMode.HTML)
        self.LOGGER(__name__).info(f"Bot Running..!\n\nCreated by \nhttps://t.me/CodeflixSupport")
        self.LOGGER(__name__).info(f"""BOT DEPLOYED BY @CODEFLIX_BOTS""")

        self.set_parse_mode(ParseMode.HTML)
        self.username = usr_bot_me.username
        
        if self.secondary_channel:
            self.LOGGER(__name__).info(f"Bot Running with 2 DB Channels!")
        else:
            self.LOGGER(__name__).info(f"Bot Running with 1 DB Channel!")

        # Start Web Server
        app = web.AppRunner(await web_server())
        await app.setup()
        await web.TCPSite(app, "0.0.0.0", PORT).start()

        try: 
            if self.secondary_channel:
                await self.send_message(OWNER_ID, text = f"<b><blockquote>✅ Bᴏᴛ Rᴇsᴛᴀʀᴛᴇᴅ with 2 DB Channels by @Codeflix_Bots\n\nPrimary: {self.db_channel.title}\nSecondary: {self.secondary_channel.title}</blockquote></b>")
            else:
                await self.send_message(OWNER_ID, text = f"<b><blockquote>✅ Bᴏᴛ Rᴇsᴛᴀʀᴛᴇᴅ with 1 DB Channel by @Codeflix_Bots\n\nPrimary: {self.db_channel.title}</blockquote></b>")
        except: 
            pass

    async def stop(self, *args):
        await super().stop()
        self.LOGGER(__name__).info("Bot stopped.")

    def run(self):
        """Run the bot."""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.start())
        self.LOGGER(__name__).info("Bot is now running. Thanks to @rohit_1888")
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            self.LOGGER(__name__).info("Shutting down...")
        finally:
            loop.run_until_complete(self.stop())

#
# Copyright (C) 2025 by Codeflix-Bots@Github, < https://github.com/Codeflix-Bots >.
#
# This file is part of < https://github.com/Codeflix-Bots/FileStore > project,
# and is released under the MIT License.
# Please see < https://github.com/Codeflix-Bots/FileStore/blob/master/LICENSE >
#
# All rights reserved.
