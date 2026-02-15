# callbacks.py - Add this file in your plugins folder

from pyrogram import filters
from pyrogram.types import CallbackQuery
from pyrogram.enums import ParseMode
from bot import Bot
from config import CUSTOM_CAPTION, PROTECT_CONTENT
from helper_func import is_subscribed, not_joined
from database.database import db

@Bot.on_callback_query(filters.regex(r"^getfile_(\d+)_(primary|secondary)$"))
async def get_file_callback(client: Bot, callback_query: CallbackQuery):
    """Handle file retrieval from sequence batch"""
    msg_id = int(callback_query.data.split("_")[1])
    channel_type = callback_query.data.split("_")[2]
    user_id = callback_query.from_user.id
    
    # Check if user is banned
    banned_users = await db.get_ban_users()
    if user_id in banned_users:
        await callback_query.answer("You are banned from using this bot!", show_alert=True)
        return
    
    # Check subscription
    if not await is_subscribed(client, user_id):
        await callback_query.answer("Please join the required channels first!", show_alert=True)
        await not_joined(client, callback_query.message)
        return
    
    await callback_query.answer("Fetching file...")
    
    try:
        # Get the message from the appropriate channel
        target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel
        
        if not target_channel:
            await callback_query.message.reply("❌ Channel not available!")
            return
        
        msg = await client.get_messages(target_channel.id, msg_id)
        
        if not msg:
            await callback_query.message.reply("❌ File not found!")
            return
        
        # Prepare caption
        caption = ""
        if msg.document:
            if CUSTOM_CAPTION:
                caption = CUSTOM_CAPTION.format(
                    previouscaption="" if not msg.caption else msg.caption.html,
                    filename=msg.document.file_name
                )
            elif msg.caption:
                caption = msg.caption.html
        elif msg.caption:
            caption = msg.caption.html
        
        # Send the file
        await msg.copy(
            chat_id=user_id,
            caption=caption,
            parse_mode=ParseMode.HTML,
            protect_content=PROTECT_CONTENT
        )
        
    except Exception as e:
        await callback_query.message.reply(f"❌ Error: {str(e)}")
