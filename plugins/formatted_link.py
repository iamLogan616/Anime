#(©)CodeFlix_Bots
#@rohit_1888

import re
import asyncio
from typing import List, Dict, Tuple
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from pyrogram.errors import FloodWait
from bot import Bot
from helper_func import encode, get_message_id, admin, decode, get_messages
from config import PERMANENT_LINKS, BLOGSPOT_URL, BLOGSPOT_PARAM

# State management for formatted link command
user_states = {}
quality_map = {
    "360p": "360P",
    "480p": "480P", 
    "720p": "720P",
    "1080p": "1080P",
    "hdrip": "HDRIP",
    "4k": "4K"
}

def generate_link(base64_string, client):
    """Generate link - permanent or direct"""
    if PERMANENT_LINKS and BLOGSPOT_URL:
        return f"{BLOGSPOT_URL}?{BLOGSPOT_PARAM}={base64_string}"
    else:
        return f"https://t.me/{client.username}?start={base64_string}"

async def parse_format_input(text: str) -> Dict[str, int]:
    """Parse format input like '360P = 2, 480P = 2, 720P = 2'"""
    format_data = {}
    try:
        # Remove extra spaces and split by comma
        parts = [p.strip() for p in text.split(',')]
        
        for part in parts:
            if '=' in part:
                key, value = part.split('=', 1)
                key = key.strip().upper()
                value = value.strip()
                
                # Map to standardized keys
                for q_key, std_key in quality_map.items():
                    if key == q_key.upper():
                        format_data[std_key] = int(value)
                        break
                else:
                    format_data[key] = int(value)
    
    except Exception as e:
        return {}
    
    return format_data

async def get_file_ids_from_format(client: Client, start_message: Message, format_data: Dict[str, int], channel_type: str):
    """Get file IDs based on format specification"""
    file_ids = {}
    
    # Get the first message ID
    first_msg_id = await get_message_id(client, start_message)
    if not first_msg_id:
        return None, "Could not get message ID from the provided message"
    
    # Check if forwarded from correct channel
    if start_message.forward_from_chat:
        if channel_type == "primary" and start_message.forward_from_chat.id != client.db_channel.id:
            return None, "Message is not from primary DB channel"
        elif channel_type == "secondary" and start_message.forward_from_chat.id != client.secondary_channel.id:
            return None, "Message is not from secondary DB channel"
    
    target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel
    
    # Calculate total files needed and distribute
    total_files_needed = sum(format_data.values())
    message_ids = list(range(first_msg_id, first_msg_id + total_files_needed))
    
    try:
        messages = await get_messages(client, message_ids, channel=channel_type)
        if len(messages) != total_files_needed:
            return None, f"Expected {total_files_needed} files but found {len(messages)}"
        
        # Distribute files to qualities
        current_index = 0
        for quality, count in format_data.items():
            quality_ids = []
            for i in range(count):
                if current_index < len(messages):
                    quality_ids.append(message_ids[current_index])
                    current_index += 1
            
            if quality_ids:
                file_ids[quality] = quality_ids
    
    except Exception as e:
        return None, f"Error fetching messages: {str(e)}"
    
    return file_ids, None

async def create_formatted_link(client: Client, file_ids: Dict[str, List[int]], channel_type: str):
    """Create formatted link with quality buttons"""
    target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel
    channel_multiplier = abs(target_channel.id)
    
    # Create base64 strings for each quality
    buttons = []
    
    for quality, ids in file_ids.items():
        if len(ids) == 1:
            string = f"get-{ids[0] * channel_multiplier}"
        else:
            string = f"get-{ids[0] * channel_multiplier}-{ids[-1] * channel_multiplier}"
        
        if channel_type == "secondary":
            string = f"sec-{string}"
        
        base64_string = await encode(string)
        link = generate_link(base64_string, client)
        
        buttons.append([InlineKeyboardButton(f"📥 {quality}", url=link)])
    
    # Create message text
    formatted_text = "<b>🎬 Formatted Download Links</b>\n\n"
    formatted_text += "<b>Available Qualities:</b>\n"
    
    for quality in file_ids.keys():
        file_count = len(file_ids[quality])
        formatted_text += f"• {quality}: {file_count} file{'s' if file_count > 1 else ''}\n"
    
    formatted_text += f"\n<b>Channel:</b> {target_channel.title}\n"
    formatted_text += f"<b>Channel Type:</b> {channel_type.capitalize()}\n"
    
    if PERMANENT_LINKS and BLOGSPOT_URL:
        formatted_text += "\n🔗 <b>Permanent Link</b>\n"
    else:
        formatted_text += "\n🤖 <b>Direct Link</b>\n"
    
    return formatted_text, buttons

@Bot.on_message(filters.private & admin & filters.command('format'))
async def format_command(client: Client, message: Message):
    """Handle /format command for formatted link creation"""
    user_id = message.from_user.id
    
    # Clear existing state
    if user_id in user_states:
        del user_states[user_id]
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Start Creating", callback_data="format_start")],
        [InlineKeyboardButton("📖 How to Use", callback_data="format_help"),
         InlineKeyboardButton("❌ Cancel", callback_data="format_cancel")]
    ])
    
    await message.reply(
        "**📝 Formatted Link Generator**\n\n"
        "Create download links with multiple quality buttons in one message!\n\n"
        "**Click '🚀 Start Creating' to begin.**",
        reply_markup=keyboard
    )

