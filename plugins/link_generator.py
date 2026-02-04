#(©)Codexbotz

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from bot import Bot
from pyrogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
from asyncio import TimeoutError
from helper_func import encode, get_message_id, admin, create_formatted_links
from config import PERMANENT_LINKS, BLOGSPOT_URL, BLOGSPOT_PARAM

def generate_link(base64_string, client):
    """Generate link - permanent for batch/genlink, direct for channel_post"""
    if PERMANENT_LINKS and BLOGSPOT_URL:
        return f"{BLOGSPOT_URL}?{BLOGSPOT_PARAM}={base64_string}"
    else:
        return f"https://t.me/{client.username}?start={base64_string}"

def get_link_type():
    """Get link type description"""
    if PERMANENT_LINKS and BLOGSPOT_URL:
        return "Permanent"
    else:
        return "Direct"

async def choose_channel(client: Client, message: Message, text: str):
    """Let admin choose which channel to use"""
    if not client.secondary_channel:
        return "primary"  # Only primary available
    
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
            
    except TimeoutError:
        await message.reply("⏰ Timed out. Operation cancelled.", reply_markup=ReplyKeyboardRemove())
        return None

@Bot.on_message(filters.private & admin & filters.command('batch'))
async def batch(client: Client, message: Message):
    # Choose channel
    channel_type = await choose_channel(client, message, "📌 Select channel for batch operation:")
    if channel_type is None:
        return
    
    if channel_type == "secondary" and not client.secondary_channel:
        await message.reply("❌ Secondary channel not configured.", reply_markup=ReplyKeyboardRemove())
        return
    
    target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel
    
    # Get first message
    while True:
        try:
            first_message = await client.ask(
                text=f"📤 Forward the First Message from {channel_type.capitalize()} DB Channel (with Quotes)..\n\nor Send the DB Channel Post Link",
                chat_id=message.from_user.id,
                filters=(filters.forwarded | (filters.text & ~filters.forwarded)),
                timeout=60
            )
        except TimeoutError:
            await message.reply("⏰ Operation timed out.", reply_markup=ReplyKeyboardRemove())
            return
        
        f_msg_id = await get_message_id(client, first_message)
        if f_msg_id:
            # Check if forwarded from correct channel
            if first_message.forward_from_chat:
                if channel_type == "primary" and first_message.forward_from_chat.id == client.db_channel.id:
                    break
                elif channel_type == "secondary" and first_message.forward_from_chat.id == client.secondary_channel.id:
                    break
            
            await first_message.reply(f"❌ Error\n\nThis message is not from {channel_type} DB Channel", quote=True)
        else:
            await first_message.reply(f"❌ Error\n\nCould not get message ID from {channel_type} channel", quote=True)

    # Get last message
    while True:
        try:
            second_message = await client.ask(
                text=f"📤 Forward the Last Message from {channel_type.capitalize()} DB Channel (with Quotes)..\nor Send the DB Channel Post link",
                chat_id=message.from_user.id,
                filters=(filters.forwarded | (filters.text & ~filters.forwarded)),
                timeout=60
            )
        except TimeoutError:
            await message.reply("⏰ Operation timed out.", reply_markup=ReplyKeyboardRemove())
            return
        
        s_msg_id = await get_message_id(client, second_message)
        if s_msg_id:
            # Check if forwarded from correct channel
            if second_message.forward_from_chat:
                if channel_type == "primary" and second_message.forward_from_chat.id == client.db_channel.id:
                    break
                elif channel_type == "secondary" and second_message.forward_from_chat.id == client.secondary_channel.id:
                    break
            
            await second_message.reply(f"❌ Error\n\nThis message is not from {channel_type} DB Channel", quote=True)
        else:
            await second_message.reply(f"❌ Error\n\nCould not get message ID from {channel_type} channel", quote=True)

    # Create link
    channel_multiplier = abs(target_channel.id)
    string = f"get-{f_msg_id * channel_multiplier}-{s_msg_id * channel_multiplier}"
    
    # Add prefix for secondary channel
    if channel_type == "secondary":
        string = f"sec-{string}"
    
    base64_string = await encode(string)
    link = generate_link(base64_string, client)
    link_type = get_link_type()
    
    # Show link type info
    if link_type == "Permanent":
        link_info = "🔗 **Permanent Link** - Will work even if bot gets banned"
    else:
        link_info = "🤖 **Direct Link** - Will stop working if bot gets banned"
    
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Share URL", url=f'https://telegram.me/share/url?url={link}')],
        [InlineKeyboardButton("📺 View Channel", url=f"https://t.me/{target_channel.username}" if target_channel.username else f"https://t.me/c/{str(target_channel.id)[4:]}" if str(target_channel.id).startswith('-100') else f"https://t.me/{target_channel.id}")]
    ])
    
    await second_message.reply_text(
        f"<b>✅ {channel_type.capitalize()} Channel Batch Link Created</b>\n\n"
        f"<b>{link_info}</b>\n\n"
        f"<b>Channel:</b> {target_channel.title}\n"
        f"<b>From ID:</b> {f_msg_id}\n"
        f"<b>To ID:</b> {s_msg_id}\n"
        f"<b>Channel Type:</b> {channel_type.capitalize()}\n\n"
        f"<code>{link}</code>",
        quote=True,
        reply_markup=reply_markup
    )
    
    await message.reply("✅ Batch link created!", reply_markup=ReplyKeyboardRemove())

