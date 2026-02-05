#(©)CodeFlix_Bots
#rohit_1888 on Tg

import asyncio
from pyrofork import Client, filters
from pyrofork.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, CallbackQuery
from pyrofork.errors import FloodWait
from asyncio import TimeoutError

from config import *
from helper_func import encode, get_message_id, admin, decode

# Default format template
DEFAULT_FORMAT = {
    "360p": 2,
    "480p": 2,
    "720p": 2,
    "1080p": 2,
    "hdrip": 1,
    "4k": 1
}

# Quality emojis and labels
QUALITY_INFO = {
    "360p": {"emoji": "📱", "label": "360P"},
    "480p": {"emoji": "📺", "label": "480P"},
    "720p": {"emoji": "📀", "label": "720P"},
    "1080p": {"emoji": "💿", "label": "1080P"},
    "hdrip": {"emoji": "🌟", "label": "HDRIP"},
    "4k": {"emoji": "🎬", "label": "4K"}
}

class FormatLinkGenerator:
    def __init__(self, client: Client):
        self.client = client
        self.user_data = {}
    
    async def ask_format(self, user_id: int):
        """Ask user to set format"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("• sᴇᴛ ғᴏʀᴍᴀᴛ •", callback_data="set_format")],
            [InlineKeyboardButton("• ᴄᴀɴᴄᴇʟ •", callback_data="cancel_flink")]
        ])
        
        msg = await self.client.send_message(
            chat_id=user_id,
            text="**📝 FORMATTED LINK GENERATOR**\n\n"
                 "This command allows you to generate formatted download links with multiple quality options.\n\n"
                 "**Click below to start:**",
            reply_markup=keyboard
        )
        return msg
    
    async def set_format_step1(self, user_id: int):
        """First step: show current format"""
        format_text = "**📊 Current Format Settings:**\n\n"
        for quality, count in DEFAULT_FORMAT.items():
            info = QUALITY_INFO[quality]
            format_text += f"{info['emoji']} {info['label']} = {count}\n"
        
        format_text += "\n━━━━━━━━━━━━━━\n"
        format_text += "**Format Example:**\n"
        format_text += "360P = 2, 480P = 2, 720P = 2\n1080P = 2, HDRIP = 1, 4K = 1\n\n"
        format_text += "**To modify format, send in this pattern:**\n"
        format_text += "`480P = 1, 720P = 1, 1080P = 1`\n\n"
        format_text += "**To use default format, send:** `DEFAULT`\n"
        format_text += "**To cancel, send:** `CANCEL`"
        
        msg = await self.client.send_message(
            chat_id=user_id,
            text=format_text,
            parse_mode="Markdown"
        )
        
        try:
            response = await self.client.listen(
                chat_id=user_id,
                filters=filters.text,
                timeout=60
            )
            
            if response.text.upper() == "CANCEL":
                await response.reply("❌ Operation cancelled.", reply_markup=ReplyKeyboardRemove())
                return None
            elif response.text.upper() == "DEFAULT":
                await response.reply("✅ Using default format settings.", reply_markup=ReplyKeyboardRemove())
                return DEFAULT_FORMAT.copy()
            else:
                # Parse custom format
                return await self.parse_format(response.text, user_id)
                
        except TimeoutError:
            await self.client.send_message(user_id, "⏰ Timed out. Operation cancelled.")
            return None
    
    async def parse_format(self, format_str: str, user_id: int):
        """Parse custom format string"""
        try:
            format_dict = DEFAULT_FORMAT.copy()
            items = format_str.split(',')
            
            for item in items:
                item = item.strip()
                if '=' in item:
                    key_part, value_part = item.split('=', 1)
                    key = key_part.strip().lower()
                    value = int(value_part.strip())
                    
                    # Map variations
                    key_mapping = {
                        '360p': '360p',
                        '360': '360p',
                        '480p': '480p',
                        '480': '480p',
                        '720p': '720p',
                        '720': '720p',
                        '1080p': '1080p',
                        '1080': '1080p',
                        'hdrip': 'hdrip',
                        'hdr': 'hdrip',
                        '4k': '4k',
                        '2160p': '4k'
                    }
                    
                    found = False
                    for input_key, mapped_key in key_mapping.items():
                        if input_key in key:
                            format_dict[mapped_key] = max(1, value)
                            found = True
                            break
                    
                    if not found:
                        await self.client.send_message(
                            user_id,
                            f"❌ Unknown quality: {key_part.strip()}\n"
                            f"Valid qualities: 360P, 480P, 720P, 1080P, HDRIP, 4K"
                        )
                        return None
            
            # Validate: at least one quality should have files
            total_files = sum(format_dict.values())
            if total_files == 0:
                await self.client.send_message(user_id, "❌ Error: No files specified in format.")
                return None
            
            return format_dict
            
        except Exception as e:
            await self.client.send_message(user_id, f"❌ Error parsing format: {e}\n\nUse format like: `480P = 1, 720P = 1`")
            return None
    
    async def get_starting_message(self, user_id: int, format_dict: dict):
        """Get the starting message from user"""
        total_files = sum(format_dict.values())
        
        await self.client.send_message(
            user_id,
            f"**📤 Send Starting Message**\n\n"
            f"Total files needed: {total_files}\n"
            f"Forward the first message from DB Channel or send post link.\n\n"
            f"**Note:** Files must be in sequence without gaps!\n"
            f"**To cancel:** Type `CANCEL`",
            parse_mode="Markdown"
        )
        
        try:
            response = await self.client.listen(
                chat_id=user_id,
                filters=(filters.forwarded | (filters.text & ~filters.forwarded)),
                timeout=60
            )
            
            if response.text and response.text.upper() == "CANCEL":
                await response.reply("❌ Operation cancelled.")
                return None
            
            # Check which channel it's from
            msg_id = await get_message_id(self.client, response)
            if not msg_id:
                await response.reply("❌ Could not get message ID. Please forward a message from DB Channel.")
                return None
            
            # Determine channel type
            if response.forward_from_chat:
                if response.forward_from_chat.id == self.client.db_channel.id:
                    channel_type = "primary"
                    target_channel = self.client.db_channel
                elif self.client.secondary_channel and response.forward_from_chat.id == self.client.secondary_channel.id:
                    channel_type = "secondary"
                    target_channel = self.client.secondary_channel
                else:
                    await response.reply("❌ Message must be from a DB Channel.")
                    return None
            else:
                # Default to primary if not forwarded
                channel_type = "primary"
                target_channel = self.client.db_channel
            
            return {
                "message": response,
                "msg_id": msg_id,
                "channel_type": channel_type,
                "target_channel": target_channel
            }
            
        except TimeoutError:
            await self.client.send_message(user_id, "⏰ Timed out. Operation cancelled.")
            return None
    
    async def generate_formatted_links(self, user_id: int, start_data: dict, format_dict: dict):
        """Generate formatted links with quality buttons"""
        start_msg = start_data["message"]
        start_id = start_data["msg_id"]
        channel_type = start_data["channel_type"]
        target_channel = start_data["target_channel"]
        
        # Calculate message IDs for each quality
        current_id = start_id
        quality_links = {}
        
        for quality, count in format_dict.items():
            if count > 0:
                if count == 1:
                    # Single file
                    string = f"get-{current_id * abs(target_channel.id)}"
                    if channel_type == "secondary":
                        string = f"sec-{string}"
                    
                    base64_string = await encode(string)
                    link = f"https://t.me/{self.client.username}?start={base64_string}"
                    quality_links[quality] = link
                    current_id += 1
                else:
                    # Multiple files (batch)
                    end_id = current_id + count - 1
                    string = f"get-{current_id * abs(target_channel.id)}-{end_id * abs(target_channel.id)}"
                    if channel_type == "secondary":
                        string = f"sec-{string}"
                    
                    base64_string = await encode(string)
                    link = f"https://t.me/{self.client.username}?start={base64_string}"
                    quality_links[quality] = link
                    current_id += count
        
        # Create formatted message with buttons
        buttons = []
        row = []
        
        for quality, link in quality_links.items():
            info = QUALITY_INFO[quality]
            row.append(InlineKeyboardButton(
                f"{info['emoji']} {info['label']}",
                url=link
            ))
            
            if len(row) == 2:  # 2 buttons per row
                buttons.append(row)
                row = []
        
        if row:  # Add remaining buttons
            buttons.append(row)
        
        # Add share button
        buttons.append([InlineKeyboardButton("🔁 Share All", callback_data="share_formatted")])
        
        keyboard = InlineKeyboardMarkup(buttons)
        
        # Create result message
        result_text = "**✅ FORMATTED LINKS GENERATED**\n\n"
        result_text += f"**Channel:** {target_channel.title}\n"
        result_text += f"**Channel Type:** {channel_type.capitalize()}\n"
        result_text += f"**Starting ID:** {start_id}\n\n"
        result_text += "**Available Qualities:**\n"
        
        for quality, count in format_dict.items():
            if count > 0:
                info = QUALITY_INFO[quality]
                result_text += f"{info['emoji']} {info['label']}: {count} file(s)\n"
        
        result_text += "\n**Note:** These are bot URLs, not permanent links.\n"
        result_text += "Files must be in sequence without deletion."
        
        await start_msg.reply_text(
            result_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        # Store for sharing
        self.user_data[user_id] = {
            "quality_links": quality_links,
            "format_dict": format_dict,
            "channel_title": target_channel.title
        }
        
        return quality_links

# Global generator instance
flink_generator = None

@Bot.on_message(filters.private & admin & filters.command('flink'))
async def flink_command(client: Client, message: Message):
    """Handle /flink command"""
    global flink_generator
    
    if flink_generator is None:
        flink_generator = FormatLinkGenerator(client)
    
    user_id = message.from_user.id
    
    # Initialize user data
    if user_id not in flink_generator.user_data:
        flink_generator.user_data[user_id] = {}
    
    # Show initial menu
    await flink_generator.ask_format(user_id)

@Bot.on_callback_query(filters.regex("^set_format$"))
async def set_format_callback(client: Client, callback_query: CallbackQuery):
    """Handle set format callback"""
    global flink_generator
    
    user_id = callback_query.from_user.id
    
    if flink_generator is None:
        flink_generator = FormatLinkGenerator(client)
    
    await callback_query.answer()
    
    # Ask for format
    format_dict = await flink_generator.set_format_step1(user_id)
    if format_dict is None:
        try:
            await callback_query.message.delete()
        except:
            pass
        return
    
    # Store format
    flink_generator.user_data[user_id]["format_dict"] = format_dict
    
    # Get starting message
    start_data = await flink_generator.get_starting_message(user_id, format_dict)
    if start_data is None:
        try:
            await callback_query.message.delete()
        except:
            pass
        return
    
    # Generate links
    await flink_generator.generate_formatted_links(user_id, start_data, format_dict)
    
    try:
        await callback_query.message.delete()
    except:
        pass

@Bot.on_callback_query(filters.regex("^cancel_flink$"))
async def cancel_flink_callback(client: Client, callback_query: CallbackQuery):
    """Handle cancel callback"""
    await callback_query.answer("Operation cancelled", show_alert=False)
    try:
        await callback_query.message.delete()
    except:
        pass

@Bot.on_callback_query(filters.regex("^share_formatted$"))
async def share_formatted_callback(client: Client, callback_query: CallbackQuery):
    """Handle share formatted links callback"""
    global flink_generator
    
    user_id = callback_query.from_user.id
    
    if flink_generator is None or user_id not in flink_generator.user_data:
        await callback_query.answer("No links to share!", show_alert=True)
        return
    
    data = flink_generator.user_data[user_id]
    quality_links = data.get("quality_links", {})
    format_dict = data.get("format_dict", {})
    channel_title = data.get("channel_title", "Unknown Channel")
    
    if not quality_links:
        await callback_query.answer("No links to share!", show_alert=True)
        return
    
    # Create shareable text
    share_text = f"🎬 **Download Links - {channel_title}**\n\n"
    
    for quality, link in quality_links.items():
        info = QUALITY_INFO[quality]
        count = format_dict.get(quality, 0)
        share_text += f"{info['emoji']} **{info['label']}** ({count} file{'s' if count > 1 else ''}):\n"
        share_text += f"{link}\n\n"
    
    share_text += f"🤖 **Bot:** @{client.username}"
    
    await callback_query.answer()
    await callback_query.message.reply_text(
        "**📤 Share Options:**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Copy Text", callback_data="copy_links_text")],
            [InlineKeyboardButton("📲 Share via Telegram", url=f"https://t.me/share/url?text={share_text}")]
        ])
    )

@Bot.on_callback_query(filters.regex("^copy_links_text$"))
async def copy_links_text_callback(client: Client, callback_query: CallbackQuery):
    """Handle copy links text callback"""
    global flink_generator
    
    user_id = callback_query.from_user.id
    
    if flink_generator is None or user_id not in flink_generator.user_data:
        await callback_query.answer("No links to copy!", show_alert=True)
        return
    
    data = flink_generator.user_data[user_id]
    quality_links = data.get("quality_links", {})
    
    if not quality_links:
        await callback_query.answer("No links to copy!", show_alert=True)
        return
    
    # Create text to copy
    copy_text = "**Download Links:**\n\n"
    for quality, link in quality_links.items():
        info = QUALITY_INFO[quality]
        copy_text += f"{info['label']}: {link}\n"
    
    # Show the text for copying
    await callback_query.answer("Text ready for copying", show_alert=False)
    await callback_query.message.reply_text(
        f"📋 **Copy the links below:**\n\n{copy_text}",
        parse_mode="Markdown"
    )

# Add help command for flink
FLINK_HELP_TEXT = """
**📖 /flink Command Help**

**Purpose:**
Generate formatted download links with multiple quality options (360p, 480p, 720p, 1080p, HDRIP, 4K)

**Usage:**
1. Send `/flink` to start
2. Click "Set Format" button
3. Set format (default or custom)
4. Send starting message from DB channel
5. Get formatted links with quality buttons

**Format Examples:**
- Default: 360P=2, 480P=2, 720P=2, 1080P=2, HDRIP=1, 4K=1
- Custom: `480P = 1, 720P = 1, 1080P = 1`

**Important Notes:**
- Files must be in sequence without gaps
- Only admin can use this command
- Generated links are bot URLs, not permanent
- Maximum 6 qualities per message

**Admin Only:** ✅
"""

@Bot.on_message(filters.private & admin & filters.command('help_flink'))
async def help_flink_command(client: Client, message: Message):
    """Show help for flink command"""
    await message.reply_text(FLINK_HELP_TEXT, parse_mode="Markdown")
