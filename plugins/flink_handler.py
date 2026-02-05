#
# Copyright (C) 2025 by AnimeLord-Bots@Github, < https://github.com/AnimeLord-Bots >.
#
# This file is part of < https://github.com/AnimeLord-Bots/FileStore > project,
# and is released under the MIT License.
# Please see < https://github.com/AnimeLord-Bots/FileStore/blob/master/LICENSE >
#
# All rights reserved.
#

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from bot import Bot
from helper_func import encode, get_message_id
from config import OWNER_ID
from database.database import db
import re
import logging
from typing import Dict

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store user data for flink command
flink_user_data: Dict[int, Dict] = {}

# Filter for flink db post input
async def flink_db_post_filter(_, __, message: Message):
    user_id = message.from_user.id
    if user_id not in flink_user_data:
        logger.info(f"flink_db_post_filter: No flink data for user {user_id}")
        return False
    state = flink_user_data[user_id].get('awaiting_db_post')
    logger.info(f"flink_db_post_filter for user {user_id}: awaiting_db_post={state}, message_text={message.text}")
    return state and (message.forward_from_chat or re.match(r"^https?://t\.me/.*$", message.text))

@Bot.on_message(filters.private & filters.command('flink'))
async def flink_command(client: Client, message: Message):
    """Handle /flink command for formatted link generation."""
    logger.info(f"flink command triggered by user {message.from_user.id}")
    try:
        admin_ids = await db.get_all_admins() or []
        if message.from_user.id not in admin_ids and message.from_user.id != OWNER_ID:
            await message.reply_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ You are not authorized!</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)
            return

        flink_user_data[message.from_user.id] = {
            'format': None,
            'links': {},
            'edit_data': {},
            'menu_message': None,
            'output_message': None,
            'caption_prompt_message': None,
            'awaiting_format': False,
            'awaiting_caption': False,
            'awaiting_db_post': False,
            'channel_type': 'primary'  # Default to primary channel
        }
        
        await show_flink_main_menu(client, message)
    except Exception as e:
        logger.error(f"error in flink_command: {e}")
        await message.reply_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ An error occurred. Please try again.</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)

async def show_flink_main_menu(client: Client, message: Message, edit: bool = False):
    """Show the main menu for the flink command."""
    try:
        current_format = flink_user_data[message.from_user.id]['format'] or "Not set"
        current_channel = flink_user_data[message.from_user.id]['channel_type'].capitalize()
        text = f"""<b>━━━━━━━━━━━━━━━━━━</b>
<b>Formatted Link Generator</b>

<blockquote><b>Current format:</b></blockquote>
<blockquote><code>{current_format}</code></blockquote>

<blockquote><b>Channel:</b> {current_channel}</blockquote>
<b>━━━━━━━━━━━━━━━━━━</b>"""
        
        buttons = [
            [
                InlineKeyboardButton("• sᴇᴛ ғᴏʀᴍᴀᴛ •", callback_data="flink_set_format"),
                InlineKeyboardButton("• ᴄʜᴀɴɴᴇʟ •", callback_data="flink_select_channel")
            ],
            [
                InlineKeyboardButton("• sᴛᴀʀᴛ ᴘʀᴏᴄᴇss •", callback_data="flink_start_process")
            ],
            [
                InlineKeyboardButton("• ʀᴇғʀᴇsʜ •", callback_data="flink_refresh"),
                InlineKeyboardButton("• ᴄʟᴏsᴇ •", callback_data="flink_close")
            ]
        ]
        
        if edit:
            msg = await message.edit_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.HTML
            )
            flink_user_data[message.from_user.id]['menu_message'] = msg
        else:
            msg = await message.reply(
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.HTML
            )
            flink_user_data[message.from_user.id]['menu_message'] = msg
    except Exception as e:
        logger.error(f"error in show_flink_main_menu: {e}")
        await message.reply_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ An error occurred while showing menu.</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)

