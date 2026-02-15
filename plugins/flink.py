# plugins/flink.py
# Formatted Link Generator – with robust callback handling

import re
import logging
from pyrogram import filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, ReplyKeyboardRemove, CallbackQuery
)
from pyrogram.errors import FloodWait
from asyncio import TimeoutError
from bot import Bot
from config import *
from helper_func import admin, encode, decode, get_message_id, get_messages
from database.database import db
from plugins.link_generator import choose_channel, generate_link, get_link_type

# ============================ LOGGING ============================
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s"
)
LOGGER = logging.getLogger(__name__)

# ====================== SESSION STORAGE ======================
flink_sessions = {}

# ====================== HELPER FUNCTIONS ======================
def parse_format(text: str):
    pairs = [p.strip() for p in text.split(',')]
    result = []
    for pair in pairs:
        match = re.match(r'^([A-Za-z0-9]+)\s*=\s*(\d+)$', pair.strip())
        if not match:
            return None
        quality = match.group(1)
        count = int(match.group(2))
        result.append((quality, count))
    return result

def format_summary(format_list):
    if not format_list:
        return "Not set"
    return ", ".join(f"{q} = {c}" for q, c in format_list)

def encode_format(format_list):
    return "_".join(f"{quality}{count}" for quality, count in format_list)

def decode_format(encoded):
    result = []
    parts = encoded.split("_")
    for part in parts:
        match = re.match(r'^([A-Za-z0-9]+)(\d+)$', part)
        if match:
            quality = match.group(1)
            count = int(match.group(2))
            result.append((quality, count))
    return result

# ====================== MAIN COMMAND ======================
@Bot.on_message(filters.private & admin & filters.command("flink"))
async def flink_command(client: Bot, message: Message):
    user_id = message.from_user.id
    LOGGER.info(f"User {user_id} issued /flink command")

    if user_id not in flink_sessions:
        flink_sessions[user_id] = {"format": None, "channel_type": None, "start_msg_id": None}

    # Use both colon and underscore to be safe
    buttons = [
        [InlineKeyboardButton("• sᴇᴛ ғᴏʀᴍᴀᴛ •", callback_data="flink:set")],
        [InlineKeyboardButton("• sᴛᴀʀᴛ ᴘʀᴏᴄᴇss •", callback_data="flink:start")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="flink:refresh")]
    ]
    current_format = format_summary(flink_sessions[user_id]["format"])
    text = (
        f"<b>📎 Formatted Link Generator</b>\n\n"
        f"<b>Current Format:</b> {current_format}\n\n"
        f"Use the buttons below to set the format and start the process."
    )
    await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))

# ====================== ROBUST CALLBACK HANDLER ======================
@Bot.on_callback_query()
async def flink_catch_all(client: Bot, callback: CallbackQuery):
    """Catches any callback and routes flink-related ones."""
    data = callback.data
    user_id = callback.from_user.id

    # If it's not a flink callback, ignore (let other handlers process it)
    if not data.startswith("flink"):
        # Allow other plugins to handle it
        callback.continue_propagation()
        return

    LOGGER.info(f"Flink callback received: {data} from user {user_id}")

    try:
        # Immediately answer to stop loading animation
        await callback.answer()

        # Extract action: supports both "flink:set" and "flink_set"
        if ":" in data:
            action = data.split(":", 1)[1]
        elif "_" in data:
            action = data.split("_", 1)[1]
        else:
            action = data[5:]  # remove "flink" prefix

        if action == "set":
            await callback.message.delete()
            await set_format(client, callback.message, user_id)

        elif action == "start":
            await callback.message.delete()
            await start_process(client, callback.message, user_id)

        elif action == "refresh":
            if user_id not in flink_sessions:
                flink_sessions[user_id] = {"format": None, "channel_type": None, "start_msg_id": None}
            current = format_summary(flink_sessions[user_id].get("format"))
            await callback.answer(f"Current format: {current}", show_alert=True)

        else:
            LOGGER.warning(f"Unknown flink action '{action}'")
            await callback.answer("Unknown action", show_alert=True)

    except Exception as e:
        LOGGER.error(f"Error in flink callback: {e}", exc_info=True)
        try:
            await callback.answer("An error occurred. Check logs.", show_alert=True)
        except:
            pass

