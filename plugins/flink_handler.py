# Don't Remove Credit @CodeFlix_Bots, @rohit_1888
# Ask Doubt on telegram @CodeflixSupport
#
# Copyright (C) 2025 by Codeflix-Bots@Github, < https://github.com/Codeflix-Bots >.
#
# This file is part of < https://github.com/Codeflix-Bots/FileStore > project,
# and is released under the MIT License.
# Please see < https://github.com/Codeflix-Bots/FileStore/blob/master/LICENSE >
#
# All rights reserved.
#

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from bot import Bot
from helper_func import encode, get_message_id
from config import OWNER_ID
from database.database import db  # Make sure this import works
import re
import logging

print("✅ flink_handler.py is loading...")

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store user data for flink command
flink_user_data = {}

# Simple filter for flink db post input
async def flink_db_post_filter(_, __, message: Message):
    user_id = message.from_user.id
    if user_id not in flink_user_data:
        return False
    state = flink_user_data[user_id].get('awaiting_db_post')
    return state and (message.forward_from_chat or (message.text and message.text.startswith('https://t.me/')))

@Bot.on_message(filters.private & filters.command('flink'))
async def flink_command(client: Client, message: Message):
    """Handle /flink command for formatted link generation."""
    try:
        # Check if user is admin (using your admin check from helper_func)
        from helper_func import check_admin
        if not await check_admin(None, client, message):
            await message.reply_text("❌ You are not authorized to use this command!")
            return

        flink_user_data[message.from_user.id] = {
            'format': None,
            'links': {},
            'edit_data': {},
            'awaiting_format': False,
            'awaiting_caption': False,
            'awaiting_db_post': False
        }
        
        await show_flink_main_menu(client, message)
    except Exception as e:
        logger.error(f"error in flink_command: {e}")
        await message.reply_text("❌ An error occurred. Please try again.")

async def show_flink_main_menu(client: Client, message: Message, edit: bool = False):
    """Show the main menu for the flink command."""
    try:
        current_format = flink_user_data[message.from_user.id]['format'] or "Not set"
        text = f"**Formatted Link Generator**\n\n**Current format:**\n`{current_format}`"
        
        buttons = [
            [
                InlineKeyboardButton("📝 Set Format", callback_data="flink_set_format"),
                InlineKeyboardButton("🚀 Start Process", callback_data="flink_start_process")
            ],
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="flink_refresh"),
                InlineKeyboardButton("❌ Close", callback_data="flink_close")
            ]
        ]
        
        if edit:
            await message.edit_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            await message.reply(
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
    except Exception as e:
        logger.error(f"error in show_flink_main_menu: {e}")
        await message.reply_text("❌ An error occurred while showing menu.")

@Bot.on_callback_query(filters.regex(r"^flink_set_format$"))
async def flink_set_format_callback(client: Client, query: CallbackQuery):
    """Handle callback for setting format in flink command."""
    try:
        from helper_func import check_admin
        if not await check_admin(None, client, query):
            await query.answer("You are not authorized!", show_alert=True)
            return

        flink_user_data[query.from_user.id]['awaiting_format'] = True
        await query.message.edit_text(
            text="**📝 Set Format**\n\n"
                 "Send your format like this:\n"
                 "`360p = 2, 720p = 2, 1080p = 2`\n\n"
                 "Meaning: 2 files for 360p, 2 for 720p, etc.\n\n"
                 "Send the format in the next message.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="flink_back_to_menu")]
            ])
        )
        await query.answer("Enter format")
    except Exception as e:
        logger.error(f"error in flink_set_format_callback: {e}")
        await query.message.edit_text("❌ An error occurred while setting format.")

@Bot.on_message(filters.private & filters.text)
async def handle_format_input(client: Client, message: Message):
    """Handle format input for flink command."""
    user_id = message.from_user.id
    
    if user_id not in flink_user_data:
        return
    
    if flink_user_data[user_id].get('awaiting_format'):
        # Check if it's a valid format
        format_text = message.text.strip()
        
        # Simple format validation
        parts = [p.strip() for p in format_text.split(",")]
        valid = True
        for part in parts:
            if not re.match(r"^[a-zA-Z0-9]+\s*=\s*\d+$", part):
                valid = False
                break
        
        if valid:
            flink_user_data[user_id]['format'] = format_text
            flink_user_data[user_id]['awaiting_format'] = False
            await message.reply_text(f"✅ **Format saved:**\n`{format_text}`")
            await show_flink_main_menu(client, message)
        else:
            await message.reply_text(
                "❌ **Invalid format!**\n\n"
                "Use format like:\n"
                "`360p = 2, 720p = 1, 1080p = 2`\n\n"
                "Try again:"
            )

@Bot.on_callback_query(filters.regex(r"^flink_start_process$"))
async def flink_start_process_callback(client: Client, query: CallbackQuery):
    """Handle callback to start the flink process."""
    try:
        from helper_func import check_admin
        if not await check_admin(None, client, query):
            await query.answer("You are not authorized!", show_alert=True)
            return

        if not flink_user_data[query.from_user.id]['format']:
            await query.answer("❌ Please set format first!", show_alert=True)
            return
        
        flink_user_data[query.from_user.id]['awaiting_db_post'] = True
        await query.message.edit_text(
            text="**📤 Send DB Channel Post**\n\n"
                 "Forward the FIRST message from your DB channel\n"
                 "OR send the post link (t.me/...)\n\n"
                 "Files should be in sequence without gaps.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="flink_cancel_process")]
            ])
        )
        await query.answer("Send db channel post")
    except Exception as e:
        logger.error(f"error in flink_start_process_callback: {e}")
        await query.message.edit_text("❌ An error occurred while starting process.")