@Bot.on_callback_query(filters.regex(r"^flink_set_format$"))
async def flink_set_format_callback(client: Client, query: CallbackQuery):
    """Handle callback for setting format in flink command."""
    logger.info(f"flink_set_format callback triggered by user {query.from_user.id}")
    try:
        admin_ids = await db.get_all_admins() or []
        if query.from_user.id not in admin_ids and query.from_user.id != OWNER_ID:
            await query.answer("You are not authorized!", show_alert=True)
            return

        flink_user_data[query.from_user.id]['awaiting_format'] = True
        await query.message.edit_text(
            text="<b>━━━━━━━━━━━━━━━━━━</b>\n"
                 "<blockquote><b>Please send your format in this pattern:</b></blockquote>\n\n"
                 "<blockquote>Example</blockquote>:\n\n"
                 "<blockquote>don't copy this. please type</blockquote>:\n"
                 "<blockquote><code>360p = 2, 720p = 2, 1080p = 2, 4k = 2, HDRIP = 2</code></blockquote>\n\n"
                 "<blockquote><b>Meaning:</b></blockquote>\n"
                 "<b>- 360p = 2 → 2 video files for 360p quality</b>\n"
                 "<blockquote><b>- If stickers/gifs follow, they will be included in the link\n"
                 "- Only these qualities will be created</b></blockquote>\n\n"
                 "<b>Send the format in the next message (no need to reply).</b>\n"
                 "<b>━━━━━━━━━━━━━━━━━━</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="flink_back_to_menu")]
            ]),
            parse_mode=ParseMode.HTML
        )
        await query.answer("Enter format")
    except Exception as e:
        logger.error(f"error in flink_set_format_callback: {e}")
        await query.message.edit_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ An error occurred while setting format.</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)

@Bot.on_message(filters.private & filters.text & filters.regex(r"^[a-zA-Z0-9]+\s*=\s*\d+(,\s*[a-zA-Z0-9]+\s*=\s*\d+)*$"))
async def handle_format_input(client: Client, message: Message):
    """Handle format input for flink command."""
    logger.info(f"format input received from user {message.from_user.id}")
    try:
        admin_ids = await db.get_all_admins() or []
        if message.from_user.id not in admin_ids and message.from_user.id != OWNER_ID:
            await message.reply_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ You are not authorized!</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)
            return

        user_id = message.from_user.id
        if user_id in flink_user_data and flink_user_data[user_id].get('awaiting_format'):
            format_text = message.text.strip()
            flink_user_data[user_id]['format'] = format_text
            flink_user_data[user_id]['awaiting_format'] = False
            await message.reply_text(f"<b>━━━━━━━━━━━━━━━━━━</b>\n<blockquote><b>✅ Format saved successfully:</b></blockquote>\n<code>{format_text}</code>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)
            await show_flink_main_menu(client, message)
        else:
            logger.info(f"format input ignored for user {message.from_user.id} - not awaiting format")
            await message.reply_text(
                "<b>━━━━━━━━━━━━━━━━━━</b>\n<blockquote><b>❌ Please use the 'Set Format' option first and provide a valid format</b></blockquote>\n<blockquote>Example:</blockquote> <code>360p = 2, 720p = 1</code>\n<b>━━━━━━━━━━━━━━━━━━</b>",
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        logger.error(f"error in handle_format_input: {e}")
        await message.reply_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ An error occurred while processing format.</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)

@Bot.on_callback_query(filters.regex(r"^flink_select_channel$"))
async def flink_select_channel_callback(client: Client, query: CallbackQuery):
    """Handle callback for selecting channel type."""
    logger.info(f"flink_select_channel callback triggered by user {query.from_user.id}")
    try:
        admin_ids = await db.get_all_admins() or []
        if query.from_user.id not in admin_ids and query.from_user.id != OWNER_ID:
            await query.answer("You are not authorized!", show_alert=True)
            return

        # Create buttons for channel selection
        buttons = []
        
        # Always include primary channel
        buttons.append([InlineKeyboardButton("📌 Primary Channel", callback_data="flink_channel_primary")])
        
        # Include secondary channel only if available
        if client.secondary_channel:
            buttons.append([InlineKeyboardButton("📂 Secondary Channel", callback_data="flink_channel_secondary")])
        
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="flink_back_to_menu")])
        
        await query.message.edit_text(
            text="<b>━━━━━━━━━━━━━━━━━━</b>\n"
                 "<blockquote><b>Select channel for flink generation:</b></blockquote>\n\n"
                 f"<b>Primary:</b> {client.db_channel.title}\n"
                 f"<b>Secondary:</b> {client.secondary_channel.title if client.secondary_channel else 'Not configured'}\n"
                 "<b>━━━━━━━━━━━━━━━━━━</b>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        await query.answer("Select channel")
    except Exception as e:
        logger.error(f"error in flink_select_channel_callback: {e}")
        await query.message.edit_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ An error occurred while selecting channel.</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)

@Bot.on_callback_query(filters.regex(r"^flink_channel_(primary|secondary)$"))
async def flink_set_channel_callback(client: Client, query: CallbackQuery):
    """Handle callback for setting channel type."""
    logger.info(f"flink_set_channel callback triggered by user {query.from_user.id}")
    try:
        admin_ids = await db.get_all_admins() or []
        if query.from_user.id not in admin_ids and query.from_user.id != OWNER_ID:
            await query.answer("You are not authorized!", show_alert=True)
            return

        channel_type = query.data.split("_")[2]  # primary or secondary
        
        # Check if secondary channel is selected but not available
        if channel_type == "secondary" and not client.secondary_channel:
            await query.answer("❌ Secondary channel not configured!", show_alert=True)
            return
        
        flink_user_data[query.from_user.id]['channel_type'] = channel_type
        await show_flink_main_menu(client, query.message, edit=True)
        await query.answer(f"Channel set to {channel_type.capitalize()}")
    except Exception as e:
        logger.error(f"error in flink_set_channel_callback: {e}")
        await query.message.edit_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ An error occurred while setting channel.</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)

