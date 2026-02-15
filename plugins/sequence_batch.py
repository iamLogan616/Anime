#(©)Codeflix_Bots
# Support @rohit_1888 on Tg

import asyncio
import base64
import ast
import logging
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait
from bot import Bot
from config import *
from helper_func import encode, decode, admin, is_subscribed, not_joined, get_messages
from database.database import db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Temporary storage for sequence batch creation
# Structure: {user_id: {"channel_type": str, "messages": list, "titles": list, "current_index": int, "name": str}}
sequence_batch_data = {}

class MessageTypes:
    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    ANIMATION = "animation"
    STICKER = "sticker"
    VOICE = "voice"
    VIDEO_NOTE = "video_note"
    CONTACT = "contact"
    LOCATION = "location"
    VENUE = "venue"
    POLL = "poll"

async def get_message_type(message: Message) -> str:
    """Detect the type of message"""
    if message.text:
        return MessageTypes.TEXT
    elif message.photo:
        return MessageTypes.PHOTO
    elif message.video:
        return MessageTypes.VIDEO
    elif message.audio:
        return MessageTypes.AUDIO
    elif message.document:
        return MessageTypes.DOCUMENT
    elif message.animation:
        return MessageTypes.ANIMATION
    elif message.sticker:
        return MessageTypes.STICKER
    elif message.voice:
        return MessageTypes.VOICE
    elif message.video_note:
        return MessageTypes.VIDEO_NOTE
    elif message.contact:
        return MessageTypes.CONTACT
    elif message.location:
        return MessageTypes.LOCATION
    elif message.venue:
        return MessageTypes.VENUE
    elif message.poll:
        return MessageTypes.POLL
    else:
        return "unknown"

def get_message_type_icon(msg_type: str) -> str:
    """Get icon for message type"""
    icons = {
        MessageTypes.TEXT: "📝",
        MessageTypes.PHOTO: "🖼️",
        MessageTypes.VIDEO: "🎥",
        MessageTypes.AUDIO: "🎵",
        MessageTypes.DOCUMENT: "📄",
        MessageTypes.ANIMATION: "🎭",
        MessageTypes.STICKER: "🎯",
        MessageTypes.VOICE: "🎤",
        MessageTypes.VIDEO_NOTE: "📹",
        MessageTypes.CONTACT: "👤",
        MessageTypes.LOCATION: "📍",
        MessageTypes.VENUE: "🏢",
        MessageTypes.POLL: "📊",
        "unknown": "❓"
    }
    return icons.get(msg_type, "📦")

def get_message_preview(message: Message, max_length: int = 30) -> str:
    """Get a preview of the message content"""
    msg_type = get_message_type(message)
    
    if msg_type == MessageTypes.TEXT and message.text:
        text = message.text.replace('\n', ' ').strip()
        return text[:max_length] + "..." if len(text) > max_length else text
    elif msg_type == MessageTypes.PHOTO:
        return "📷 Photo" + (f" - {message.caption[:max_length]}..." if message.caption else "")
    elif msg_type == MessageTypes.VIDEO:
        duration = f"{message.video.duration}s" if message.video.duration else ""
        return f"🎬 Video {duration}" + (f" - {message.caption[:max_length]}..." if message.caption else "")
    elif msg_type == MessageTypes.DOCUMENT:
        name = message.document.file_name or "Document"
        size = f"{message.document.file_size / 1024 / 1024:.1f}MB" if message.document.file_size else ""
        return f"📄 {name[:max_length-10]}... {size}" if len(name) > max_length-10 else f"📄 {name} {size}"
    elif msg_type == MessageTypes.AUDIO:
        title = message.audio.title or "Audio"
        performer = message.audio.performer or ""
        return f"🎵 {title[:max_length-15]}..." if len(title) > max_length-15 else f"🎵 {title} {performer}"
    else:
        return f"{get_message_type_icon(msg_type)} {msg_type}"

