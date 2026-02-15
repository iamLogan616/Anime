# plugins/flink.py
# Formatted Link Generator (multi-quality batch links)

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
from helper_func import admin, encode, get_message_id, get_messages
from database.database import db
from plugins.link_generator import choose_channel, generate_link, get_link_type

# ============================ LOGGING ============================
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s"
)
LOGGER = logging.getLogger(__name__)

# ====================== SESSION STORAGE ======================
# Format: {user_id: {"format": [(quality, count), ...], "channel_type": str, "start_msg_id": int}}
flink_sessions = {}

# ====================== HELPER FUNCTIONS ======================
def parse_format(text: str):
    """Parse format string like '360P = 2, 480P = 2, 720P = 2' into list of (quality, count)."""
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
    """Create a readable summary of the current format."""
    if not format_list:
        return "Not set"
    return ", ".join(f"{q} = {c}" for q, c in format_list)

# ====================== MAIN COMMAND ======================
@Bot.on_message(filters.private & admin & filters.command("flink"))
async def flink_command(client: Bot, message: Message):
    user_id = message.from_user.id
    LOGGER.info(f"User {user_id} issued /flink command")

    # Initialize session if not exists
    if user_id not in flink_sessions:
        flink_sessions[user_id] = {"format": None, "channel_type": None, "start_msg_id": None}

    # Main menu buttons (using colon in callback data for reliable splitting)
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

# ====================== CALLBACK HANDLER ======================
@Bot.on_callback_query(filters.regex(r"^flink:"))
async def flink_callback(client: Bot, callback: CallbackQuery):
    user_id = callback.from_user.id
    LOGGER.info(f"Callback received: {callback.data} from user {user_id}")

    try:
        # Always answer the callback immediately to stop loading animation
        await callback.answer()

        # Extract action (everything after "flink:")
        action = callback.data.split(":", 1)[1]  # "set", "start", "refresh"

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
            LOGGER.warning(f"Unknown action '{action}' from user {user_id}")
            await callback.answer("Unknown action", show_alert=True)

    except Exception as e:
        LOGGER.error(f"Error in flink_callback for user {user_id}: {e}", exc_info=True)
        # Ensure callback is answered even if something crashed
        try:
            await callback.answer("An error occurred. Please try again.", show_alert=True)
        except:
            pass

# ====================== STEP FUNCTIONS ======================
async def set_format(client: Bot, msg: Message, user_id: int):
    """Ask user for the format string and store it."""
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

    # Store in session
    if user_id not in flink_sessions:
        flink_sessions[user_id] = {"format": None, "channel_type": None, "start_msg_id": None}
    flink_sessions[user_id]["format"] = format_list
    await answer.reply(f"✅ Format set: {format_summary(format_list)}")

async def start_process(client: Bot, msg: Message, user_id: int):
    """Start the link generation process."""
    # Check if format is set
    if user_id not in flink_sessions or not flink_sessions[user_id].get("format"):
        await client.send_message(user_id, "❌ Please set the format first using /flink.")
        return

    # Choose channel (primary or secondary)
    channel_type = await choose_channel(client, msg, "📌 Select channel for formatted links:")
    if channel_type is None:
        return

    if channel_type == "secondary" and not client.secondary_channel:
        await client.send_message(user_id, "❌ Secondary channel not configured.", reply_markup=ReplyKeyboardRemove())
        return

    target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel
    flink_sessions[user_id]["channel_type"] = channel_type

    # Get the starting message from the user
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

    # Verify it's from the correct channel
    if start_msg.forward_from_chat:
        expected_id = target_channel.id
        if start_msg.forward_from_chat.id != expected_id:
            await start_msg.reply(f"❌ This message is not from the {channel_type} DB Channel.")
            return
    else:
        # If it's a link, we trust get_message_id already checked the channel.
        pass

    # Calculate total files needed
    format_list = flink_sessions[user_id]["format"]
    total_needed = sum(count for _, count in format_list)
    end_id = start_id + total_needed - 1

    # Fetch the messages from the DB channel
    try:
        messages = await get_messages(client, list(range(start_id, end_id + 1)), channel=channel_type)
    except Exception as e:
        await start_msg.reply(f"❌ Failed to fetch messages: {e}")
        return

    if len(messages) < total_needed:
        await start_msg.reply(
            f"❌ Not enough messages in the channel.\n"
            f"Required: {total_needed}, Found: {len(messages)}"
        )
        return

    # Build batch links for each quality
    multiplier = abs(target_channel.id)
    current_index = 0
    quality_buttons = []

    for quality, count in format_list:
        if count == 0:
            continue

        # Get the slice of message IDs for this quality
        msg_ids = [msg.id for msg in messages[current_index:current_index + count]]
        if not msg_ids:
            continue

        # Create a batch link for this quality range
        start_id_mult = msg_ids[0] * multiplier
        end_id_mult = msg_ids[-1] * multiplier
        string = f"get-{start_id_mult}-{end_id_mult}"
        if channel_type == "secondary":
            string = f"sec-{string}"

        base64_string = await encode(string)
        link = generate_link(base64_string, client)

        # Add button for this quality
        quality_buttons.append([InlineKeyboardButton(text=quality, url=link)])

        current_index += count

    # Send the final message with all quality buttons
    link_type = get_link_type()
    link_info = (
        "🔗 **Permanent Link**" if link_type == "Permanent" else "🤖 **Direct Link**"
    )

    text = (
        f"<b>✅ Formatted Links Generated</b>\n\n"
        f"<b>{link_info}</b>\n"
        f"<b>Channel:</b> {target_channel.title}\n"
        f"<b>Format:</b> {format_summary(format_list)}\n"
        f"<b>Start Message ID:</b> {start_id}\n\n"
        f"Click the buttons below to get files for each quality."
    )

    await client.send_message(
        user_id,
        text,
        reply_markup=InlineKeyboardMarkup(quality_buttons),
        disable_web_page_preview=True
    )

    # Clear session data (optional)
    flink_sessions[user_id] = {"format": None, "channel_type": None, "start_msg_id": None}