@Bot.on_callback_query(filters.regex(r"^flink_start_process$"))
async def flink_start_process_callback(client: Client, query: CallbackQuery):
    """Handle callback to start the flink process."""
    logger.info(f"flink_start_process callback triggered by user {query.from_user.id}")
    try:
        admin_ids = await db.get_all_admins() or []
        if query.from_user.id not in admin_ids and query.from_user.id != OWNER_ID:
            await query.answer("You are not authorized!", show_alert=True)
            return

        if not flink_user_data[query.from_user.id]['format']:
            await query.answer("❌ Please set format first!", show_alert=True)
            return
        
        channel_type = flink_user_data[query.from_user.id]['channel_type']
        if channel_type == "secondary" and not client.secondary_channel:
            await query.answer("❌ Secondary channel not configured!", show_alert=True)
            return
        
        flink_user_data[query.from_user.id]['awaiting_db_post'] = True
        
        # Get the target channel for display
        target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel
        
        await query.message.edit_text(
            text=f"<b>━━━━━━━━━━━━━━━━━━</b>\n"
                 f"<blockquote><b>Send the first post link from {channel_type.capitalize()} DB Channel:</b></blockquote>\n"
                 f"<blockquote><b>Forward a message from the {channel_type} channel or send its direct link (e.g., <code>t.me/channel/123</code>).</b></blockquote>\n\n"
                 f"<blockquote><b>Channel:</b> {target_channel.title}</blockquote>\n"
                 f"<blockquote><b>Ensure files are in sequence without gaps.</b></blockquote>\n\n"
                 f"<b>Send the link or forwarded message in the next message (no need to reply).</b>\n"
                 f"<b>━━━━━━━━━━━━━━━━━━</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✖️ Cancel", callback_data="flink_cancel_process")]
            ]),
            parse_mode=ParseMode.HTML
        )
        await query.answer(f"Send {channel_type} channel post")
    except Exception as e:
        logger.error(f"error in flink_start_process_callback: {e}")
        await query.message.edit_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ An error occurred while starting process.</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)

