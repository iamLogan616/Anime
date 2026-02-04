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
from database.database import db

# State management for /flink command
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
    """Generate link - permanent for /flink, direct for channel_post"""
    if PERMANENT_LINKS and BLOGSPOT_URL:
        return f"{BLOGSPOT_URL}?{BLOGSPOT_PARAM}={base64_string}"
    else:
        return f"https://t.me/{client.username}?start={base64_string}"

async def choose_channel_for_flink(client: Client, message: Message):
    """Let admin choose which channel to use for formatted links"""
    if not client.secondary_channel:
        return "primary"
    
    keyboard = ReplyKeyboardMarkup(
        [
            ["📌 Primary Channel"],
            ["📂 Secondary Channel"],
            ["❌ Cancel"]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.reply("📌 Select channel for formatted link creation:", reply_markup=keyboard)
    
    try:
        response = await client.listen(
            chat_id=message.chat.id,
            filters=filters.text & filters.regex(r"^(📌 Primary Channel|📂 Secondary Channel|❌ Cancel)$"),
            timeout=30
        )
        
        if response.text == "❌ Cancel":
            await message.reply("❌ Operation cancelled.", reply_markup=ReplyKeyboardRemove())
            return None
        elif response.text == "📂 Secondary Channel":
            return "secondary"
        else:
            return "primary"
            
    except asyncio.TimeoutError:
        await message.reply("⏰ Timed out. Operation cancelled.", reply_markup=ReplyKeyboardRemove())
        return None

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
        print(f"Error parsing format: {e}")
        return {}
    
    return format_data

async def get_file_ids_from_format(client: Client, start_message: Message, format_data: Dict[str, int], channel_type: str):
    """Get file IDs based on format specification"""
    file_ids = {}
    total_files_needed = sum(format_data.values())
    
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
    
    # Calculate range of message IDs needed
    start_id = first_msg_id
    end_id = first_msg_id + total_files_needed - 1
    
    # Fetch all messages in the range
    message_ids = list(range(start_id, end_id + 1))
    
    try:
        messages = await get_messages(client, message_ids, channel=channel_type)
        if len(messages) != total_files_needed:
            return None, f"Expected {total_files_needed} files but found {len(messages)}. Make sure files are in sequence without gaps."
        
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
    quality_links = {}
    buttons = []
    
    for quality, ids in file_ids.items():
        if len(ids) == 1:
            # Single file
            string = f"get-{ids[0] * channel_multiplier}"
        else:
            # Multiple files
            string = f"get-{ids[0] * channel_multiplier}-{ids[-1] * channel_multiplier}"
        
        # Add prefix for secondary channel
        if channel_type == "secondary":
            string = f"sec-{string}"
        
        base64_string = await encode(string)
        link = generate_link(base64_string, client)
        quality_links[quality] = link
        
        # Add button for this quality
        buttons.append([InlineKeyboardButton(f"📥 {quality}", url=link)])
    
    # Create main message with all buttons
    formatted_text = "<b>🎬 Formatted Download Links</b>\n\n"
    formatted_text += "<b>Available Qualities:</b>\n"
    
    for quality in file_ids.keys():
        file_count = len(file_ids[quality])
        formatted_text += f"• {quality}: {file_count} file{'s' if file_count > 1 else ''}\n"
    
    # Add channel info
    formatted_text += f"\n<b>Channel:</b> {target_channel.title}\n"
    formatted_text += f"<b>Channel Type:</b> {channel_type.capitalize()}\n"
    
    # Add link type info
    if PERMANENT_LINKS and BLOGSPOT_URL:
        formatted_text += "\n🔗 <b>Permanent Link</b> - Will work even if bot gets banned\n"
    else:
        formatted_text += "\n🤖 <b>Direct Link</b> - Will stop working if bot gets banned\n"
    
    return formatted_text, buttons

@Bot.on_message(filters.private & admin & filters.command('formatlink'))
async def flink_command(client: Client, message: Message):
    """Handle /flink command for formatted link creation"""
    user_id = message.from_user.id
    
    # Create initial keyboard
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("• sᴇᴛ ғᴏʀᴍᴀᴛ •", callback_data="flink_set_format")],
        [InlineKeyboardButton("• ʜᴏᴡ ᴛᴏ ᴜsᴇ •", callback_data="flink_help"),
         InlineKeyboardButton("• ᴄᴀɴᴄᴇʟ •", callback_data="flink_cancel")]
    ])
    
    await message.reply(
        "**📝 Formatted Link Generator**\n\n"
        "This feature allows you to create formatted download links with multiple quality buttons.\n\n"
        "Click **• sᴇᴛ ғᴏʀᴍᴀᴛ •** to start creating formatted links.",
        reply_markup=keyboard
    )

