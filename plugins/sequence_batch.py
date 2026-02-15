#(©)Codexbotz
# plugins/sequence_batch.py

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from bot import Bot
from config import *
from helper_func import encode, get_message_id, admin, generate_link, get_link_type
from database.database import db

async def choose_channel(client: Client, message: Message, text: str):
    """Let admin choose primary/secondary channel."""
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
    await message.reply(text, reply_markup=keyboard)
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

@Bot.on_message(filters.private & admin & filters.command('seqbatch'))
async def sequence_batch(client: Client, message: Message):
    # Choose channel
    channel_type = await choose_channel(client, message, "📌 Select channel for sequence batch:")
    if channel_type is None:
        return

    if channel_type == "secondary" and not client.secondary_channel:
        await message.reply("❌ Secondary channel not configured.", reply_markup=ReplyKeyboardRemove())
        return

    target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel

    collected_ids = []
    collected_titles = []
    STOP_KEYBOARD = ReplyKeyboardMarkup([["🛑 STOP"]], resize_keyboard=True)

    await message.reply(
        f"📤 Send all messages you want to include in the sequence batch.\n"
        f"For each message, you will be asked to provide a button title.\n\n"
        f"Press 🛑 STOP when you're done.",
        reply_markup=STOP_KEYBOARD
    )

    while True:
        try:
            user_msg = await client.ask(
                chat_id=message.chat.id,
                text=f"⏳ Send a message (forward or link) to add to the sequence.\nCurrently added: {len(collected_ids)}",
                timeout=60
            )
        except asyncio.TimeoutError:
            break

        if user_msg.text and user_msg.text.strip().upper() == "🛑 STOP":
            break

        # Get message ID from DB channel
        msg_id = await get_message_id(client, user_msg)
        if not msg_id:
            await user_msg.reply("❌ This message is not from the DB channel. Please forward a message from the channel or send a valid link.", quote=True)
            continue

        # Verify correct channel
        if user_msg.forward_from_chat:
            if channel_type == "primary" and user_msg.forward_from_chat.id != client.db_channel.id:
                await user_msg.reply(f"❌ This message is not from the {channel_type} DB channel.", quote=True)
                continue
            elif channel_type == "secondary" and (not client.secondary_channel or user_msg.forward_from_chat.id != client.secondary_channel.id):
                await user_msg.reply(f"❌ This message is not from the {channel_type} DB channel.", quote=True)
                continue

        # Ask for button title
        await user_msg.reply("✏️ Now send the button title for this message (or send /skip to use filename).", quote=True)
        try:
            title_msg = await client.ask(
                chat_id=message.chat.id,
                text="Send title or /skip",
                timeout=60
            )
        except asyncio.TimeoutError:
            await message.reply("⏰ Timed out. Operation cancelled.")
            return

        if title_msg.text and title_msg.text == "/skip":
            # Use filename or first 50 chars of caption as default
            msgs = await client.get_messages(target_channel.id, msg_id)
            if msgs and msgs.document:
                title = msgs.document.file_name
            elif msgs and msgs.caption:
                title = msgs.caption[:50]
            else:
                title = f"File {len(collected_ids)+1}"
        else:
            title = title_msg.text

        collected_ids.append(msg_id)
        collected_titles.append(title)
        await message.reply(f"✅ Added message {len(collected_ids)} with title: {title}")

    if not collected_ids:
        await message.reply("❌ No messages were added.", reply_markup=ReplyKeyboardRemove())
        return

    # Save batch to database
    batch_id = await db.create_seq_batch(channel_type, collected_ids, collected_titles)

    # Generate link
    string = f"seq-{batch_id}"
    base64_string = await encode(string)
    link = generate_link(base64_string, client)
    link_type = get_link_type()

    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Share URL", url=f'https://telegram.me/share/url?url={link}')],
        [InlineKeyboardButton("📺 View Channel", url=f"https://t.me/{target_channel.username}" if target_channel.username else f"https://t.me/c/{str(target_channel.id)[4:]}" if str(target_channel.id).startswith('-100') else f"https://t.me/{target_channel.id}")]
    ])

    await message.reply(
        f"<b>✅ Sequence Batch Created Successfully!</b>\n\n"
        f"<b>Channel:</b> {target_channel.title}\n"
        f"<b>Total Files:</b> {len(collected_ids)}\n"
        f"<b>Link Type:</b> {link_type}\n\n"
        f"<code>{link}</code>",
        reply_markup=reply_markup,
        quote=True
    )

    # Preview titles
    title_list = "\n".join([f"{i+1}. {t}" for i, t in enumerate(collected_titles)])
    await message.reply(f"<b>Button Titles:</b>\n{title_list}", quote=True)