@Bot.on_message(filters.private & admin & filters.command('seqbatch'))
async def start_sequence_batch(client: Bot, message: Message):
    """Start the sequence batch creation process"""
    user_id = message.from_user.id
    
    # Check if secondary channel is available
    if not client.secondary_channel:
        # Only primary channel available
        sequence_batch_data[user_id] = {
            "channel_type": "primary",
            "messages": [],
            "titles": [],
            "current_index": 0,
            "name": f"Batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }
        target_channel = client.db_channel
        await message.reply(
            f"<b>📦 Starting Sequence Batch Creation</b>\n\n"
            f"<b>Channel:</b> {target_channel.title} (Primary)\n"
            f"<b>Instructions:</b>\n"
            f"1️⃣ Send messages one by one (any type: text, photo, video, document, etc.)\n"
            f"2️⃣ After each message, you'll set a button title\n"
            f"3️⃣ Type <code>/done</code> when finished\n"
            f"4️⃣ Type <code>/cancel</code> to abort\n\n"
            f"<b>Send your first message:</b>"
        )
        return
    
    # Ask user to choose channel
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 Primary Channel", callback_data="seq_primary")],
        [InlineKeyboardButton("📂 Secondary Channel", callback_data="seq_secondary")],
        [InlineKeyboardButton("❌ Cancel", callback_data="close")]
    ])
    
    await message.reply(
        "<b>📦 Select Channel for Sequence Batch</b>\n\n"
        "Choose which channel to store the messages in:",
        reply_markup=keyboard
    )

@Bot.on_callback_query(filters.regex(r"^seq_(primary|secondary)$"))
async def select_sequence_channel(client: Bot, callback_query: CallbackQuery):
    """Handle channel selection for sequence batch"""
    user_id = callback_query.from_user.id
    channel_type = callback_query.data.split("_")[1]
    
    if channel_type == "secondary" and not client.secondary_channel:
        await callback_query.answer("Secondary channel not configured!", show_alert=True)
        return
    
    target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel
    
    # Initialize session
    sequence_batch_data[user_id] = {
        "channel_type": channel_type,
        "messages": [],
        "titles": [],
        "current_index": 0,
        "name": f"Batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    }
    
    await callback_query.message.delete()
    await callback_query.message.reply(
        f"<b>📦 Starting Sequence Batch Creation</b>\n\n"
        f"<b>Channel:</b> {target_channel.title} ({channel_type.capitalize()})\n"
        f"<b>Instructions:</b>\n"
        f"1️⃣ Send messages one by one (any type: text, photo, video, document, etc.)\n"
        f"2️⃣ After each message, you'll set a button title\n"
        f"3️⃣ Type <code>/done</code> when finished\n"
        f"4️⃣ Type <code>/cancel</code> to abort\n\n"
        f"<b>Send your first message:</b>"
    )
    
    await callback_query.answer()

@Bot.on_message(filters.private & admin & filters.command('cancel'))
async def cancel_sequence_batch(client: Bot, message: Message):
    """Cancel the sequence batch creation"""
    user_id = message.from_user.id
    
    if user_id in sequence_batch_data:
        del sequence_batch_data[user_id]
        await message.reply("❌ Sequence batch creation cancelled.")
    else:
        await message.reply("No active batch creation session.")

@Bot.on_message(filters.private & admin & filters.command('done'))
async def finish_sequence_batch(client: Bot, message: Message):
    """Finish the sequence batch and generate link"""
    user_id = message.from_user.id
    
    if user_id not in sequence_batch_data:
        await message.reply("No active batch creation session. Use /seqbatch to start.")
        return
    
    data = sequence_batch_data[user_id]
    
    if len(data["messages"]) == 0:
        await message.reply("No messages added to batch. Use /cancel to exit.")
        return
    
    # Generate the batch link
    await generate_sequence_link(client, message, data)

async def generate_sequence_link(client: Bot, message: Message, data: dict):
    """Generate link for sequence batch with custom button titles"""
    user_id = message.from_user.id
    channel_type = data["channel_type"]
    message_ids = data["messages"]
    button_titles = data["titles"]
    batch_name = data.get("name", f"Batch_{len(message_ids)}_files")
    
    target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel
    
    # Create the batch string with metadata
    # Format: seq-{start_id}-{end_id}-{titles_encoded}
    titles_json = str(button_titles)
    titles_b64 = base64.b64encode(titles_json.encode()).decode()
    
    channel_multiplier = abs(target_channel.id)
    start_id = message_ids[0] * channel_multiplier
    end_id = message_ids[-1] * channel_multiplier
    
    string = f"seq-{start_id}-{end_id}-{titles_b64}"
    
    # Add prefix for secondary channel
    if channel_type == "secondary":
        string = f"sec-{string}"
    
    base64_string = await encode(string)
    
    # Generate link based on config
    if PERMANENT_LINKS and BLOGSPOT_URL:
        link = f"{BLOGSPOT_URL}?{BLOGSPOT_PARAM}={base64_string}"
        link_type = "🔗 Permanent"
    else:
        link = f"https://t.me/{client.username}?start={base64_string}"
        link_type = "🤖 Direct"
    
    # Create preview of files
    files_preview = ""
    for i, (msg_id, title) in enumerate(zip(message_ids, button_titles), 1):
        files_preview += f"{i}. {title}\n"
    
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Share URL", url=f'https://telegram.me/share/url?url={link}')],
        [InlineKeyboardButton("📺 View Channel", url=f"https://t.me/{target_channel.username}" if target_channel.username else f"https://t.me/c/{str(target_channel.id)[4:]}")],
        [InlineKeyboardButton("📋 Copy Link", callback_data=f"copy_{base64_string}")]
    ])
    
    await message.reply_text(
        f"<b>✅ Sequence Batch Created Successfully!</b>\n\n"
        f"<b>{link_type} Link</b>\n"
        f"<code>{link}</code>\n\n"
        f"<b>📊 Batch Details:</b>\n"
        f"• <b>Channel:</b> {target_channel.title} ({channel_type.capitalize()})\n"
        f"• <b>Total Files:</b> {len(message_ids)}\n"
        f"• <b>Batch Name:</b> {batch_name}\n"
        f"• <b>Message IDs:</b> {message_ids[0]} → {message_ids[-1]}\n\n"
        f"<b>📋 File List with Buttons:</b>\n<blockquote>{files_preview}</blockquote>",
        reply_markup=reply_markup
    )
    
    # Send confirmation to channel
    try:
        await client.send_message(
            target_channel.id,
            f"<b>📦 New Sequence Batch Created</b>\n\n"
            f"<b>Name:</b> {batch_name}\n"
            f"<b>Files:</b> {len(message_ids)}\n"
            f"<b>Created by:</b> {message.from_user.mention}\n"
            f"<b>Link:</b> {link}"
        )
    except:
        pass
    
    # Clear session data
    del sequence_batch_data[user_id]

