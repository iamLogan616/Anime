# Don't Remove Credit @Yeon_Bots
# Ask Doubt on telegram @MrXeonTg
# Copyright (C) 2026 by Yeon-Bots
# ===============================[ ᴍᴀᴅᴇ ᴡɪᴛʜ 🤍 ʙʏ @YEON_bots × Copyright (C) 2026 by Yeon-Bots@Github, < https://github.com/MrYKTG>. Copyright (C) 2026 by Yeon-Bots@Telegram, < https://t.me/Yeon_Bots >.  ]==============================
# ᴅᴏɴ'ᴛ sᴇʟʟ • ᴅᴏɴ'ᴛ ᴄʟᴀɪᴍ ᴀs ʏᴏᴜʀs • sᴜᴘᴘᴏʀᴛ: t.me/Yeon_bots • ʀᴇᴘᴏʀᴛ ʙᴜɢs: @MrXeontg
# ==================================================================================================
# All rights reserved.
#

import asyncio
import os
import random
import sys
import time
import re
import logging  # added for logging
from datetime import datetime, timedelta
from pyrogram import Client, filters, __version__
from pyrogram.enums import ParseMode, ChatAction
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, ChatInviteLink, ChatPrivileges
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated, UserNotParticipant
from bot import Bot
from config import *
from helper_func import *
from database.database import *
from plugins.link_generator import generate_link  # for flink links
from plugins.flink import flink_sessions       # session guard for flink

# Set up logger
LOGGER = logging.getLogger(__name__)

BAN_SUPPORT = f"{BAN_SUPPORT}"

# ====================== FLINK HELPER ======================
def decode_format(encoded):
    """Decode format string like '360P2_480P2_720P2' back to list of (quality, count)."""
    result = []
    parts = encoded.split("_")
    for part in parts:
        match = re.match(r'^([A-Za-z0-9]+)(\d+)$', part)
        if match:
            quality = match.group(1)
            count = int(match.group(2))
            result.append((quality, count))
    return result

