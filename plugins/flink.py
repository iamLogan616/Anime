# (©)Codeflix_Bots
# @rohit_1888 on Telegram

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from bot import Bot
from helper_func import encode, get_message_id, admin, get_messages
from config import PERMANENT_LINKS, BLOGSPOT_URL, BLOGSPOT_PARAM
from database.database import db

# Store format settings per user
user_formats = {}

def generate_link(base64_string, client):
    """Generate link based on configuration"""
    if PERMANENT_LINKS and BLOGSPOT_URL:
        return f"{BLOGSPOT_URL}?{BLOGSPOT_PARAM}={base64_string}"
    else:
        return f"https://t.me/{client.username}?start={base64_string}"

@Bot.on_message(filters.private & admin & filters.command('flink'))
async def flink_command(client: Client, message: Message):
    """Formatted link generation command"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("• sᴇᴛ ғᴏʀᴍᴀᴛ •", callback_data="set_format")],
        [InlineKeyboardButton("• sᴛᴀʀᴛ •", callback_data="start_format_link")],
        [InlineKeyboardButton("• ᴄᴀɴᴄᴇʟ •", callback_data="cancel_format")]
    ])
    
    await message.reply_text(
        "**📁 Formatted Link Generator**\n\n"
        "1. **Set Format** - Configure quality settings\n"
        "2. **Start** - Begin link generation process\n"
        "3. **Cancel** - Cancel current operation\n\n"
        "**Note:** Files must be in sequence without deletions between them.",
        reply_markup=keyboard
    )

@Bot.on_callback_query(filters.regex("^set_format$"))
async def set_format_callback(client: Client, callback_query: CallbackQuery):
    """Set format for formatted links"""
    user_id = callback_query.from_user.id
    
    # Initialize format for user
    if user_id not in user_formats:
        user_formats[user_id] = {
            "360P": 0,
            "480P": 0, 
            "720P": 0,
            "1080P": 0,
            "HDRIP": 0,
            "4K": 0,
            "channel_type": "primary"
        }
    
    await callback_query.message.edit_text(
        "**📝 Set Format Configuration**\n\n"
        "**Current Format:**\n"
        f"360P = {user_formats[user_id]['360P']}\n"
        f"480P = {user_formats[user_id]['480P']}\n"
        f"720P = {user_formats[user_id]['720P']}\n"
        f"1080P = {user_formats[user_id]['1080P']}\n"
        f"HDRIP = {user_formats[user_id]['HDRIP']}\n"
        f"4K = {user_formats[user_id]['4K']}\n"
        f"Channel: {user_formats[user_id]['channel_type'].upper()}\n\n"
        "**How to set format:**\n"
        "Send format in this pattern:\n"
        "`360P=2 480P=2 720P=2 1080P=2 HDRIP=1 4K=1`\n\n"
        "**Examples:**\n"
        "• `480P=1 720P=1 1080P=1`\n"
        "• `360P=2 HDRIP=1`\n"
        "• `720P=3 1080P=2 4K=1`\n\n"
        "**Reply with your format or type CANCEL to abort.**",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Wait for user input
    try:
        response = await client.listen(
            chat_id=callback_query.message.chat.id,
            filters=filters.text & filters.user(user_id),
            timeout=60
        )
        
        if response.text.upper() == "CANCEL":
            await response.reply("❌ Format setting cancelled.")
            return
        
        # Parse format string
        format_text = response.text.upper()
        formats = format_text.split()
        
        # Reset all formats
        user_formats[user_id].update({
            "360P": 0, "480P": 0, "720P": 0, 
            "1080P": 0, "HDRIP": 0, "4K": 0
        })
        
        for fmt in formats:
            if '=' in fmt:
                try:
                    quality, count = fmt.split('=')
                    quality = quality.strip()
                    count = int(count.strip())
                    
                    if quality in user_formats[user_id]:
                        user_formats[user_id][quality] = count
                except:
                    pass
        
        # Ask for channel type if secondary channel exists
        if client.secondary_channel:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📌 Primary Channel", callback_data="set_primary")],
                [InlineKeyboardButton("📂 Secondary Channel", callback_data="set_secondary")]
            ])
            
            await response.reply(
                "**Select Channel Type:**",
                reply_markup=keyboard
            )
        else:
            user_formats[user_id]['channel_type'] = 'primary'
            await response.reply(
                "✅ **Format Set Successfully!**\n\n"
                f"**Current Format:**\n"
                f"360P = {user_formats[user_id]['360P']}\n"
                f"480P = {user_formats[user_id]['480P']}\n" 
                f"720P = {user_formats[user_id]['720P']}\n"
                f"1080P = {user_formats[user_id]['1080P']}\n"
                f"HDRIP = {user_formats[user_id]['HDRIP']}\n"
                f"4K = {user_formats[user_id]['4K']}\n"
                f"Channel: {user_formats[user_id]['channel_type'].upper()}\n\n"
                "Click **• sᴛᴀʀᴛ •** to begin link generation.",
                parse_mode=ParseMode.MARKDOWN
            )
            
    except asyncio.TimeoutError:
        await callback_query.message.reply("⏰ Timeout! Format setting cancelled.")

@Bot.on_callback_query(filters.regex("^set_(primary|secondary)$"))
async def set_channel_callback(client: Client, callback_query: CallbackQuery):
    """Set channel type for formatted links"""
    user_id = callback_query.from_user.id
    channel_type = callback_query.data.split('_')[1]
    
    if user_id in user_formats:
        user_formats[user_id]['channel_type'] = channel_type
        
        await callback_query.message.edit_text(
            "✅ **Format Set Successfully!**\n\n"
            f"**Current Format:**\n"
            f"360P = {user_formats[user_id]['360P']}\n"
            f"480P = {user_formats[user_id]['480P']}\n" 
            f"720P = {user_formats[user_id]['720P']}\n"
            f"1080P = {user_formats[user_id]['1080P']}\n"
            f"HDRIP = {user_formats[user_id]['HDRIP']}\n"
            f"4K = {user_formats[user_id]['4K']}\n"
            f"Channel: {user_formats[user_id]['channel_type'].upper()}\n\n"
            "Click **• sᴛᴀʀᴛ •** to begin link generation.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    await callback_query.answer()

@Bot.on_callback_query(filters.regex("^start_format_link$"))
async def start_format_link(client: Client, callback_query: CallbackQuery):
    """Start formatted link generation process"""
    user_id = callback_query.from_user.id
    
    if user_id not in user_formats or sum(user_formats[user_id].values()) == 0:
        await callback_query.answer("❌ Please set format first!", show_alert=True)
        return
    
    await callback_query.message.edit_text(
        "**📤 Starting Formatted Link Generation**\n\n"
        "**Current Format:**\n"
        f"360P = {user_formats[user_id]['360P']}\n"
        f"480P = {user_formats[user_id]['480P']}\n" 
        f"720P = {user_formats[user_id]['720P']}\n"
        f"1080P = {user_formats[user_id]['1080P']}\n"
        f"HDRIP = {user_formats[user_id]['HDRIP']}\n"
        f"4K = {user_formats[user_id]['4K']}\n\n"
        f"**Total Files:** {sum(user_formats[user_id].values())}\n"
        f"**Channel:** {user_formats[user_id]['channel_type'].upper()}\n\n"
        "**Please send the first post link or forward the first message from the database channel.**\n"
        "Type **CANCEL** to abort.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        # Get first message
        first_msg = await client.listen(
            chat_id=callback_query.message.chat.id,
            filters=filters.text & filters.user(user_id),
            timeout=60
        )
        
        if first_msg.text.upper() == "CANCEL":
            await first_msg.reply("❌ Link generation cancelled.")
            return
        
        # Determine target channel
        channel_type = user_formats[user_id]['channel_type']
        target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel
        
        if not target_channel:
            await first_msg.reply("❌ Target channel not available!")
            return
        
        # Get message ID
        msg_id = await get_message_id(client, first_msg)
        if not msg_id:
            await first_msg.reply("❌ Could not get message ID. Please send a valid link or forward.")
            return
        
        # Check if from correct channel
        if first_msg.forward_from_chat:
            expected_id = client.secondary_channel.id if channel_type == "secondary" else client.db_channel.id
            if first_msg.forward_from_chat.id != expected_id:
                await first_msg.reply(f"❌ Message is not from {channel_type} channel!")
                return
        
        await first_msg.reply("✅ First message received. Generating links...")
        
        # Calculate total files needed
        total_files = sum([
            user_formats[user_id]['360P'],
            user_formats[user_id]['480P'],
            user_formats[user_id]['720P'],
            user_formats[user_id]['1080P'],
            user_formats[user_id]['HDRIP'],
            user_formats[user_id]['4K']
        ])
        
        # Generate message IDs
        channel_multiplier = abs(target_channel.id)
        start_id = msg_id
        end_id = msg_id + total_files - 1
        message_ids = list(range(start_id, end_id + 1))
        
        # Fetch all messages
        messages = await get_messages(client, message_ids, channel=channel_type)
        
        if len(messages) != total_files:
            await first_msg.reply(f"❌ Error: Expected {total_files} files, found {len(messages)}. Make sure files are in sequence.")
            return
        
        # Create individual links for each quality
        quality_links = {}
        current_index = 0
        
        for quality in ['360P', '480P', '720P', '1080P', 'HDRIP', '4K']:
            count = user_formats[user_id][quality]
            if count > 0:
                # Get message IDs for this quality
                quality_ids = message_ids[current_index:current_index + count]
                
                if len(quality_ids) == 1:
                    # Single file link
                    string = f"get-{quality_ids[0] * channel_multiplier}"
                else:
                    # Batch link
                    string = f"get-{quality_ids[0] * channel_multiplier}-{quality_ids[-1] * channel_multiplier}"
                
                # Add prefix for secondary channel
                if channel_type == "secondary":
                    string = f"sec-{string}"
                
                base64_string = await encode(string)
                link = generate_link(base64_string, client)
                quality_links[quality] = link
                
                current_index += count
        
        # Create formatted message with buttons
        buttons = []
        for quality, link in quality_links.items():
            buttons.append([InlineKeyboardButton(f"📥 {quality}", url=link)])
        
        # Add share button
        if len(quality_links) > 1:
            # Create a master link for all files
            master_string = f"get-{start_id * channel_multiplier}-{end_id * channel_multiplier}"
            if channel_type == "secondary":
                master_string = f"sec-{master_string}"
            master_base64 = await encode(master_string)
            master_link = generate_link(master_base64, client)
            buttons.append([InlineKeyboardButton("📦 ALL FILES", url=master_link)])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        
        # Create final message
        format_details = "\n".join([f"• {quality}: {count} file(s)" for quality, count in [
            ('360P', user_formats[user_id]['360P']),
            ('480P', user_formats[user_id]['480P']),
            ('720P', user_formats[user_id]['720P']),
            ('1080P', user_formats[user_id]['1080P']),
            ('HDRIP', user_formats[user_id]['HDRIP']),
            ('4K', user_formats[user_id]['4K'])
        ] if count > 0])
        
        await first_msg.reply_text(
            f"✅ **Formatted Links Generated Successfully!**\n\n"
            f"**Format Details:**\n{format_details}\n\n"
            f"**Channel:** {channel_type.upper()}\n"
            f"**Total Files:** {total_files}\n"
            f"**Message Range:** {start_id} to {end_id}\n\n"
            f"**Click the buttons below to download:**\n"
            f"_(Note: These are bot URLs, not permanent links)_",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Clear user format after completion
        if user_id in user_formats:
            del user_formats[user_id]
            
    except asyncio.TimeoutError:
        await callback_query.message.reply("⏰ Timeout! Link generation cancelled.")
    except Exception as e:
        await callback_query.message.reply(f"❌ Error: {str(e)}")

@Bot.on_callback_query(filters.regex("^cancel_format$"))
async def cancel_format_callback(client: Client, callback_query: CallbackQuery):
    """Cancel formatted link generation"""
    user_id = callback_query.from_user.id
    
    # Clear user format
    if user_id in user_formats:
        del user_formats[user_id]
    
    await callback_query.message.edit_text("❌ Formatted link generation cancelled.")
    await callback_query.answer()