@Bot.on_message(filters.private & admin & filters.command('genlink'))
async def link_generator(client: Client, message: Message):
    # Choose channel
    channel_type = await choose_channel(client, message, "📌 Select channel for single link:")
    if channel_type is None:
        return
    
    if channel_type == "secondary" and not client.secondary_channel:
        await message.reply("❌ Secondary channel not configured.", reply_markup=ReplyKeyboardRemove())
        return
    
    target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel
    
    # Get message
    while True:
        try:
            channel_message = await client.ask(
                text=f"📤 Forward Message from {channel_type.capitalize()} DB Channel (with Quotes)..\nor Send the DB Channel Post link",
                chat_id=message.from_user.id,
                filters=(filters.forwarded | (filters.text & ~filters.forwarded)),
                timeout=60
            )
        except TimeoutError:
            await message.reply("⏰ Operation timed out.", reply_markup=ReplyKeyboardRemove())
            return
        
        msg_id = await get_message_id(client, channel_message)
        if msg_id:
            # Check if forwarded from correct channel
            if channel_message.forward_from_chat:
                if channel_type == "primary" and channel_message.forward_from_chat.id == client.db_channel.id:
                    break
                elif channel_type == "secondary" and channel_message.forward_from_chat.id == client.secondary_channel.id:
                    break
            
            await channel_message.reply(f"❌ Error\n\nThis message is not from {channel_type} DB Channel", quote=True)
        else:
            await channel_message.reply(f"❌ Error\n\nCould not get message ID from {channel_type} channel", quote=True)

    # Create link
    channel_multiplier = abs(target_channel.id)
    string = f"get-{msg_id * channel_multiplier}"
    
    # Add prefix for secondary channel
    if channel_type == "secondary":
        string = f"sec-{string}"
    
    base64_string = await encode(string)
    link = generate_link(base64_string, client)
    link_type = get_link_type()
    
    # Show link type info
    if link_type == "Permanent":
        link_info = "🔗 **Permanent Link** - Will work even if bot gets banned"
    else:
        link_info = "🤖 **Direct Link** - Will stop working if bot gets banned"
    
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Share URL", url=f'https://telegram.me/share/url?url={link}')],
        [InlineKeyboardButton("📺 View Channel", url=f"https://t.me/{target_channel.username}" if target_channel.username else f"https://t.me/c/{str(target_channel.id)[4:]}" if str(target_channel.id).startswith('-100') else f"https://t.me/{target_channel.id}")]
    ])
    
    await channel_message.reply_text(
        f"<b>✅ {channel_type.capitalize()} Channel Link Created</b>\n\n"
        f"<b>{link_info}</b>\n\n"
        f"<b>Channel:</b> {target_channel.title}\n"
        f"<b>Message ID:</b> {msg_id}\n"
        f"<b>Channel Type:</b> {channel_type.capitalize()}\n\n"
        f"<code>{link}</code>",
        quote=True,
        reply_markup=reply_markup
    )
    
    await message.reply("✅ Single link created!", reply_markup=ReplyKeyboardRemove())