# ====================== START COMMAND ======================
@Bot.on_message(filters.command('start') & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id

    # --- Flink session guard: prevent /start from interrupting active flink process ---
    if user_id in flink_sessions and flink_sessions[user_id].get("in_progress"):
        await message.reply("⏳ Please complete the current flink process first (type CANCEL if needed).")
        return

    # Check if user is banned
    banned_users = await db.get_ban_users()
    if user_id in banned_users:
        return await message.reply_text(
            "<b>⛔️ You are Bᴀɴɴᴇᴅ from using this bot.</b>\n\n"
            "<i>Contact support if you think this is a mistake.</i>",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Contact Support", url=BAN_SUPPORT)]]
            )
        )
    # ✅ Check Force Subscription
    if not await is_subscribed(client, user_id):
        return await not_joined(client, message)

    # File auto-delete time in seconds
    FILE_AUTO_DELETE = await db.get_del_timer()

    # Add user if not already present
    if not await db.present_user(user_id):
        try:
            await db.add_user(user_id)
        except:
            pass

    # Handle deep-linked messages
    text = message.text
    if len(text) > 7:
        try:
            base64_string = text.split(" ", 1)[1]
        except IndexError:
            return

        string = await decode(base64_string)

        # ========== DEBUG LOG: see what string we got ==========
        LOGGER.info(f"🔍 Decoded start string for user {user_id}: {string}")

        # ========== FLINK (Formatted Link) Handler ==========
        if string.startswith("flink-"):
            # Format: flink-{channel_code}-{start_id}-{format_encoded}
            parts = string.split("-")
            if len(parts) != 4:
                return await message.reply("❌ Invalid formatted link.")

            _, channel_code, start_id_str, format_encoded = parts
            channel_type = "primary" if channel_code == "p" else "secondary"
            if channel_type == "secondary" and not client.secondary_channel:
                return await message.reply("⚠️ Secondary channel not available. Please contact admin.")
            target_channel = client.secondary_channel if channel_type == "secondary" else client.db_channel

            try:
                start_id = int(start_id_str)
            except ValueError:
                return await message.reply("❌ Invalid message ID in link.")

            format_list = decode_format(format_encoded)
            if not format_list:
                return await message.reply("❌ Invalid format in link.")

            # Calculate total messages needed
            total_needed = sum(count for _, count in format_list)
            end_id = start_id + total_needed - 1

            # Fetch messages
            try:
                messages = await get_messages(client, list(range(start_id, end_id + 1)), channel=channel_type)
            except Exception as e:
                return await message.reply(f"❌ Failed to fetch messages: {e}")

            if len(messages) < total_needed:
                return await message.reply("❌ Not enough messages available. The link may be expired.")

            # Build quality buttons
            multiplier = abs(target_channel.id)
            current_index = 0
            quality_buttons = []

            for quality, count in format_list:
                if count == 0:
                    continue
                msg_ids = [msg.id for msg in messages[current_index:current_index + count]]
                if not msg_ids:
                    continue
                # Create batch link for this quality
                start_id_mult = msg_ids[0] * multiplier
                end_id_mult = msg_ids[-1] * multiplier
                string_batch = f"get-{start_id_mult}-{end_id_mult}"
                if channel_type == "secondary":
                    string_batch = f"sec-{string_batch}"
                batch_base64 = await encode(string_batch)
                batch_link = generate_link(batch_base64, client)
                quality_buttons.append([InlineKeyboardButton(text=quality, url=batch_link)])
                current_index += count

            if not quality_buttons:
                return await message.reply("❌ No quality buttons could be generated.")

            text = (
                f"<b>📥 Select Quality</b>\n\n"
                f"<b>Channel:</b> {target_channel.title}\n"
                f"Click a button below to get the files for that quality."
            )
            await message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(quality_buttons),
                disable_web_page_preview=True
            )
            return

        # ========== Existing Secondary/Primary Link Handlers ==========
        if string.startswith("sec-"):
            channel_type = "secondary"
            string = string[4:]
            if not client.secondary_channel:
                return await message.reply("⚠️ Secondary channel not available. Please contact admin.")
            target_channel = client.secondary_channel
        else:
            channel_type = "primary"
            target_channel = client.db_channel

        argument = string.split("-")

        ids = []
        if len(argument) == 3:  # Batch: get-start-end
            try:
                start = int(int(argument[1]) / abs(target_channel.id))
                end = int(int(argument[2]) / abs(target_channel.id))
                ids = range(start, end + 1) if start <= end else list(range(start, end - 1, -1))
            except Exception as e:
                print(f"Error decoding batch IDs: {e}")
                return await message.reply("❌ Invalid link format.")

        elif len(argument) == 2:  # Single: get-id
            try:
                ids = [int(int(argument[1]) / abs(target_channel.id))]
            except Exception as e:
                print(f"Error decoding single ID: {e}")
                return await message.reply("❌ Invalid link format.")

        temp_msg = await message.reply(f"<b>📥 Fetching from {channel_type} channel...</b>")

        try:
            messages = await get_messages(client, ids, channel=channel_type)
            if not messages:
                await temp_msg.delete()
                return await message.reply_text("❌ No files found. Link may be expired or invalid.")
        except Exception as e:
            await temp_msg.delete()
            await message.reply_text("❌ Something went wrong!")
            print(f"Error getting messages: {e}")
            return

        await temp_msg.delete()

        codeflix_msgs = []
        for msg in messages:
            if not msg or not hasattr(msg, 'document'):
                continue

            caption = (CUSTOM_CAPTION.format(previouscaption="" if not msg.caption else msg.caption.html,
                                             filename=msg.document.file_name) if bool(CUSTOM_CAPTION) and bool(msg.document)
                       else ("" if not msg.caption else msg.caption.html))

            reply_markup = msg.reply_markup if DISABLE_CHANNEL_BUTTON else None

            try:
                copied_msg = await msg.copy(chat_id=message.from_user.id, caption=caption, parse_mode=ParseMode.HTML,
                                            reply_markup=reply_markup, protect_content=PROTECT_CONTENT)
                codeflix_msgs.append(copied_msg)
            except FloodWait as e:
                await asyncio.sleep(e.x)
                copied_msg = await msg.copy(chat_id=message.from_user.id, caption=caption, parse_mode=ParseMode.HTML,
                                            reply_markup=reply_markup, protect_content=PROTECT_CONTENT)
                codeflix_msgs.append(copied_msg)
            except Exception as e:
                print(f"Failed to send message: {e}")
                pass

        if not codeflix_msgs:
            return await message.reply("❌ No files could be sent. Please try again.")

        if FILE_AUTO_DELETE > 0:
            notification_msg = await message.reply(
                f"<b>⏳ This file will be deleted in {get_exp_time(FILE_AUTO_DELETE)}. Please save or forward it to your saved messages before it gets deleted.</b>"
            )

            await asyncio.sleep(FILE_AUTO_DELETE)

            for snt_msg in codeflix_msgs:
                if snt_msg:
                    try:
                        await snt_msg.delete()
                    except Exception as e:
                        print(f"Error deleting message {snt_msg.id}: {e}")

            try:
                await notification_msg.edit(
                    "<b><i>⏰ Time is over\nYour files has been deleted ✅</i></b>"
                )
            except Exception as e:
                print(f"Error updating notification message: {e}")

    else:
        # Normal start command (no deep link)
        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("• ᴀʙᴏᴜᴛ", callback_data="about"),
                    InlineKeyboardButton('ʜᴇʟᴘ •', callback_data="help")
                ]
            ]
        )
        await message.reply_photo(
            photo=START_PIC,
            caption=START_MSG.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name,
                username=None if not message.from_user.username else '@' + message.from_user.username,
                mention=message.from_user.mention,
                id=message.from_user.id
            ),
            reply_markup=reply_markup,
            message_effect_id=5104841245755180586
        )
        return

