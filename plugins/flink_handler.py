#
# Copyright (C) 2025 by AnimeLord-Bots@Github, < https://github.com/AnimeLord-Bots >.
#
# This file is part of < https://github.com/AnimeLord-Bots/FileStore > project,
# and is released under the MIT License.
# Please see < https://github.com/AnimeLord-Bots/FileStore/blob/master/LICENSE >
#
# All rights reserved.
#

import asyncio
import re
import logging
from typing import Dict, Tuple
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from bot import Bot
from helper_func import encode, get_message_id, decode
from config import OWNER_ID
from database.database import db

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store user data for flink command
flink_user_data: Dict[int, Dict] = {}

@Bot.on_message(filters.private & filters.command('flink'))
async def flink_command(client: Client, message: Message):
    """Handle /flink command for formatted link generation."""
    try:
        admin_ids = await db.get_all_admins() or []
        if message.from_user.id not in admin_ids and message.from_user.id != OWNER_ID:
            await message.reply_text("❌ You are not authorized!")
            return

        # Reset user data
        flink_user_data[message.from_user.id] = {
            'step': 'format',
            'format_data': {},
            'channel_type': 'primary',
            'start_msg_id': None,
            'links': {},
            'caption': None,
            'image': None
        }
        
        await message.reply_text(
            "📋 **Formatted Link Generator**\n\n"
            "Send the format in this pattern:\n\n"
            "**Example:**\n"
            "`360p = 2, 720p = 2, 1080p = 2`\n\n"
            "**Meaning:**\n"
            "• 360p = 2 → 2 video files for 360p quality\n"
            "• If stickers/gifs follow, they will be included\n"
            "• Only these qualities will be created\n\n"
            "Send your format now:"
        )
        
    except Exception as e:
        logger.error(f"Error in flink_command: {e}")
        await message.reply_text("❌ An error occurred. Please try again.")

@Bot.on_message(filters.private & filters.text & ~filters.command(['start', 'flink', 'cancel']))
async def handle_flink_input(client: Client, message: Message):
    """Handle all flink command inputs."""
    try:
        user_id = message.from_user.id
        
        # Check if user is in flink process
        if user_id not in flink_user_data:
            return
        
        step = flink_user_data[user_id]['step']
        
        if step == 'format':
            await handle_format_input(client, message)
        elif step == 'channel':
            await handle_channel_input(client, message)
        elif step == 'post':
            await handle_post_input(client, message)
        elif step == 'caption':
            await handle_caption_input_step(client, message)
            
    except Exception as e:
        logger.error(f"Error in handle_flink_input: {e}")
        await message.reply_text("❌ An error occurred. Please try /flink again.")