@Bot.on_message(filters.private & filters.create(flink_db_post_filter))
async def handle_db_post_input(client: Client, message: Message):
    """Handle db channel post input for flink command."""
    logger.info(f"db post input received from user {message.from_user.id}")
    try:
        admin_ids = await db.get_all_admins() or []
        if message.from_user.id not in admin_ids and message.from_user.id != OWNER_ID:
            await message.reply_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ You are not authorized!</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)
            return

        user_id = message.from_user.id
        if user_id not in flink_user_data or not flink_user_data[user_id].get('awaiting_db_post'):
            logger.info(f"db post input ignored for user {user_id} - not awaiting db channel input")
            await message.reply_text(
                "<b>━━━━━━━━━━━━━━━━━━</b>\n<blockquote><b>❌ Please use the 'Start Process' option first and provide a valid forwarded message or link from the db channel.</b></blockquote>\n<b>━━━━━━━━━━━━━━━━━━</b>",
                parse_mode=ParseMode.HTML
            )
            return

        # Get channel type
        channel_type = flink_user_data[user_id]['channel_type']
        target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel
        
        # Check if the forwarded message is from the correct channel
        if message.forward_from_chat:
            if channel_type == "primary" and message.forward_from_chat.id != client.db_channel.id:
                await message.reply(f"<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ This message is not from Primary DB Channel!</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)
                return
            elif channel_type == "secondary" and message.forward_from_chat.id != client.secondary_channel.id:
                await message.reply(f"<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ This message is not from Secondary DB Channel!</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)
                return

        msg_id = await get_message_id(client, message)
        if not msg_id:
            await message.reply("<b>━━━━━━━━━━━━━━━━━━</b>\n<blockquote><b>❌ Invalid db channel post! Ensure it's a valid forwarded message or link from the db channel.</b></blockquote>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)
            return
                
        format_str = flink_user_data[message.from_user.id]['format']
        format_parts = [part.strip() for part in format_str.split(",")]
        
        current_id = msg_id
        links = {}
        
        for part in format_parts:
            match = re.match(r"([a-zA-Z0-9]+)\s*=\s*(\d+)", part)
            if not match:
                await message.reply(f"<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ Invalid format part:</b> <code>{part}</code>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)
                return
            quality, count = match.groups()
            quality = quality.strip().upper()
            count = int(count.strip())
            
            valid_ids = []
            missing_files = []
            temp_id = current_id
            
            # Collect valid message IDs, skipping missing ones
            while len(valid_ids) < count and temp_id <= current_id + count * 2:  # Limit search to avoid infinite loops
                try:
                    msg = await client.get_messages(target_channel.id, temp_id)
                    if msg.video or msg.document:
                        valid_ids.append(temp_id)
                    else:
                        missing_files.append(temp_id)
                except Exception as e:
                    logger.info(f"message {temp_id} not found or invalid: {e}")
                    missing_files.append(temp_id)
                temp_id += 1
            
            if len(valid_ids) < count:
                logger.error(f"not enough valid media files for {quality}: found {len(valid_ids)}, required {count}")
                await message.reply(
                    f"<b>━━━━━━━━━━━━━━━━━━</b>\n<blockquote><b>❌ Not enough valid media files for {quality}. Found {len(valid_ids)} files, but {count} required.</b></blockquote>\n<b>━━━━━━━━━━━━━━━━━━</b>",
                    parse_mode=ParseMode.HTML
                )
                return
            
            start_id = valid_ids[0]
            end_id = valid_ids[count - 1]
            
            additional_count = 0
            next_id = end_id + 1
            try:
                next_msg = await client.get_messages(target_channel.id, next_id)
                if next_msg.sticker or next_msg.animation:
                    additional_count = 1
                    end_id = next_id
            except Exception as e:
                logger.info(f"no additional sticker/gif found at id {next_id}: {e}")
            
            links[quality] = {
                'start': start_id,
                'end': end_id,
                'count': count + additional_count
            }
            
            current_id = end_id + 1
            if missing_files:
                logger.info(f"skipped missing files for {quality}: {missing_files}")
            
            logger.info(f"processed {quality}: start={links[quality]['start']}, end={links[quality]['end']}, total files={links[quality]['count']}")
        
        flink_user_data[message.from_user.id]['links'] = links
        flink_user_data[message.from_user.id]['awaiting_db_post'] = False
        await flink_generate_final_output(client, message)
    except Exception as e:
        logger.error(f"error in handle_db_post_input: {e}")
        await message.reply_text(f"<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ Error: {str(e)}</b>\nPlease ensure the input is valid and try again.\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)

async def flink_generate_final_output(client: Client, message: Message):
    """Generate the final output for flink Mest with download buttons."""
    logger.info(f"generating final output for user {message.from_user.id}")
    try:
        user_id = message.from_user.id
        links = flink_user_data[user_id]['links']
        channel_type = flink_user_data[user_id]['channel_type']
        target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel
        
        if not links:
            logger.error("no links generated in flink_user_data")
            await message.reply_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ No links generated. Please check the input and try again.</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)
            return
        
        # Debug: Show what links we have
        logger.info(f"Generated links: {links}")
        logger.info(f"Channel type: {channel_type}")
        logger.info(f"Target channel ID: {target_channel.id}")
        
        buttons = []
        quality_list = list(links.keys())
        num_qualities = len(quality_list)
        
        # Test each link before creating buttons
        test_links = []
        for quality in quality_list:
            link_url = await create_link(client, links[quality], channel_type, target_channel)
            test_links.append((quality, link_url))
            logger.info(f"Generated link for {quality}: {link_url}")
        
        # Create buttons based on number of qualities
        if num_qualities == 2:
            buttons.append([
                InlineKeyboardButton(f"🦋 {quality_list[0]} 🦋", url=await create_link(client, links[quality_list[0]], channel_type, target_channel)),
                InlineKeyboardButton(f"🦋 {quality_list[1]} 🦋", url=await create_link(client, links[quality_list[1]], channel_type, target_channel))
            ])
        elif num_qualities == 3:
            buttons.append([
                InlineKeyboardButton(f"🦋 {quality_list[0]} 🦋", url=await create_link(client, links[quality_list[0]], channel_type, target_channel)),
                InlineKeyboardButton(f"🦋 {quality_list[1]} 🦋", url=await create_link(client, links[quality_list[1]], channel_type, target_channel))
            ])
            buttons.append([
                InlineKeyboardButton(f"🦋 {quality_list[2]} 🦋", url=await create_link(client, links[quality_list[2]], channel_type, target_channel))
            ])
        elif num_qualities == 4:
            buttons.append([
                InlineKeyboardButton(f"🦋 {quality_list[0]} 🦋", url=await create_link(client, links[quality_list[0]], channel_type, target_channel)),
                InlineKeyboardButton(f"🦋 {quality_list[1]} 🦋", url=await create_link(client, links[quality_list[1]], channel_type, target_channel))
            ])
            buttons.append([
                InlineKeyboardButton(f"🦋 {quality_list[2]} 🦋", url=await create_link(client, links[quality_list[2]], channel_type, target_channel)),
                InlineKeyboardButton(f"🦋 {quality_list[3]} 🦋", url=await create_link(client, links[quality_list[3]], channel_type, target_channel))
            ])
        elif num_qualities == 5:
            buttons.append([
                InlineKeyboardButton(f"🦋 {quality_list[0]} 🦋", url=await create_link(client, links[quality_list[0]], channel_type, target_channel)),
                InlineKeyboardButton(f"🦋 {quality_list[1]} 🦋", url=await create_link(client, links[quality_list[1]], channel_type, target_channel))
            ])
            buttons.append([
                InlineKeyboardButton(f"🦋 {quality_list[2]} 🦋", url=await create_link(client, links[quality_list[2]], channel_type, target_channel)),
                InlineKeyboardButton(f"🦋 {quality_list[3]} 🦋", url=await create_link(client, links[quality_list[3]], channel_type, target_channel))
            ])
            buttons.append([
                InlineKeyboardButton(f"🦋 {quality_list[4]} 🦋", url=await create_link(client, links[quality_list[4]], channel_type, target_channel))
            ])
        else:
            for quality in quality_list:
                buttons.append([
                    InlineKeyboardButton(f"🦋 {quality} 🦋", url=await create_link(client, links[quality], channel_type, target_channel))
                ])
        
        buttons.append([
            InlineKeyboardButton("◈ Edit ◈", callback_data="flink_edit_output"),
            InlineKeyboardButton("✅ Done", callback_data="flink_done_output")
        ])
        
        edit_data = flink_user_data[user_id].get('edit_data', {})
        caption = edit_data.get('caption', '')
        
        # Add debug info to caption
        debug_info = f"\n\n<b>Debug Info:</b>\nChannel: {channel_type.capitalize()}\n"
        for quality, data in links.items():
            debug_info += f"{quality}: IDs {data['start']}-{data['end']} ({data['count']} files)\n"
        
        final_caption = caption + debug_info if caption else f"<b>━━━━━━━━━━━━━━━━━━</b>\n<blockquote><b>Here are your download buttons from {channel_type.capitalize()} Channel:</b></blockquote>\n{debug_info}\n<b>━━━━━━━━━━━━━━━━━━</b>"
        
        if edit_data.get('image'):
            output_msg = await message.reply_photo(
                photo=edit_data['image'],
                caption=final_caption,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.HTML
            )
        else:
            output_msg = await message.reply(
                text=final_caption,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.HTML
            )
        
        flink_user_data[user_id]['output_message'] = output_msg
    except Exception as e:
        logger.error(f"error in flink_generate_final_output: {e}")
        await message.reply_text(f"<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ An error occurred while generating output: {str(e)}</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)

async def create_link(client: Client, link_data: Dict, channel_type: str, target_channel) -> str:
    """Create a Telegram link for a range of message IDs."""
    try:
        # Get the channel multiplier
        channel_multiplier = abs(target_channel.id)
        
        # Calculate converted IDs (multiply by channel ID)
        start_converted = link_data['start'] * channel_multiplier
        end_converted = link_data['end'] * channel_multiplier
        
        logger.info(f"Creating link for: start_id={link_data['start']}, end_id={link_data['end']}")
        logger.info(f"Channel multiplier: {channel_multiplier}")
        logger.info(f"Converted: start={start_converted}, end={end_converted}")
        
        # Create the string based on channel type
        if channel_type == "secondary":
            string = f"sec-get-{start_converted}-{end_converted}"
        else:
            string = f"get-{start_converted}-{end_converted}"
        
        logger.info(f"String to encode: {string}")
        
        # Encode to base64
        base64_string = await encode(string)
        logger.info(f"Base64 string: {base64_string}")
        
        # Create the final bot link
        link = f"https://t.me/{client.username}?start={base64_string}"
        logger.info(f"Final link: {link}")
        
        return link
        
    except Exception as e:
        logger.error(f"Error in create_link: {e}")
        raise

@Bot.on_callback_query(filters.regex(r"^flink_edit_output$"))
async def flink_edit_output_callback(client: Client, query: CallbackQuery):
    """Handle callback for editing flink output."""
    logger.info(f"flink_edit_output callback triggered by user {query.from_user.id}")
    try:
        admin_ids = await db.get_all_admins() or []
        if query.from_user.id not in admin_ids and query.from_user.id != OWNER_ID:
            await query.answer("You are not authorized!", show_alert=True)
            return

        await query.message.edit_text(
            text="<b>━━━━━━━━━━━━━━━━━━</b>\n"
                 "<b>Add optional elements to the output:</b>\n\n"
                 "Send an image or type a caption separately.\n"
                 "<b>━━━━━━━━━━━━━━━━━━</b>",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("◈ Image ◈", callback_data="flink_add_image"),
                    InlineKeyboardButton("◈ Caption ◈", callback_data="flink_add_caption")
                ],
                [
                    InlineKeyboardButton("✔️ Finish setup 🦋", callback_data="flink_done_output")
                ]
            ]),
            parse_mode=ParseMode.HTML
        )
        await query.answer()
    except Exception as e:
        logger.error(f"error in flink_edit_output_callback: {e}")
        await query.message.edit_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ An error occurred while editing output.</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)

@Bot.on_callback_query(filters.regex(r"^flink_add_image$"))
async def flink_add_image_callback(client: Client, query: CallbackQuery):
    """Handle callback for adding an image to flink output."""
    logger.info(f"flink_add_image callback triggered by user {query.from_user.id}")
    try:
        admin_ids = await db.get_all_admins() or []
        if query.from_user.id not in admin_ids and query.from_user.id != OWNER_ID:
            await query.answer("You are not authorized!", show_alert=True)
            return

        await query.message.edit_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<blockquote><b>Send the image:</b></blockquote>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)
        await query.answer("Send image")
    except Exception as e:
        logger.error(f"error in flink_add_image_callback: {e}")
        await query.message.edit_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<blockquote><b>❌ An error occurred while adding image.</b></blockquote>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)