@Bot.on_message(filters.private & admin)
async def handle_sequence_message(client: Bot, message: Message):
    """Handle messages during sequence batch creation"""
    user_id = message.from_user.id
    
    # Ignore commands
    if message.text and message.text.startswith('/'):
        return
    
    # Check if user has active session
    if user_id not in sequence_batch_data:
        return
    
    data = sequence_batch_data[user_id]
    target_channel = client.secondary_channel if data["channel_type"] == "secondary" else client.db_channel
    
    # Store the message in channel
    try:
        # Copy message to channel
        sent_msg = await message.copy(
            chat_id=target_channel.id,
            disable_notification=True
        )
        
        msg_id = sent_msg.id
        msg_type = get_message_type(message)
        msg_icon = get_message_type_icon(msg_type)
        preview = get_message_preview(message)
        
        # Store message ID temporarily
        data["messages"].append(msg_id)
        data["current_index"] += 1
        
        # Ask for button title
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭️ Skip Title", callback_data=f"title_skip_{msg_id}")],
            [InlineKeyboardButton("❌ Cancel Batch", callback_data="close")]
        ])
        
        title_request = await message.reply(
            f"<b>✅ Message #{data['current_index']} Stored!</b>\n\n"
            f"<b>Message ID:</b> <code>{msg_id}</code>\n"
            f"<b>Type:</b> {msg_icon} {msg_type}\n"
            f"<b>Preview:</b> <code>{preview}</code>\n\n"
            f"<b>📝 Send a button title for this message:</b>\n"
            f"(or click 'Skip Title' to use default)\n\n"
            f"<i>You can send any text as title. It will appear on the button when users access the batch.</i>",
            reply_markup=keyboard
        )
        
        # Store the request message ID to delete later
        data["last_title_request"] = title_request.id
        
    except FloodWait as e:
        await asyncio.sleep(e.x)
        await handle_sequence_message(client, message)
    except Exception as e:
        await message.reply(f"❌ Failed to store message: {str(e)}")

@Bot.on_message(filters.private & admin & filters.text)
async def handle_button_title(client: Bot, message: Message):
    """Handle button title input during sequence batch"""
    user_id = message.from_user.id
    
    if user_id not in sequence_batch_data:
        return
    
    data = sequence_batch_data[user_id]
    
    # Check if we're waiting for a title
    if "last_title_request" not in data:
        return
    
    # Get the last message ID that was stored
    if not data["messages"]:
        return
    
    last_msg_id = data["messages"][-1]
    title = message.text.strip()
    
    # Store the title
    data["titles"].append(title)
    
    # Delete the title request message
    try:
        await client.delete_messages(
            chat_id=message.chat.id,
            message_ids=data["last_title_request"]
        )
        del data["last_title_request"]
    except:
        pass
    
    # Delete the user's title message
    try:
        await message.delete()
    except:
        pass
    
    # Confirm and ask for next message
    await message.reply(
        f"<b>✅ Title Set for Message #{data['current_index']}</b>\n\n"
        f"<b>Title:</b> {title}\n"
        f"<b>Total stored:</b> {data['current_index']} messages\n\n"
        f"<b>Send next message or type:</b>\n"
        f"• <code>/done</code> - Finish batch\n"
        f"• <code>/cancel</code> - Cancel"
    )