async def handle_format_input(client: Client, message: Message):
    """Handle format input."""
    user_id = message.from_user.id
    
    # Validate format pattern
    format_text = message.text.strip()
    
    # Check format pattern: quality = count, quality = count, ...
    if not re.match(r'^[a-zA-Z0-9]+\s*=\s*\d+(\s*,\s*[a-zA-Z0-9]+\s*=\s*\d+)*$', format_text):
        await message.reply_text(
            "❌ Invalid format!\n\n"
            "Please use format: `360p = 2, 720p = 2, 1080p = 2`\n"
            "Try again:"
        )
        return
    
    # Parse format
    format_parts = [part.strip() for part in format_text.split(',')]
    format_data = {}
    
    for part in format_parts:
        if '=' in part:
            quality, count = part.split('=')
            quality = quality.strip().upper()
            count = int(count.strip())
            format_data[quality] = count
    
    if not format_data:
        await message.reply_text("❌ Could not parse format. Please try again.")
        return
    
    # Store format data
    flink_user_data[user_id]['format_data'] = format_data
    flink_user_data[user_id]['step'] = 'channel'
    
    # Show channel selection keyboard
    keyboard = []
    
    # Primary channel always available
    keyboard.append([InlineKeyboardButton("📌 Primary Channel", callback_data="flink_channel_primary")])
    
    # Secondary channel if available
    if client.secondary_channel:
        keyboard.append([InlineKeyboardButton("📂 Secondary Channel", callback_data="flink_channel_secondary")])
    
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="flink_cancel")])
    
    await message.reply_text(
        "✅ **Format saved successfully!**\n\n"
        f"Format: `{format_text}`\n\n"
        "Now select which channel to use:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@Bot.on_callback_query(filters.regex(r"^flink_channel_(primary|secondary)$"))
async def handle_channel_selection(client: Client, query: CallbackQuery):
    """Handle channel selection."""
    user_id = query.from_user.id
    
    if user_id not in flink_user_data:
        await query.answer("Session expired. Please use /flink again.")
        await query.message.delete()
        return
    
    channel_type = query.data.split('_')[2]  # primary or secondary
    
    # Check if secondary channel is selected but not available
    if channel_type == 'secondary' and not client.secondary_channel:
        await query.answer("❌ Secondary channel not configured!")
        return
    
    flink_user_data[user_id]['channel_type'] = channel_type
    flink_user_data[user_id]['step'] = 'post'
    
    target_channel = client.secondary_channel if channel_type == 'secondary' else client.db_channel
    
    await query.message.edit_text(
        f"✅ **{channel_type.capitalize()} Channel Selected**\n\n"
        f"Channel: {target_channel.title}\n\n"
        "Now forward the **first message** from this channel "
        "or send the direct link to the first post.\n\n"
        "**Important:** Files must be in sequence without gaps."
    )
    
    await query.answer()

async def handle_post_input(client: Client, message: Message):
    """Handle db channel post input."""
    user_id = message.from_user.id
    
    if user_id not in flink_user_data:
        return
    
    # Get message ID from forwarded message or link
    msg_id = await get_message_id(client, message)
    
    if not msg_id:
        await message.reply_text(
            "❌ Could not get message ID!\n"
            "Please forward a message from the DB channel "
            "or send a direct link to the post."
        )
        return
    
    # Validate channel
    channel_type = flink_user_data[user_id]['channel_type']
    target_channel = client.secondary_channel if channel_type == 'secondary' else client.db_channel
    
    if message.forward_from_chat:
        if channel_type == 'primary' and message.forward_from_chat.id != client.db_channel.id:
            await message.reply_text("❌ This message is not from the Primary DB Channel!")
            return
        elif channel_type == 'secondary' and message.forward_from_chat.id != client.secondary_channel.id:
            await message.reply_text("❌ This message is not from the Secondary DB Channel!")
            return
    
    # Store start message ID
    flink_user_data[user_id]['start_msg_id'] = msg_id
    
    # Process files
    await process_files(client, message)

async def process_files(client: Client, message: Message):
    """Process files and generate links."""
    user_id = message.from_user.id
    format_data = flink_user_data[user_id]['format_data']
    start_msg_id = flink_user_data[user_id]['start_msg_id']
    channel_type = flink_user_data[user_id]['channel_type']
    target_channel = client.secondary_channel if channel_type == 'secondary' else client.db_channel
    
    processing_msg = await message.reply_text("⏳ Processing files...")
    
    try:
        current_id = start_msg_id
        links = {}
        all_found = True
        
        for quality, count in format_data.items():
            valid_ids = []
            temp_id = current_id
            
            # Look for the required number of files
            while len(valid_ids) < count:
                try:
                    msg = await client.get_messages(target_channel.id, temp_id)
                    
                    # Check if it's a video or document
                    if msg and (msg.video or msg.document):
                        valid_ids.append(temp_id)
                    else:
                        # Not a video/document, skip it
                        pass
                        
                except Exception as e:
                    # Message not found or other error
                    logger.info(f"Message {temp_id} not found: {e}")
                
                temp_id += 1
                
                # Safety limit to prevent infinite loop
                if temp_id > current_id + (count * 10):
                    break
            
            if len(valid_ids) < count:
                await processing_msg.edit_text(
                    f"❌ Not enough files found for {quality}!\n"
                    f"Required: {count}, Found: {len(valid_ids)}\n"
                    f"Starting from ID: {current_id}"
                )
                all_found = False
                break
            
            # Get start and end IDs
            start_id = valid_ids[0]
            end_id = valid_ids[-1]
            
            # Check for stickers/gifs after the last file
            next_id = end_id + 1
            try:
                next_msg = await client.get_messages(target_channel.id, next_id)
                if next_msg and (next_msg.sticker or next_msg.animation):
                    end_id = next_id  # Include the sticker/gif
            except:
                pass
            
            links[quality] = {
                'start': start_id,
                'end': end_id,
                'count': count
            }
            
            # Move to next position (after the last file we processed)
            current_id = end_id + 1
        
        if not all_found:
            # Clean up
            if user_id in flink_user_data:
                del flink_user_data[user_id]
            return
        
        # Store links and move to next step
        flink_user_data[user_id]['links'] = links
        flink_user_data[user_id]['step'] = 'options'
        
        # Generate output
        await generate_output(client, message, processing_msg)
        
    except Exception as e:
        logger.error(f"Error in process_files: {e}")
        await processing_msg.edit_text(f"❌ Error processing files: {str(e)}")
        if user_id in flink_user_data:
            del flink_user_data[user_id]

async def generate_output(client: Client, message: Message, processing_msg: Message = None):
    """Generate the final output with buttons."""
    user_id = message.from_user.id
    
    if user_id not in flink_user_data:
        return
    
    links = flink_user_data[user_id]['links']
    channel_type = flink_user_data[user_id]['channel_type']
    target_channel = client.secondary_channel if channel_type == 'secondary' else client.db_channel
    
    # Create buttons
    buttons = []
    quality_list = list(links.keys())
    
    # Arrange buttons based on number of qualities
    if len(quality_list) == 1:
        quality = quality_list[0]
        button_url = await create_batch_link(client, links[quality], channel_type, target_channel)
        buttons.append([InlineKeyboardButton(f"📥 {quality}", url=button_url)])
    
    elif len(quality_list) == 2:
        for i in range(0, len(quality_list), 2):
            row = []
            for j in range(i, min(i+2, len(quality_list))):
                quality = quality_list[j]
                button_url = await create_batch_link(client, links[quality], channel_type, target_channel)
                row.append(InlineKeyboardButton(f"📥 {quality}", url=button_url))
            buttons.append(row)
    
    elif len(quality_list) == 3:
        # First row: 2 buttons
        row1 = []
        for i in range(2):
            quality = quality_list[i]
            button_url = await create_batch_link(client, links[quality], channel_type, target_channel)
            row1.append(InlineKeyboardButton(f"📥 {quality}", url=button_url))
        buttons.append(row1)
        
        # Second row: 1 button centered
        quality = quality_list[2]
        button_url = await create_batch_link(client, links[quality], channel_type, target_channel)
        buttons.append([InlineKeyboardButton(f"📥 {quality}", url=button_url)])
    
    elif len(quality_list) >= 4:
        # Create rows of 2 buttons each
        for i in range(0, len(quality_list), 2):
            row = []
            for j in range(i, min(i+2, len(quality_list))):
                quality = quality_list[j]
                button_url = await create_batch_link(client, links[quality], channel_type, target_channel)
                row.append(InlineKeyboardButton(f"📥 {quality}", url=button_url))
            buttons.append(row)
    
    # Add action buttons
    action_buttons = [
        [InlineKeyboardButton("🖼️ Add Image", callback_data="flink_add_image"),
         InlineKeyboardButton("📝 Add Caption", callback_data="flink_add_caption")],
        [InlineKeyboardButton("✅ Finish", callback_data="flink_finish"),
         InlineKeyboardButton("🔄 Regenerate", callback_data="flink_regenerate")]
    ]
    
    buttons.extend(action_buttons)
    
    # Create caption
    caption = flink_user_data[user_id].get('caption')
    if not caption:
        caption = f"**📦 Download Links**\n\nChannel: {target_channel.title}\n\n"
        for quality, data in links.items():
            caption += f"• {quality}: {data['count']} file(s)\n"
    
    # Send or edit message
    if processing_msg:
        await processing_msg.delete()
    
    if flink_user_data[user_id].get('image'):
        # Send as photo with caption
        sent_msg = await message.reply_photo(
            photo=flink_user_data[user_id]['image'],
            caption=caption,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        # Send as text message
        sent_msg = await message.reply_text(
            caption,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Store the message for later reference
    flink_user_data[user_id]['output_message'] = sent_msg

async def create_batch_link(client: Client, link_data: Dict, channel_type: str, target_channel) -> str:
    """Create a batch link for a range of message IDs."""
    # Multiply by channel ID (absolute value)
    channel_multiplier = abs(target_channel.id)
    start_converted = link_data['start'] * channel_multiplier
    end_converted = link_data['end'] * channel_multiplier
    
    # Create string based on channel type
    if channel_type == 'secondary':
        string = f"sec-get-{start_converted}-{end_converted}"
    else:
        string = f"get-{start_converted}-{end_converted}"
    
    # Encode to base64
    base64_string = await encode(string)
    
    # Return the bot link
    return f"https://t.me/{client.username}?start={base64_string}"

@Bot.on_callback_query(filters.regex(r"^flink_add_image$"))
async def handle_add_image(client: Client, query: CallbackQuery):
    """Handle add image callback."""
    user_id = query.from_user.id
    
    if user_id not in flink_user_data:
        await query.answer("Session expired!")
        return
    
    flink_user_data[user_id]['step'] = 'waiting_image'
    
    await query.message.edit_text(
        "🖼️ **Add Image**\n\n"
        "Please send the image you want to use.\n"
        "Reply to this message with the image."
    )
    
    await query.answer()

@Bot.on_callback_query(filters.regex(r"^flink_add_caption$"))
async def handle_add_caption(client: Client, query: CallbackQuery):
    """Handle add caption callback."""
    user_id = query.from_user.id
    
    if user_id not in flink_user_data:
        await query.answer("Session expired!")
        return
    
    flink_user_data[user_id]['step'] = 'caption'
    
    await query.message.edit_text(
        "📝 **Add Caption**\n\n"
        "Please send your caption text.\n"
        "You can use markdown formatting.\n\n"
        "**Example:**\n"
        "Title: Movie Name\n"
        "Quality: 360p, 720p, 1080p\n"
        "Click below to download!"
    )
    
    await query.answer()

async def handle_caption_input_step(client: Client, message: Message):
    """Handle caption input from user."""
    user_id = message.from_user.id
    
    if user_id not in flink_user_data:
        return
    
    # Store caption
    flink_user_data[user_id]['caption'] = message.text
    flink_user_data[user_id]['step'] = 'options'
    
    # Regenerate output with new caption
    await generate_output(client, message)
    
    await message.reply_text("✅ Caption added successfully!")

@Bot.on_message(filters.private & filters.photo)
async def handle_image_upload(client: Client, message: Message):
    """Handle image upload for flink."""
    user_id = message.from_user.id
    
    if user_id not in flink_user_data:
        return
    
    if flink_user_data[user_id].get('step') != 'waiting_image':
        return
    
    # Store image file ID
    flink_user_data[user_id]['image'] = message.photo.file_id
    flink_user_data[user_id]['step'] = 'options'
    
    # Regenerate output with image
    await generate_output(client, message)
    
    await message.reply_text("✅ Image added successfully!")

@Bot.on_callback_query(filters.regex(r"^flink_finish$"))
async def handle_finish(client: Client, query: CallbackQuery):
    """Handle finish callback."""
    user_id = query.from_user.id
    
    if user_id not in flink_user_data:
        await query.answer("Session expired!")
        return
    
    # Get data
    links = flink_user_data[user_id]['links']
    channel_type = flink_user_data[user_id]['channel_type']
    caption = flink_user_data[user_id].get('caption')
    image = flink_user_data[user_id].get('image')
    target_channel = client.secondary_channel if channel_type == 'secondary' else client.db_channel
    
    # Create final buttons (without edit options)
    buttons = []
    quality_list = list(links.keys())
    
    # Create download buttons only
    if len(quality_list) == 1:
        quality = quality_list[0]
        button_url = await create_batch_link(client, links[quality], channel_type, target_channel)
        buttons.append([InlineKeyboardButton(f"📥 {quality}", url=button_url)])
    
    elif len(quality_list) == 2:
        row = []
        for quality in quality_list:
            button_url = await create_batch_link(client, links[quality], channel_type, target_channel)
            row.append(InlineKeyboardButton(f"📥 {quality}", url=button_url))
        buttons.append(row)
    
    elif len(quality_list) == 3:
        # First row: 2 buttons
        row1 = []
        for i in range(2):
            quality = quality_list[i]
            button_url = await create_batch_link(client, links[quality], channel_type, target_channel)
            row1.append(InlineKeyboardButton(f"📥 {quality}", url=button_url))
        buttons.append(row1)
        
        # Second row: 1 button
        quality = quality_list[2]
        button_url = await create_batch_link(client, links[quality], channel_type, target_channel)
        buttons.append([InlineKeyboardButton(f"📥 {quality}", url=button_url)])
    
    elif len(quality_list) >= 4:
        for i in range(0, len(quality_list), 2):
            row = []
            for j in range(i, min(i+2, len(quality_list))):
                quality = quality_list[j]
                button_url = await create_batch_link(client, links[quality], channel_type, target_channel)
                row.append(InlineKeyboardButton(f"📥 {quality}", url=button_url))
            buttons.append(row)
    
    # Create default caption if none provided
    if not caption:
        caption = f"**📦 Download Links**\n\nChannel: {target_channel.title}\n\n"
        for quality, data in links.items():
            caption += f"• {quality}: {data['count']} file(s)\n"
    
    # Send final message
    if image:
        await query.message.reply_photo(
            photo=image,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await query.message.reply_text(
            caption,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Clean up
    del flink_user_data[user_id]
    
    await query.answer("✅ Process completed!")
    await query.message.delete()

@Bot.on_callback_query(filters.regex(r"^flink_regenerate$"))
async def handle_regenerate(client: Client, query: CallbackQuery):
    """Handle regenerate callback."""
    user_id = query.from_user.id
    
    if user_id not in flink_user_data:
        await query.answer("Session expired!")
        return
    
    # Reset to format step
    flink_user_data[user_id]['step'] = 'format'
    flink_user_data[user_id]['caption'] = None
    flink_user_data[user_id]['image'] = None
    
    # Get existing format
    format_data = flink_user_data[user_id]['format_data']
    format_text = ", ".join([f"{k} = {v}" for k, v in format_data.items()])
    
    await query.message.edit_text(
        "🔄 **Regenerating Links**\n\n"
        f"Current format: `{format_text}`\n\n"
        "Forward the **first message** again or send the link:"
    )
    
    await query.answer()

@Bot.on_callback_query(filters.regex(r"^flink_cancel$"))
async def handle_cancel(client: Client, query: CallbackQuery):
    """Handle cancel callback."""
    user_id = query.from_user.id
    
    if user_id in flink_user_data:
        del flink_user_data[user_id]
    
    await query.message.edit_text("❌ Process cancelled.")
    await query.answer()

@Bot.on_message(filters.private & filters.command('cancel'))
async def handle_cancel_command(client: Client, message: Message):
    """Handle cancel command."""
    user_id = message.from_user.id
    
    if user_id in flink_user_data:
        del flink_user_data[user_id]
        await message.reply_text("✅ Flink process cancelled.")
    else:
        await message.reply_text("No active flink process to cancel.")

# Helper function to test link format
async def test_link_format(client: Client, start_id: int, end_id: int, channel_type: str, target_channel) -> str:
    """Test function to verify link format."""
    channel_multiplier = abs(target_channel.id)
    start_converted = start_id * channel_multiplier
    end_converted = end_id * channel_multiplier
    
    if channel_type == 'secondary':
        string = f"sec-get-{start_converted}-{end_converted}"
    else:
        string = f"get-{start_converted}-{end_converted}"
    
    # Decode to verify
    try:
        base64_string = await encode(string)
        decoded = await decode(base64_string)
        
        logger.info(f"Test Link Debug:")
        logger.info(f"  Raw IDs: {start_id} to {end_id}")
        logger.info(f"  Channel multiplier: {channel_multiplier}")
        logger.info(f"  Converted IDs: {start_converted} to {end_converted}")
        logger.info(f"  String: {string}")
        logger.info(f"  Base64: {base64_string}")
        logger.info(f"  Decoded: {decoded}")
        logger.info(f"  Match: {string == decoded}")
        
        return f"https://t.me/{client.username}?start={base64_string}"
    except Exception as e:
        logger.error(f"Test link error: {e}")
        return None

#
# Copyright (C) 2025 by AnimeLord-Bots@Github, < https://github.com/AnimeLord-Bots >.
#
# This file is part of < https://github.com/AnimeLord-Bots/FileStore > project,
# and is released under the MIT License.
# Please see < https://github.com/AnimeLord-Bots/FileStore/blob/master/LICENSE >
#
# All rights reserved.
#