@Bot.on_message(filters.private & (filters.forwarded | filters.text))
async def handle_db_post_input(client: Client, message: Message):
    """Handle db channel post input for flink command."""
    user_id = message.from_user.id
    
    if user_id not in flink_user_data or not flink_user_data[user_id].get('awaiting_db_post'):
        return
    
    try:
        from helper_func import check_admin
        if not await check_admin(None, client, message):
            return

        msg_id = await get_message_id(client, message)
        if not msg_id:
            await message.reply_text("❌ Invalid message! Forward from DB channel or send valid link.")
            return
                
        format_str = flink_user_data[user_id]['format']
        format_parts = [part.strip() for part in format_str.split(",")]
        
        current_id = msg_id
        links = {}
        
        for part in format_parts:
            match = re.match(r"([a-zA-Z0-9]+)\s*=\s*(\d+)", part)
            if not match:
                await message.reply_text(f"❌ Invalid format part: `{part}`")
                continue
                
            quality, count = match.groups()
            quality = quality.strip().upper()
            count = int(count.strip())
            
            # Calculate IDs
            start_id = current_id
            end_id = current_id + count - 1
            
            links[quality] = {
                'start': start_id,
                'end': end_id,
                'count': count
            }
            
            current_id = end_id + 1
        
        flink_user_data[user_id]['links'] = links
        flink_user_data[user_id]['awaiting_db_post'] = False
        
        # Generate buttons
        await generate_flink_output(client, message)
        
    except Exception as e:
        logger.error(f"error in handle_db_post_input: {e}")
        await message.reply_text(f"❌ Error: {str(e)}")

async def generate_flink_output(client: Client, message: Message):
    """Generate the final output with download buttons."""
    try:
        user_id = message.from_user.id
        links = flink_user_data[user_id]['links']
        
        if not links:
            await message.reply_text("❌ No links generated.")
            return
        
        buttons = []
        for quality, data in links.items():
            # Create Telegram bot URL
            string = f"get-{data['start'] * abs(client.db_channel.id)}-{data['end'] * abs(client.db_channel.id)}"
            base64_string = await encode(string)
            url = f"https://t.me/{client.username}?start={base64_string}"
            
            buttons.append([InlineKeyboardButton(f"📥 {quality}", url=url)])
        
        # Add edit/done buttons
        buttons.append([
            InlineKeyboardButton("✏️ Edit", callback_data="flink_edit_output"),
            InlineKeyboardButton("✅ Done", callback_data="flink_done_output")
        ])
        
        await message.reply_text(
            f"✅ **Download Links Generated**\n\n"
            f"Format: `{flink_user_data[user_id]['format']}`\n"
            f"Starting from ID: {list(links.values())[0]['start']}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        logger.error(f"error in generate_flink_output: {e}")
        await message.reply_text("❌ Error generating output.")

@Bot.on_callback_query(filters.regex(r"^flink_done_output$"))
async def flink_done_output_callback(client: Client, query: CallbackQuery):
    """Handle callback for finalizing flink output."""
    try:
        user_id = query.from_user.id
        if user_id in flink_user_data:
            del flink_user_data[user_id]
        
        await query.answer("✅ Process completed!")
        await query.message.delete()
        
    except Exception as e:
        logger.error(f"error in flink_done_output_callback: {e}")
        await query.answer("❌ Error!", show_alert=True)

@Bot.on_callback_query(filters.regex(r"^flink_refresh$"))
async def flink_refresh_callback(client: Client, query: CallbackQuery):
    """Handle callback to refresh flink menu."""
    try:
        await show_flink_main_menu(client, query.message, edit=True)
        await query.answer("♻️ Refreshed")
    except Exception as e:
        logger.error(f"error in flink_refresh_callback: {e}")
        await query.answer("❌ Error!", show_alert=True)

@Bot.on_callback_query(filters.regex(r"^flink_(back_to_menu|cancel_process|close)$"))
async def flink_handle_back_buttons(client: Client, query: CallbackQuery):
    """Handle back, cancel, and close actions for flink command."""
    try:
        action = query.data.split("_")[-1]
        
        if action == "back_to_menu":
            await show_flink_main_menu(client, query.message, edit=True)
            await query.answer("🔙 Back to menu")
        elif action == "cancel_process":
            user_id = query.from_user.id
            if user_id in flink_user_data:
                del flink_user_data[user_id]
            await query.message.edit_text("❌ Process cancelled.")
            await query.answer("Process cancelled")
        elif action == "close":
            user_id = query.from_user.id
            if user_id in flink_user_data:
                del flink_user_data[user_id]
            await query.message.delete()
            await query.answer("Closed")
    except Exception as e:
        logger.error(f"error in flink_handle_back_buttons: {e}")
        await query.answer("❌ Error!", show_alert=True)

#
# Copyright (C) 2025 by Codeflix-Bots@Github, < https://github.com/Codeflix-Bots >.
#
# This file is part of < https://github.com/Codeflix-Bots/FileStore > project,
# and is released under the MIT License.
# Please see < https://github.com/Codeflix-Bots/FileStore/blob/master/LICENSE >
#
# All rights reserved.