@Bot.on_message(filters.private & filters.photo & filters.reply)
async def handle_image_input(client: Client, message: Message):
    """Handle image input for flink output."""
    logger.info(f"image input received from user {message.from_user.id}")
    try:
        admin_ids = await db.get_all_admins() or []
        if message.from_user.id not in admin_ids and message.from_user.id != OWNER_ID:
            await message.reply_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ You are not authorized!</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)
            return

        user_id = message.from_user.id
        if user_id not in flink_user_data:
            flink_user_data[user_id] = {
                'format': None,
                'links': {},
                'edit_data': {},
                'menu_message': None,
                'output_message': None,
                'caption_prompt_message': None,
                'awaiting_format': False,
                'awaiting_caption': False,
                'awaiting_db_post': False,
                'channel_type': 'primary'
            }
        elif 'edit_data' not in flink_user_data[user_id]:
            flink_user_data[user_id]['edit_data'] = {}

        if not (message.reply_to_message and "send the image:" in message.reply_to_message.text.lower()):
            logger.info(f"image input ignored for user {user_id} - not a reply to image prompt")
            await message.reply_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ Please reply to the image prompt with a valid image.</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)
            return

        flink_user_data[user_id]['edit_data']['image'] = message.photo.file_id
        await message.reply_text(
            "<b>━━━━━━━━━━━━━━━━━━</b>\n<blockquote><b>✅ Image saved successfully.</b></blockquote>\n<blockquote>Type a caption if needed, or proceed with 'Done'.</blockquote>\n<b>━━━━━━━━━━━━━━━━━━</b>",
            parse_mode=ParseMode.HTML
        )
        await flink_generate_final_output(client, message)
    except Exception as e:
        logger.error(f"error in handle_image_input: {e}")
        await message.reply_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ An error occurred while processing image.</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)