@Bot.on_message(filters.private & admin & filters.command("custom_batch"))
async def custom_batch(client: Client, message: Message):
    # Choose channel
    channel_type = await choose_channel(client, message, "📌 Select channel for custom batch:")
    if channel_type is None:
        return
    
    if channel_type == "secondary" and not client.secondary_channel:
        await message.reply("❌ Secondary channel not configured.", reply_markup=ReplyKeyboardRemove())
        return
    
    target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel
    
    collected = []
    STOP_KEYBOARD = ReplyKeyboardMarkup([["🛑 STOP"]], resize_keyboard=True)

    await message.reply(
        f"📤 Send all messages you want to include in {channel_type} channel batch.\n\nPress 🛑 STOP when you're done.",
        reply_markup=STOP_KEYBOARD
    )

    while True:
        try:
            user_msg = await client.ask(
                chat_id=message.chat.id,
                text=f"⏳ Waiting for files/messages...\nPress 🛑 STOP to finish. ({len(collected)} collected)",
                timeout=60
            )
        except TimeoutError:
            break

        if user_msg.text and user_msg.text.strip().upper() == "🛑 STOP":
            break

        try:
            sent = await user_msg.copy(target_channel.id, disable_notification=True)
            collected.append(sent.id)
            await message.reply(f"✅ Added message #{len(collected)} to {channel_type} channel")
        except Exception as e:
            await message.reply(f"❌ Failed to store a message:\n<code>{e}</code>")
            continue

    await message.reply("✅ Batch collection complete.", reply_markup=ReplyKeyboardRemove())

    if not collected:
        await message.reply("❌ No messages were added to batch.")
        return

    # Create link
    channel_multiplier = abs(target_channel.id)
    start_id = collected[0] * channel_multiplier
    end_id = collected[-1] * channel_multiplier
    string = f"get-{start_id}-{end_id}"
    
    # Add prefix for secondary channel
    if channel_type == "secondary":
        string = f"sec-{string}"
    
    base64_string = await encode(string)
    link = generate_link(base64_string, client)
    link_type = get_link_type()
    
    # Show link type info
    if link_type == "Permanent":
        link_info = "🔗 **Permanent Link** - Will work even if bot gets banned"
    else:
        link_info = "🤖 **Direct Link** - Will stop working if bot gets banned"

    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Share URL", url=f'https://telegram.me/share/url?url={link}')],
        [InlineKeyboardButton("📺 View Channel", url=f"https://t.me/{target_channel.username}" if target_channel.username else f"https://t.me/c/{str(target_channel.id)[4:]}" if str(target_channel.id).startswith('-100') else f"https://t.me/{target_channel.id}")]
    ])
    
    await message.reply(
        f"<b>✅ {channel_type.capitalize()} Channel Custom Batch Link Created</b>\n\n"
        f"<b>{link_info}</b>\n\n"
        f"<b>Channel:</b> {target_channel.title}\n"
        f"<b>Total Files:</b> {len(collected)}\n"
        f"<b>From ID:</b> {collected[0]}\n"
        f"<b>To ID:</b> {collected[-1]}\n"
        f"<b>Channel Type:</b> {channel_type.capitalize()}\n\n"
        f"<code>{link}</code>",
        reply_markup=reply_markup
    )

# ===== FORMATTED LINKS COMMAND (/flink) =====

QUALITIES = ["360P", "480P", "720P", "1080P", "HDRIP", "4K"]

class FormatSession:
    def __init__(self, user_id):
        self.user_id = user_id
        self.quality_counts = {}
        self.message_ids = []
        self.channel_type = "primary"
        self.state = "waiting_format"

format_sessions = {}

def parse_format_input(text):
    """Parse format input like: 480P = 2, 720P = 2, 1080P = 1"""
    quality_counts = {}
    text = text.upper().strip()
    parts = text.split(',')
    
    for part in parts:
        part = part.strip()
        if '=' in part:
            quality, count_str = part.split('=', 1)
            quality = quality.strip()
            count_str = count_str.strip()
            
            if quality in QUALITIES:
                try:
                    count = int(count_str)
                    if count > 0:
                        quality_counts[quality] = count
                except ValueError:
                    continue
    
    return quality_counts