# ====================== SET FORMAT ======================
async def set_format(client: Bot, msg: Message, user_id: int):
    try:
        answer = await client.ask(
            chat_id=user_id,
            text=(
                "<b>📝 Send the format for links.</b>\n\n"
                "Example: <code>360P = 2, 480P = 2, 720P = 2</code>\n"
                "Meaning: 2 files for 360P, 2 for 480P, 2 for 720P.\n\n"
                "You can use any quality names.\n"
                "Type <code>CANCEL</code> to abort."
            ),
            timeout=120
        )
    except TimeoutError:
        await client.send_message(user_id, "⏰ Timeout. Operation cancelled.")
        return

    if answer.text and answer.text.upper() == "CANCEL":
        await answer.reply("❌ Operation cancelled.")
        return

    format_list = parse_format(answer.text)
    if not format_list:
        await answer.reply(
            "❌ Invalid format. Please use the pattern: <code>QUALITY = COUNT</code> separated by commas.\n"
            "Example: <code>480P = 1, 720P = 2, 1080P = 1</code>"
        )
        return

    if user_id not in flink_sessions:
        flink_sessions[user_id] = {"format": None, "channel_type": None, "start_msg_id": None}
    flink_sessions[user_id]["format"] = format_list
    await answer.reply(f"✅ Format set: {format_summary(format_list)}")

# ====================== START PROCESS ======================
async def start_process(client: Bot, msg: Message, user_id: int):
    if user_id not in flink_sessions or not flink_sessions[user_id].get("format"):
        await client.send_message(user_id, "❌ Please set the format first using /flink.")
        return

    channel_type = await choose_channel(client, msg, "📌 Select channel for formatted links:")
    if channel_type is None:
        return

    if channel_type == "secondary" and not client.secondary_channel:
        await client.send_message(user_id, "❌ Secondary channel not configured.", reply_markup=ReplyKeyboardRemove())
        return

    target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel
    flink_sessions[user_id]["channel_type"] = channel_type

    try:
        start_msg = await client.ask(
            chat_id=user_id,
            text=(
                f"📤 Now forward the <b>first message</b> of the sequence from the "
                f"{channel_type.capitalize()} DB Channel, or send its link."
            ),
            filters=(filters.forwarded | (filters.text & ~filters.forwarded)),
            timeout=120
        )
    except TimeoutError:
        await client.send_message(user_id, "⏰ Timeout. Operation cancelled.")
        return

    if start_msg.text and start_msg.text.upper() == "CANCEL":
        await start_msg.reply("❌ Operation cancelled.")
        return

    start_id = await get_message_id(client, start_msg)
    if not start_id:
        await start_msg.reply(f"❌ Could not get message ID from {channel_type} channel.")
        return

    if start_msg.forward_from_chat and start_msg.forward_from_chat.id != target_channel.id:
        await start_msg.reply(f"❌ This message is not from the {channel_type} DB Channel.")
        return

    format_list = flink_sessions[user_id]["format"]
    total_needed = sum(count for _, count in format_list)

    # Encode data for shareable link
    channel_code = "p" if channel_type == "primary" else "s"
    format_encoded = encode_format(format_list)
    data_str = f"flink-{channel_code}-{start_id}-{format_encoded}"
    base64_param = await encode(data_str)
    share_link = generate_link(f"flink_{base64_param}", client)

    link_type = get_link_type()
    link_info = "🔗 **Permanent Link**" if link_type == "Permanent" else "🤖 **Direct Link**"

    text = (
        f"<b>✅ Formatted Links Generated – Single Shareable Link</b>\n\n"
        f"<b>{link_info}</b>\n"
        f"<b>Channel:</b> {target_channel.title}\n"
        f"<b>Format:</b> {format_summary(format_list)}\n"
        f"<b>Start Message ID:</b> {start_id}\n\n"
        f"📎 <b>Share this link with users:</b>\n"
        f"<code>{share_link}</code>\n\n"
        f"When clicked, users will see the quality selection buttons."
    )

    await client.send_message(user_id, text, disable_web_page_preview=True)
    flink_sessions[user_id] = {"format": None, "channel_type": None, "start_msg_id": None}