@Bot.on_callback_query(filters.regex(r"^flink_add_caption$"))
async def flink_add_caption_callback(client: Client, query: CallbackQuery):
    """Handle callback for adding a caption to flink output."""
    logger.info(f"flink_add_caption callback triggered by user {query.from_user.id}")
    try:
        admin_ids = await db.get_all_admins() or []
        if query.from_user.id not in admin_ids and query.from_user.id != OWNER_ID:
            await query.answer("You are not authorized!", show_alert=True)
            return

        user_id = query.from_user.id
        flink_user_data[user_id]['awaiting_caption'] = True
        caption_prompt_text = (
            "<b>━━━━━━━━━━━━━━━━━━</b>\n<blockquote><b>Type your caption:</b></blockquote>\n\n"
            "<blockquote><b>Example:</b></blockquote>\n\n"
            "<blockquote><code>ᴛɪᴛʟᴇ- BLACK CLOVER\n"
            "Aᴜᴅɪᴏ Tʀᴀᴄᴋ- Hɪɴᴅɪ Dᴜʙʙᴇᴅ\n\n"
            "Qᴜᴀʟɪᴛʏ - 360ᴘ, 720p, 1080ᴘ\n\n"
            "Eᴘɪsᴏᴅᴇ - 01 & S1 Uᴘʟᴏᴀᴅᴇᴅ\n\n"
            "Aʟʟ Qᴜᴀʟɪᴛʏ - ( Hɪɴᴅɪ Dᴜʙʙᴇᴅ )\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Cʟɪᴄᴋ Hᴇʀᴇ Tᴏ Dᴏᴡɴʟᴏᴀᴅ | Eᴘ - 01 & S1</code></blockquote>\n\n"
            "<blockquote><b>Reply to this message with your caption.</b></blockquote>\n<b>━━━━━━━━━━━━━━━━━━</b>"
        )
        
        caption_prompt_msg = await query.message.reply_text(caption_prompt_text, parse_mode=ParseMode.HTML)
        flink_user_data[user_id]['caption_prompt_message'] = caption_prompt_msg
        
        await query.answer("Type caption")
    except Exception as e:
        logger.error(f"error in flink_add_caption_callback: {e}")
        await query.message.edit_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ An error occurred while adding caption.</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)