@Bot.on_message(filters.private & admin & filters.command('flink'))
async def formatted_link_command(client: Client, message: Message):
    """Start formatted link generation process"""
    
    # Clean old session
    if message.from_user.id in format_sessions:
        del format_sessions[message.from_user.id]
    
    # Choose channel
    channel_type = await choose_channel(client, message, "📌 Select channel for formatted links:")
    if channel_type is None:
        return
    
    if channel_type == "secondary" and not client.secondary_channel:
        await message.reply("❌ Secondary channel not configured.", reply_markup=ReplyKeyboardRemove())
        return
    
    # Create session
    session = FormatSession(message.from_user.id)
    session.channel_type = channel_type
    format_sessions[message.from_user.id] = session
    
    # Instructions
    instructions = (
        "📋 **Formatted Link Generator**\n\n"
        "**Available Qualities:** 360P, 480P, 720P, 1080P, HDRIP, 4K\n\n"
        "**Format Example:**\n"
        "`480P = 2, 720P = 2, 1080P = 1`\n\n"
        "This means:\n"
        "• 2 files for 480P quality\n"
        "• 2 files for 720P quality\n"
        "• 1 file for 1080P quality\n\n"
        "**Send your format now or CANCEL to cancel:**"
    )
    
    await message.reply(instructions, reply_markup=ReplyKeyboardRemove())
    
    # Wait for format input
    try:
        format_msg = await client.ask(
            chat_id=message.chat.id,
            text="⏳ Waiting for format...",
            timeout=60
        )
    except TimeoutError:
        if message.from_user.id in format_sessions:
            del format_sessions[message.from_user.id]
        await message.reply("⏰ Operation timed out.", reply_markup=ReplyKeyboardRemove())
        return
    
    if format_msg.text.upper() == "CANCEL":
        if message.from_user.id in format_sessions:
            del format_sessions[message.from_user.id]
        await message.reply("❌ Operation cancelled.", reply_markup=ReplyKeyboardRemove())
        return
    
    # Parse format
    quality_counts = parse_format_input(format_msg.text)
    
    if not quality_counts:
        if message.from_user.id in format_sessions:
            del format_sessions[message.from_user.id]
        await message.reply(
            "❌ Invalid format!\n\n"
            "Please use format like:\n"
            "`480P = 2, 720P = 2, 1080P = 1`\n\n"
            "Use /flink to try again.",
            reply_markup=ReplyKeyboardRemove()
        )
        return
    
    session.quality_counts = quality_counts
    session.state = "waiting_messages"
    
    # Calculate total files needed
    total_files = sum(quality_counts.values())
    
    # Determine target channel
    target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel
    channel_name = "Secondary" if channel_type == "secondary" else "Primary"
    
    await message.reply(
        f"✅ **Format Set!**\n\n"
        f"**Channel:** {channel_name} Channel\n"
        f"**Total Files Needed:** {total_files}\n\n"
        f"**Quality Distribution:**\n" +
        "\n".join([f"• {quality}: {count} file(s)" for quality, count in quality_counts.items()]) +
        f"\n\n📤 **Now forward {total_files} message(s) from {channel_name} DB Channel IN SEQUENCE**"
    )
    
    # Collect messages
    collected_ids = []
    
    while len(collected_ids) < total_files:
        try:
            user_msg = await client.ask(
                chat_id=message.chat.id,
                text=f"📥 **Collecting files...**\n"
                     f"Collected: {len(collected_ids)}/{total_files}\n"
                     f"Remaining: {total_files - len(collected_ids)}\n\n"
                     f"Forward messages one by one or send CANCEL to stop.",
                timeout=60
            )
        except TimeoutError:
            if message.from_user.id in format_sessions:
                del format_sessions[message.from_user.id]
            await message.reply("⏰ Operation timed out.", reply_markup=ReplyKeyboardRemove())
            return
        
        if user_msg.text and user_msg.text.upper() == "CANCEL":
            if message.from_user.id in format_sessions:
                del format_sessions[message.from_user.id]
            await message.reply("❌ Operation cancelled.", reply_markup=ReplyKeyboardRemove())
            return
        
        # Get message ID
        msg_id = await get_message_id(client, user_msg)
        
        if msg_id:
            # Verify it's from the correct channel
            if user_msg.forward_from_chat:
                if channel_type == "primary" and user_msg.forward_from_chat.id == client.db_channel.id:
                    collected_ids.append(msg_id)
                    await message.reply(f"✅ Added file {len(collected_ids)}/{total_files}")
                elif channel_type == "secondary" and client.secondary_channel and user_msg.forward_from_chat.id == client.secondary_channel.id:
                    collected_ids.append(msg_id)
                    await message.reply(f"✅ Added file {len(collected_ids)}/{total_files}")
                else:
                    await message.reply("❌ This message is not from the selected DB channel!")
            else:
                await message.reply("❌ Please forward messages from the DB channel!")
        else:
            await message.reply("❌ Could not get message ID. Please forward proper messages!")
    
    # Store collected IDs and generate links
    session.message_ids = collected_ids
    
    # Generate formatted links
    formatted_links = await create_formatted_links(
        client,
        collected_ids,
        "get-",
        quality_counts,
        channel_type
    )
    
    # Prepare output
    link_type = "Permanent" if (PERMANENT_LINKS and BLOGSPOT_URL) else "Direct"
    
    message_text = (
        f"✅ **{channel_name} Channel Formatted Links Created**\n\n"
        f"**Link Type:** {link_type} Link\n"
        f"**Channel:** {target_channel.title}\n"
        f"**Total Files:** {len(collected_ids)}\n"
        f"**Channel Type:** {channel_type.capitalize()}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
    )
    
    # Add quality-wise links
    buttons = []
    
    for quality, data in formatted_links.items():
        message_text += f"\n**{quality}** ({data['count']} file(s)):\n"
        message_text += f"`{data['link']}`\n"
        
        # Add button for each quality
        buttons.append([InlineKeyboardButton(f"📥 {quality}", url=data['link'])])
    
    # Add share and view channel buttons
    if formatted_links:
        first_link = list(formatted_links.values())[0]['link']
        buttons.append([
            InlineKeyboardButton("🔁 Share All", url=f'https://telegram.me/share/url?url={first_link}&text=Download%20Links'),
            InlineKeyboardButton("📺 View Channel", url=f"https://t.me/{target_channel.username}" if target_channel.username else f"https://t.me/c/{str(target_channel.id)[4:]}" if str(target_channel.id).startswith('-100') else f"https://t.me/{target_channel.id}")
        ])
    
    reply_markup = InlineKeyboardMarkup(buttons)
    
    # Send the formatted message
    await message.reply(
        message_text,
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )
    
    # Clean up session
    if message.from_user.id in format_sessions:
        del format_sessions[message.from_user.id]
    
    await message.reply("✅ Formatted links created successfully!", reply_markup=ReplyKeyboardRemove())