@Bot.on_callback_query(filters.regex(r"^flink_"))
async def flink_callback_handler(client: Client, callback_query):
    """Handle /flink callback queries"""
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    if data == "flink_set_format":
        # Store user state
        user_states[user_id] = {"step": "choose_channel"}
        
        # Ask to choose channel
        await callback_query.message.edit_text(
            "**📌 Step 1: Select Channel**\n\n"
            "Please select which channel to use for formatted links:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📌 Primary Channel", callback_data="flink_channel_primary")],
                [InlineKeyboardButton("📂 Secondary Channel", callback_data="flink_channel_secondary")],
                [InlineKeyboardButton("❌ Cancel", callback_data="flink_cancel")]
            ])
        )
    
    elif data.startswith("flink_channel_"):
        channel_type = data.split("_")[2]
        user_states[user_id] = {
            "step": "enter_format",
            "channel_type": channel_type
        }
        
        await callback_query.message.edit_text(
            f"**📝 Step 2: Enter Format**\n\n"
            f"Please enter the format for {channel_type.capitalize()} Channel.\n\n"
            "**Format Example:**\n"
            "```\n"
            "360P = 2, 480P = 2, 720P = 2\n"
            "1080P = 2, HDRIP = 1, 4K = 1\n"
            "```\n\n"
            "**Explanation:**\n"
            "• `360P = 2` → 2 files for 360P quality\n"
            "• `HDRIP = 1` → 1 file for HDRIP quality\n\n"
            "**Send your format now:**\n"
            "(Type `CANCEL` to cancel)",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="flink_cancel")]
            ])
        )
    
    elif data == "flink_help":
        await callback_query.message.edit_text(
            "**📖 How to Use /flink**\n\n"
            "**Step 1:** Click '• sᴇᴛ ғᴏʀᴍᴀᴛ •'\n"
            "**Step 2:** Select channel (Primary/Secondary)\n"
            "**Step 3:** Enter format like:\n"
            "```\n"
            "480P = 1, 720P = 1, 1080P = 1\n"
            "```\n"
            "**Step 4:** Forward first message from DB channel\n"
            "**Step 5:** Bot creates formatted links\n\n"
            "**Important:**\n"
            "• Files must be in sequence without gaps\n"
            "• Use CAPITAL letters for quality names\n"
            "• Type `CANCEL` anytime to stop",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Back", callback_data="flink_back"),
                 InlineKeyboardButton("🚀 Start Now", callback_data="flink_set_format")]
            ])
        )
    
    elif data == "flink_back":
        await flink_command(client, callback_query.message)
    
    elif data == "flink_cancel":
        if user_id in user_states:
            del user_states[user_id]
        await callback_query.message.delete()
        await callback_query.message.reply("❌ Formatted link creation cancelled.", reply_markup=ReplyKeyboardRemove())
    
    await callback_query.answer()