@Bot.on_message(filters.private & filters.text & filters.reply & ~filters.regex(r"^CANCEL$") & ~filters.forwarded)
async def handle_caption_input(client: Client, message: Message):
    """Handle caption input for flink command."""
    logger.info(f"caption input received from user {message.from_user.id}, text: {message.text}")
    try:
        admin_ids = await db.get_all_admins() or []
        if message.from_user.id not in admin_ids and message.from_user.id != OWNER_ID:
            await message.reply_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ You are not authorized!</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)
            return

        user_id = message.from_user.id
        if user_id not in flink_user_data or not flink_user_data[user_id].get('awaiting_caption'):
            await message.reply_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ No active caption prompt found. Please use the 'Add Caption' option first.</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)
            return

        caption_prompt_msg = flink_user_data[user_id].get('caption_prompt_message')
        if not caption_prompt_msg or not message.reply_to_message or message.reply_to_message.id != caption_prompt_msg.id:
            logger.info(f"caption input ignored for user {message.from_user.id} - not a reply to caption prompt")
            await message.reply_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ Please reply to the caption prompt message with your caption.</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)
            return

        if 'edit_data' not in flink_user_data[user_id]:
            flink_user_data[user_id]['edit_data'] = {}
        flink_user_data[user_id]['edit_data']['caption'] = message.text
        flink_user_data[user_id]['awaiting_caption'] = False
        await message.reply_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<blockquote><b>✅ Caption saved successfully.</b></blockquote>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)
        await flink_generate_final_output(client, message)
    except Exception as e:
        logger.error(f"error in handle_caption_input: {e}")
        await message.reply_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ An error occurred while processing caption.</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)

@Bot.on_callback_query(filters.regex(r"^flink_done_output$"))
async def flink_done_output_callback(client: Client, query: CallbackQuery):
    """Handle callback for finalizing flink output."""
    logger.info(f"flink_done_output callback triggered by user {query.from_user.id}")
    try:
        admin_ids = await db.get_all_admins() or []
        if query.from_user.id not in admin_ids and query.from_user.id != OWNER_ID:
            await query.answer("You are not authorized!", show_alert=True)
            return

        user_id = query.from_user.id
        if user_id not in flink_user_data or 'links' not in flink_user_data[user_id]:
            await query.message.edit_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<blockquote><b>❌ No links found. Please start the process again using /flink.</b></blockquote>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)
            return

        links = flink_user_data[user_id]['links']
        channel_type = flink_user_data[user_id]['channel_type']
        target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel
        edit_data = flink_user_data[user_id].get('edit_data', {})
        caption = edit_data.get('caption', '')
        
        buttons = []
        quality_list = list(links.keys())
        num_qualities = len(quality_list)
        
        if num_qualities == 2:
            buttons.append([
                InlineKeyboardButton(f"🦋 {quality_list[0]} 🦋", url=await create_link(client, links[quality_list[0]], channel_type, target_channel)),
                InlineKeyboardButton(f"🦋 {quality_list[1]} 🦋", url=await create_link(client, links[quality_list[1]], channel_type, target_channel))
            ])
        elif num_qualities == 3:
            buttons.append([
                InlineKeyboardButton(f"🦋 {quality_list[0]} 🦋", url=await create_link(client, links[quality_list[0]], channel_type, target_channel)),
                InlineKeyboardButton(f"🦋 {quality_list[1]} 🦋", url=await create_link(client, links[quality_list[1]], channel_type, target_channel))
            ])
            buttons.append([
                InlineKeyboardButton(f"🦋 {quality_list[2]} 🦋", url=await create_link(client, links[quality_list[2]], channel_type, target_channel))
            ])
        elif num_qualities == 4:
            buttons.append([
                InlineKeyboardButton(f"🦋 {quality_list[0]} 🦋", url=await create_link(client, links[quality_list[0]], channel_type, target_channel)),
                InlineKeyboardButton(f"🦋 {quality_list[1]} 🦋", url=await create_link(client, links[quality_list[1]], channel_type, target_channel))
            ])
            buttons.append([
                InlineKeyboardButton(f"🦋 {quality_list[2]} 🦋", url=await create_link(client, links[quality_list[2]], channel_type, target_channel)),
                InlineKeyboardButton(f"🦋 {quality_list[3]} 🦋", url=await create_link(client, links[quality_list[3]], channel_type, target_channel))
            ])
        elif num_qualities == 5:
            buttons.append([
                InlineKeyboardButton(f"🦋 {quality_list[0]} 🦋", url=await create_link(client, links[quality_list[0]], channel_type, target_channel)),
                InlineKeyboardButton(f"🦋 {quality_list[1]} 🦋", url=await create_link(client, links[quality_list[1]], channel_type, target_channel))
            ])
            buttons.append([
                InlineKeyboardButton(f"🦋 {quality_list[2]} 🦋", url=await create_link(client, links[quality_list[2]], channel_type, target_channel)),
                InlineKeyboardButton(f"🦋 {quality_list[3]} 🦋", url=await create_link(client, links[quality_list[3]], channel_type, target_channel))
            ])
            buttons.append([
                InlineKeyboardButton(f"🦋 {quality_list[4]} 🦋", url=await create_link(client, links[quality_list[4]], channel_type, target_channel))
            ])
        else:
            for quality in quality_list:
                buttons.append([
                    InlineKeyboardButton(f"🦋 {quality} 🦋", url=await create_link(client, links[quality], channel_type, target_channel))
                ])
        
        if edit_data.get('image'):
            await query.message.reply_photo(
                photo=edit_data['image'],
                caption=caption,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.HTML
            )
        else:
            await query.message.reply(
                text=caption if caption else f"<b>━━━━━━━━━━━━━━━━━━</b>\n<blockquote><b>Here are your download buttons from {channel_type.capitalize()} Channel:</b></blockquote>\n<b>━━━━━━━━━━━━━━━━━━</b>",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.HTML
            )
        
        if user_id in flink_user_data:
            del flink_user_data[user_id]
        await query.answer("Process completed")
    except Exception as e:
        logger.error(f"error in flink_done_output_callback: {e}")
        await query.message.edit_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ An error occurred while completing process.</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)