# Helper command to show current format sessions
@Bot.on_message(filters.private & admin & filters.command('format_status'))
async def format_status_command(client: Client, message: Message):
    """Show active format sessions"""
    if not format_sessions:
        await message.reply("📭 No active format sessions.")
        return
    
    status_text = "📊 **Active Format Sessions:**\n\n"
    
    for user_id, session in format_sessions.items():
        try:
            user = await client.get_users(user_id)
            username = f"@{user.username}" if user.username else user.first_name
        except:
            username = f"User {user_id}"
        
        status_text += f"👤 **User:** {username}\n"
        status_text += f"📁 **State:** {session.state}\n"
        
        if session.quality_counts:
            status_text += f"📋 **Format:** {', '.join([f'{q}={c}' for q, c in session.quality_counts.items()])}\n"
        
        if session.message_ids:
            status_text += f"📥 **Files Collected:** {len(session.message_ids)}\n"
        
        status_text += "━━━━━━━━━━━━━━\n"
    
    await message.reply(status_text)

# Clean up any leftover sessions
@Bot.on_message(filters.command('clean_format') & filters.private & admin)
async def clean_format_command(client: Client, message: Message):
    """Clean all format sessions"""
    count = len(format_sessions)
    format_sessions.clear()
    await message.reply(f"🧹 Cleared {count} format session(s).")

# ===== ADD TEST COMMAND TO VERIFY FILE IS WORKING =====
@Bot.on_message(filters.command('linktest') & filters.private)
async def link_test_command(client: Client, message: Message):
    await message.reply("✅ link_generator.py is loaded and working!")