@Bot.on_callback_query(filters.regex(r"^title_skip_(\d+)$"))
async def skip_button_title(client: Bot, callback_query: CallbackQuery):
    """Skip setting custom title, use default"""
    user_id = callback_query.from_user.id
    msg_id = int(callback_query.data.split("_")[2])
    
    if user_id not in sequence_batch_data:
        await callback_query.answer("Session expired!", show_alert=True)
        return
    
    data = sequence_batch_data[user_id]
    
    # Use default title based on message type and index
    default_title = f"File #{data['current_index']}"
    
    # Try to get message to create better default title
    try:
        target_channel = client.secondary_channel if data["channel_type"] == "secondary" else client.db_channel
        msg = await client.get_messages(target_channel.id, msg_id)
        msg_type = get_message_type(msg)
        
        if msg_type == MessageTypes.DOCUMENT and msg.document and msg.document.file_name:
            default_title = msg.document.file_name.split('/')[-1][:30]
        elif msg_type == MessageTypes.VIDEO and msg.video and msg.video.file_name:
            default_title = msg.video.file_name.split('/')[-1][:30]
        elif msg_type == MessageTypes.AUDIO and msg.audio:
            default_title = msg.audio.title or msg.audio.file_name or f"Audio #{data['current_index']}"
        elif msg_type == MessageTypes.PHOTO:
            default_title = f"Photo #{data['current_index']}"
        else:
            default_title = f"{msg_type.capitalize()} #{data['current_index']}"
    except:
        pass
    
    # Store the default title
    data["titles"].append(default_title)
    
    # Delete the title request message
    try:
        await client.delete_messages(
            chat_id=callback_query.message.chat.id,
            message_ids=callback_query.message.id
        )
    except:
        pass
    
    await callback_query.message.reply(
        f"<b>✅ Default Title Set for Message #{data['current_index']}</b>\n\n"
        f"<b>Title:</b> {default_title}\n"
        f"<b>Total stored:</b> {data['current_index']} messages\n\n"
        f"<b>Send next message or type:</b>\n"
        f"• <code>/done</code> - Finish batch\n"
        f"• <code>/cancel</code> - Cancel"
    )
    
    await callback_query.answer()

@Bot.on_callback_query(filters.regex(r"^copy_(.+)$"))
async def copy_link_callback(client: Bot, callback_query: CallbackQuery):
    """Handle copy link callback"""
    encoded = callback_query.data.split("_")[1]
    
    # Generate the full link
    if PERMANENT_LINKS and BLOGSPOT_URL:
        link = f"{BLOGSPOT_URL}?{BLOGSPOT_PARAM}={encoded}"
    else:
        link = f"https://t.me/{client.username}?start={encoded}"
    
    await callback_query.answer(f"Link: {link}", show_alert=True)

@Bot.on_message(filters.command('seqlist'))
async def list_sequence_batches(client: Bot, message: Message):
    """List all sequence batches in channels"""
    user_id = message.from_user.id
    
    # Check if user is admin
    if not await check_admin(None, client, message):
        return
    
    keyboard = []
    
    if client.db_channel:
        keyboard.append([InlineKeyboardButton(
            f"📌 Primary: {client.db_channel.title[:20]}",
            callback_data="list_seq_primary"
        )])
    
    if client.secondary_channel:
        keyboard.append([InlineKeyboardButton(
            f"📂 Secondary: {client.secondary_channel.title[:20]}",
            callback_data="list_seq_secondary"
        )])
    
    keyboard.append([InlineKeyboardButton("❌ Close", callback_data="close")])
    
    await message.reply(
        "<b>📋 Select Channel to List Sequence Batches</b>",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@Bot.on_callback_query(filters.regex(r"^list_seq_(primary|secondary)$"))
async def show_channel_batches(client: Bot, callback_query: CallbackQuery):
    """Show batches in selected channel"""
    channel_type = callback_query.data.split("_")[2]
    target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel
    
    await callback_query.answer("Batch listing feature coming soon! This will show all sequence batches stored in this channel.", show_alert=True)