@Bot.on_callback_query(filters.regex(r"^flink_refresh$"))
async def flink_refresh_callback(client: Client, query: CallbackQuery):
    """Handle callback to refresh flink menu."""
    logger.info(f"flink_refresh callback triggered by user {query.from_user.id}")
    try:
        admin_ids = await db.get_all_admins() or []
        if query.from_user.id not in admin_ids and query.from_user.id != OWNER_ID:
            await query.answer("You are not authorized!", show_alert=True)
            return

        await show_flink_main_menu(client, query.message, edit=True)
        await query.answer("Format status refreshed")
    except Exception as e:
        logger.error(f"error in flink_refresh_callback: {e}")
        await query.message.edit_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ An error occurred while refreshing status.</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)

@Bot.on_callback_query(filters.regex(r"^flink_(back_to_menu|cancel_process|back_to_output|close)$"))
async def flink_handle_back_buttons(client: Client, query: CallbackQuery):
    """Handle back, cancel, and close actions for flink command."""
    logger.info(f"flink back/cancel/close callback triggered by user {query.from_user.id} with action {query.data}")
    try:
        admin_ids = await db.get_all_admins() or []
        if query.from_user.id not in admin_ids and query.from_user.id != OWNER_ID:
            await query.answer("You are not authorized!", show_alert=True)
            return

        action = query.data.split("_")[-1]
        
        if action == "back_to_menu":
            await show_flink_main_menu(client, query.message, edit=True)
            await query.answer("Back to menu")
        elif action == "cancel_process":
            await query.message.edit_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ Process cancelled.</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)
            if query.from_user.id in flink_user_data:
                del flink_user_data[query.from_user.id]
            await query.answer("Process cancelled")
        elif action == "back_to_output":
            await flink_generate_final_output(client, query.message)
            await query.answer("Back to output")
        elif action == "close":
            await query.message.delete()
            if query.from_user.id in flink_user_data:
                del flink_user_data[query.from_user.id]
            await query.answer("Menu closed")
    except Exception as e:
        logger.error(f"error in flink_handle_back_buttons: {e}")
        await query.message.edit_text("<b>━━━━━━━━━━━━━━━━━━</b>\n<b>❌ An error occurred while processing action.</b>\n<b>━━━━━━━━━━━━━━━━━━</b>", parse_mode=ParseMode.HTML)

#
# Copyright (C) 2025 by AnimeLord-Bots@Github, < https://github.com/AnimeLord-Bots >.
#
# This file is part of < https://github.com/AnimeLord-Bots/FileStore > project,
# and is released under the MIT License.
# Please see < https://github.com/AnimeLord-Bots/FileStore/blob/master/LICENSE >
#
# All rights reserved.
#
