#(©)Codexbotz

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from bot import Bot
from asyncio import TimeoutError
from helper_func import encode, get_message_id, admin, create_formatted_links
from config import PERMANENT_LINKS, BLOGSPOT_URL, BLOGSPOT_PARAM

# ===== SIMPLE HELPER FUNCTIONS =====

def generate_link(base64_string, client):
    if PERMANENT_LINKS and BLOGSPOT_URL:
        return f"{BLOGSPOT_URL}?{BLOGSPOT_PARAM}={base64_string}"
    else:
        return f"https://t.me/{client.username}?start={base64_string}"

async def choose_channel(client: Client, message: Message, text: str):
    if not client.secondary_channel:
        return "primary"
    
    keyboard = ReplyKeyboardMarkup([
        ["📌 Primary Channel"],
        ["📂 Secondary Channel"],
        ["❌ Cancel"]
    ], resize_keyboard=True)
    
    await message.reply(text, reply_markup=keyboard)
    
    try:
        response = await client.listen(
            chat_id=message.chat.id,
            filters=filters.text & filters.regex(r"^(📌 Primary Channel|📂 Secondary Channel|❌ Cancel)$"),
            timeout=30
        )
        
        if response.text == "❌ Cancel":
            await message.reply("❌ Cancelled.", reply_markup=ReplyKeyboardRemove())
            return None
        elif response.text == "📂 Secondary Channel":
            return "secondary"
        else:
            return "primary"
    except TimeoutError:
        await message.reply("⏰ Timeout.", reply_markup=ReplyKeyboardRemove())
        return None

# ===== /flink COMMAND (MINIMAL VERSION) =====

@Bot.on_message(filters.private & admin & filters.command('flink'))
async def simple_flink(client: Client, message: Message):
    # Step 1: Choose channel
    channel_type = await choose_channel(client, message, "Select channel for formatted links:")
    if channel_type is None:
        return
    
    if channel_type == "secondary" and not client.secondary_channel:
        await message.reply("❌ No secondary channel.", reply_markup=ReplyKeyboardRemove())
        return
    
    target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel
    channel_name = "Secondary" if channel_type == "secondary" else "Primary"
    
    # Step 2: Ask for format
    await message.reply(
        "📝 **Send format:**\n"
        "Example: `480P = 2, 720P = 2, 1080P = 1`\n"
        "Type CANCEL to cancel.",
        reply_markup=ReplyKeyboardRemove()
    )
    
    try:
        format_msg = await client.ask(
            chat_id=message.chat.id,
            text="⏳ Waiting...",
            timeout=60
        )
    except TimeoutError:
        await message.reply("⏰ Timeout.")
        return
    
    if format_msg.text.upper() == "CANCEL":
        await message.reply("❌ Cancelled.")
        return
    
    # Parse format
    quality_counts = {}
    text = format_msg.text.upper().strip()
    
    for part in text.split(','):
        part = part.strip()
        if '=' in part:
            quality, count = part.split('=', 1)
            quality = quality.strip()
            count = count.strip()
            if quality in ["360P", "480P", "720P", "1080P", "HDRIP", "4K"]:
                try:
                    quality_counts[quality] = int(count)
                except:
                    pass
    
    if not quality_counts:
        await message.reply("❌ Invalid format!")
        return
    
    # Step 3: Collect files
    total_files = sum(quality_counts.values())
    await message.reply(f"📥 Need {total_files} files. Forward them one by one from {channel_name} channel.")
    
    collected_ids = []
    
    for i in range(total_files):
        try:
            user_msg = await client.ask(
                chat_id=message.chat.id,
                text=f"File {i+1}/{total_files}:",
                timeout=60
            )
        except TimeoutError:
            await message.reply("⏰ Timeout.")
            return
        
        msg_id = await get_message_id(client, user_msg)
        if msg_id:
            collected_ids.append(msg_id)
            await message.reply(f"✅ Added {i+1}/{total_files}")
        else:
            await message.reply("❌ Invalid file. Try again.")
            i -= 1
    
    # Step 4: Generate links
    formatted_links = await create_formatted_links(client, collected_ids, quality_counts, channel_type)
    
    # Step 5: Show results
    buttons = []
    result_text = f"✅ **{channel_name} Channel Links**\n\n"
    
    for quality, link in formatted_links.items():
        result_text += f"**{quality}:** `{link}`\n"
        buttons.append([InlineKeyboardButton(f"📥 {quality}", url=link)])
    
    # Add share button
    if formatted_links:
        first_link = list(formatted_links.values())[0]
        buttons.append([InlineKeyboardButton("🔁 Share", url=f'https://telegram.me/share/url?url={first_link}')])
    
    await message.reply(
        result_text,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )

# ===== KEEP YOUR EXISTING COMMANDS BELOW =====
# (Keep your existing /batch, /genlink, /custom_batch code here)
# Just add the above /flink handler at the TOP

@Bot.on_message(filters.private & admin & filters.command('batch'))
async def batch(client: Client, message: Message):
    # Your existing batch code...
    pass

@Bot.on_message(filters.private & admin & filters.command('genlink'))
async def link_generator(client: Client, message: Message):
    # Your existing genlink code...
    pass

@Bot.on_message(filters.private & admin & filters.command("custom_batch"))
async def custom_batch(client: Client, message: Message):
    # Your existing custom_batch code...
    pass

@Bot.on_message(filters.command('linktest') & filters.private)
async def link_test_command(client: Client, message: Message):
    await message.reply("✅ Working!")