@Bot.on_callback_query(filters.regex(r"^format_"))
async def format_callback_handler(client: Client, callback_query):
    """Handle format callback queries"""
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    if data == "format_start":
        user_states[user_id] = {"step": "choose_channel"}
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📌 Primary Channel", callback_data="format_channel_primary")],
            [InlineKeyboardButton("📂 Secondary Channel", callback_data="format_channel_secondary")],
            [InlineKeyboardButton("◀️ Back", callback_data="format_back")]
        ])
        
        await callback_query.message.edit_text(
            "**Step 1: Select Channel**\n\n"
            "Choose which channel to use:",
            reply_markup=keyboard
        )
    
    elif data == "format_help":
        help_text = (
            "**📖 How to Use /format**\n\n"
            "**1.** Click '🚀 Start Creating'\n"
            "**2.** Select channel (Primary/Secondary)\n"
            "**3.** Enter format like:\n"
            "```\n480P = 1, 720P = 1, 1080P = 1```\n"
            "**4.** Forward first message from DB channel\n\n"
            "**Example Format:**\n"
            "• `480P = 2` → 2 files for 480P quality\n"
            "• `1080P = 1` → 1 file for 1080P quality\n\n"
            "**Note:** Files must be in sequence!"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Start Now", callback_data="format_start")],
            [InlineKeyboardButton("◀️ Back", callback_data="format_back")]
        ])
        
        await callback_query.message.edit_text(help_text, reply_markup=keyboard)
    
    elif data == "format_back":
        await format_command(client, callback_query.message)
    
    elif data == "format_cancel":
        if user_id in user_states:
            del user_states[user_id]
        await callback_query.message.delete()
    
    elif data.startswith("format_channel_"):
        channel_type = data.split("_")[2]
        user_states[user_id] = {
            "step": "enter_format",
            "channel_type": channel_type
        }
        
        format_example = (
            "**Step 2: Enter Format**\n\n"
            f"Channel: **{channel_type.capitalize()}**\n\n"
            "**Format Examples:**\n"
            "```\n"
            "480P = 2, 720P = 2, 1080P = 1\n"
            "360P = 1, 480P = 1, 720P = 1, HDRIP = 1\n"
            "```\n\n"
            "**Send your format now:**\n"
            "(Reply with your format or type 'cancel' to stop)"
        )
        
        await callback_query.message.edit_text(format_example)
    
    await callback_query.answer()

@Bot.on_message(filters.private & admin & filters.text)
async def handle_format_steps(client: Client, message: Message):
    """Handle format creation steps"""
    user_id = message.from_user.id
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    step = state.get("step")
    
    # Check for cancel
    if message.text.lower() == "cancel":
        if user_id in user_states:
            del user_states[user_id]
        await message.reply("❌ Format creation cancelled.", reply_markup=ReplyKeyboardRemove())
        return
    
    if step == "enter_format":
        # Parse format
        format_data = await parse_format_input(message.text)
        
        if not format_data:
            await message.reply(
                "❌ Invalid format. Please use format like:\n"
                "```\n480P = 2, 720P = 1, 1080P = 1```\n\n"
                "**Try again:**",
                reply_markup=ReplyKeyboardMarkup([["Cancel"]], resize_keyboard=True)
            )
            return
        
        state["format_data"] = format_data
        state["step"] = "get_first_message"
        
        channel_type = state.get("channel_type", "primary")
        total_files = sum(format_data.values())
        
        await message.reply(
            f"**✅ Format Accepted!**\n\n"
            f"**Summary:**\n"
            + "\n".join([f"• {q}: {c} file{'s' if c > 1 else ''}" for q, c in format_data.items()])
            + f"\n\n**Total files:** {total_files}\n\n"
            f"**Step 3: Send First Message**\n"
            f"Forward the first message from {channel_type} DB channel.\n"
            f"**Note:** Next {total_files} files must be in sequence!",
            reply_markup=ReplyKeyboardMarkup([["Cancel"]], resize_keyboard=True)
        )
    
    elif step == "get_first_message":
        channel_type = state.get("channel_type", "primary")
        format_data = state.get("format_data", {})
        
        if channel_type == "secondary" and not client.secondary_channel:
            del user_states[user_id]
            await message.reply("❌ Secondary channel not available.", reply_markup=ReplyKeyboardRemove())
            return
        
        # Process message
        processing_msg = await message.reply("⏳ Processing...")
        
        file_ids, error = await get_file_ids_from_format(client, message, format_data, channel_type)
        
        if error:
            del user_states[user_id]
            await processing_msg.delete()
            await message.reply(f"❌ Error: {error}", reply_markup=ReplyKeyboardRemove())
            return
        
        # Create formatted links
        formatted_text, buttons = await create_formatted_link(client, file_ids, channel_type)
        
        # Add share and channel buttons
        target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel
        channel_link = f"https://t.me/{target_channel.username}" if target_channel.username else f"https://t.me/c/{str(target_channel.id)[4:]}" if str(target_channel.id).startswith('-100') else f"https://t.me/{target_channel.id}"
        
        buttons.append([InlineKeyboardButton("🔁 Share", url=f"https://t.me/share/url?url={formatted_text}")])
        buttons.append([InlineKeyboardButton("📺 View Channel", url=channel_link)])
        
        keyboard = InlineKeyboardMarkup(buttons)
        
        await processing_msg.delete()
        await message.reply(formatted_text, reply_markup=keyboard)
        
        # Clear state
        del user_states[user_id]
        await message.reply("✅ Formatted links created!", reply_markup=ReplyKeyboardRemove())