# ====================== NOT JOINED HANDLER ======================
chat_data_cache = {}

async def not_joined(client: Client, message: Message):
    temp = await message.reply("<b><i>ᴡᴀɪᴛ ᴀ sᴇᴄ..</i></b>")

    user_id = message.from_user.id
    buttons = []
    count = 0

    try:
        all_channels = await db.show_channels()
        for total, chat_id in enumerate(all_channels, start=1):
            mode = await db.get_channel_mode(chat_id)

            await message.reply_chat_action(ChatAction.TYPING)

            if not await is_sub(client, user_id, chat_id):
                try:
                    if chat_id in chat_data_cache:
                        data = chat_data_cache[chat_id]
                    else:
                        data = await client.get_chat(chat_id)
                        chat_data_cache[chat_id] = data

                    name = data.title

                    if mode == "on" and not data.username:
                        invite = await client.create_chat_invite_link(
                            chat_id=chat_id,
                            creates_join_request=True,
                            expire_date=datetime.utcnow() + timedelta(seconds=FSUB_LINK_EXPIRY) if FSUB_LINK_EXPIRY else None
                        )
                        link = invite.invite_link
                    else:
                        if data.username:
                            link = f"https://t.me/{data.username}"
                        else:
                            invite = await client.create_chat_invite_link(
                                chat_id=chat_id,
                                expire_date=datetime.utcnow() + timedelta(seconds=FSUB_LINK_EXPIRY) if FSUB_LINK_EXPIRY else None
                            )
                            link = invite.invite_link

                    buttons.append([InlineKeyboardButton(text=name, url=link)])
                    count += 1
                    await temp.edit(f"<b>{'! ' * count}</b>")

                except Exception as e:
                    print(f"Error with chat {chat_id}: {e}")
                    return await temp.edit(
                        f"<b><i>! Eʀʀᴏʀ, Cᴏɴᴛᴀᴄᴛ ᴅᴇᴠᴇʟᴏᴘᴇʀ ᴛᴏ sᴏʟᴠᴇ ᴛʜᴇ ɪssᴜᴇs @rohit_1888</i></b>\n"
                        f"<blockquote expandable><b>Rᴇᴀsᴏɴ:</b> {e}</blockquote>"
                    )

        try:
            buttons.append([
                InlineKeyboardButton(
                    text='♻️ Tʀʏ Aɢᴀɪɴ',
                    url=f"https://t.me/{client.username}?start={message.command[1]}"
                )
            ])
        except IndexError:
            pass

        await message.reply_photo(
            photo=FORCE_PIC,
            caption=FORCE_MSG.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name,
                username=None if not message.from_user.username else '@' + message.from_user.username,
                mention=message.from_user.mention,
                id=message.from_user.id
            ),
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    except Exception as e:
        print(f"Final Error: {e}")
        await temp.edit(
            f"<b><i>! Eʀʀᴏʀ, Cᴏɴᴛᴀᴄᴛ ᴅᴇᴠᴇʟᴏᴘᴇʀ ᴛᴏ sᴏʟᴠᴇ ᴛʜᴇ ɪssᴜᴇs @rohit_1888</i></b>\n"
            f"<blockquote expandable><b>Rᴇᴀsᴏɴ:</b> {e}</blockquote>"
        )

# ====================== COMMANDS MENU ======================
@Bot.on_message(filters.command('commands') & filters.private & admin)
async def bcmd(bot: Bot, message: Message):
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("• ᴄʟᴏsᴇ •", callback_data="close")]])
    await message.reply(text=CMD_TXT, reply_markup=reply_markup, quote=True)