@Bot.on_message(filters.private & admin & filters.text & ~filters.command(['start', 'batch', 'genlink', 'custom_batch', 'flink']))
async def handle_flink_steps(client: Client, message: Message):
    """Handle /flink step-by-step process"""
    user_id = message.from_user.id
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    step = state.get("step")
    
    # Check for cancel
    if message.text.upper() == "CANCEL":
        if user_id in user_states:
            del user_states[user_id]
        await message.reply("❌ Formatted link creation cancelled.", reply_markup=ReplyKeyboardRemove())
        return
    
    if step == "enter_format":
        # Parse format input
        format_data = await parse_format_input(message.text)
        
        if not format_data:
            await message.reply(
                "❌ Invalid format. Please enter in the correct format:\n\n"
                "**Example:**\n"
                "```\n"
                "480P = 1, 720P = 1, 1080P = 1\n"
                "```\n\n"
                "**Try again:** (or type `CANCEL` to cancel)",
                reply_markup=ReplyKeyboardMarkup([["❌ Cancel"]], resize_keyboard=True)
            )
            return
        
        # Store format data
        state["format_data"] = format_data
        state["step"] = "get_first_message"
        
        channel_type = state.get("channel_type", "primary")
        
        await message.reply(
            f"**✅ Format Accepted!**\n\n"
            f"**Format Summary for {channel_type.capitalize()} Channel:**\n"
            + "\n".join([f"• {quality}: {count} file{'s' if count > 1 else ''}" 
                        for quality, count in format_data.items()])
            + f"\n\n**Total Files Needed:** {sum(format_data.values())}\n\n"
            f"**📤 Step 3: Send First Message**\n\n"
            f"Now forward the **first message** from {channel_type.capitalize()} DB Channel "
            f"(with quotes) or send the DB channel post link.\n\n"
            f"**Important:** The next {sum(format_data.values())} files must be in sequence!",
            reply_markup=ReplyKeyboardMarkup([["❌ Cancel"]], resize_keyboard=True)
        )
    
    elif step == "get_first_message":
        # Get channel type and format data
        channel_type = state.get("channel_type", "primary")
        format_data = state.get("format_data", {})
        
        if channel_type == "secondary" and not client.secondary_channel:
            del user_states[user_id]
            await message.reply("❌ Secondary channel not configured.", reply_markup=ReplyKeyboardRemove())
            return
        
        # Process the first message
        processing_msg = await message.reply("⏳ Processing format and fetching files...")
        
        # Get file IDs based on format
        file_ids, error = await get_file_ids_from_format(client, message, format_data, channel_type)
        
        if error:
            del user_states[user_id]
            await processing_msg.delete()
            await message.reply(f"❌ Error: {error}", reply_markup=ReplyKeyboardRemove())
            return
        
        # Create formatted links
        formatted_text, buttons = await create_formatted_link(client, file_ids, channel_type)
        
        # Add share button
        buttons.append([InlineKeyboardButton("🔁 Share", callback_data="flink_share")])
        
        # Add view channel button
        target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel
        channel_link = f"https://t.me/{target_channel.username}" if target_channel.username else f"https://t.me/c/{str(target_channel.id)[4:]}" if str(target_channel.id).startswith('-100') else f"https://t.me/{target_channel.id}"
        buttons.append([InlineKeyboardButton("📺 View Channel", url=channel_link)])
        
        # Create final message
        keyboard = InlineKeyboardMarkup(buttons)
        
        await processing_msg.delete()
        await message.reply(formatted_text, reply_markup=keyboard)
        
        # Clear user state
        del user_states[user_id]
        await message.reply("✅ Formatted links created successfully!", reply_markup=ReplyKeyboardRemove())

@Bot.on_callback_query(filters.regex(r"^flink_share$"))
async def share_flink_callback(client: Client, callback_query):
    """Handle share button for formatted links"""
    message_text = callback_query.message.text
    message_text += "\n\n🔗 **Shared via @CodeFlix_Bots**"
    
    share_keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📱 Share to Chat", 
                           url=f"https://t.me/share/url?url={callback_query.message.link}&text=Check%20out%20these%20formatted%20download%20links!"),
        InlineKeyboardButton("◀️ Back", callback_data="flink_share_back")
    ]])
    
    await callback_query.message.edit_text(
        message_text,
        reply_markup=share_keyboard
    )
    await callback_query.answer("Share these links with others!")

@Bot.on_callback_query(filters.regex(r"^flink_share_back$"))
async def flink_share_back_callback(client: Client, callback_query):
    """Go back from share view"""
    # Extract original buttons from message text
    original_text = callback_query.message.text
    original_text = original_text.replace("\n\n🔗 **Shared via @CodeFlix_Bots**", "")
    
    # Recreate original keyboard (simplified - in real implementation you might want to store it)
    await callback_query.message.edit_text(
        original_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔁 Share", callback_data="flink_share")],
            [InlineKeyboardButton("📺 View Channel", url="https://t.me/CodeFlix_Bots")]
        ])
    )
    await callback_query.answer()
