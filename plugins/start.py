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

BAN_SUPPORT = f"{BAN_SUPPORT}"

@Bot.on_message(filters.command('start') & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id

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
        #await temp.delete()
        return await not_joined(client, message)

    # File auto-delete time in seconds (Set your desired time in seconds here)
    FILE_AUTO_DELETE = await db.get_del_timer()  # Example: 3600 seconds (1 hour)

    # Add user if not already present
    if not await db.present_user(user_id):
        try:
            await db.add_user(user_id)
        except:
            pass

    # Handle normal message flow
    text = message.text
    if len(text) > 7:
        try:
            base64_string = text.split(" ", 1)[1]
        except IndexError:
            return

        string = await decode(base64_string)
        
        # Check if it's a secondary channel link
        if string.startswith("sec-"):
            channel_type = "secondary"
            string = string[4:]  # Remove 'sec-' prefix
            if not client.secondary_channel:
                return await message.reply("⚠️ Secondary channel not available. Please contact admin.")
            target_channel = client.secondary_channel
        else:
            channel_type = "primary"
            target_channel = client.db_channel
        
        # ============= SEQUENCE BATCH HANDLING =============
        # Check if it's a sequence batch
        if string.startswith("seq-") or (string.startswith("sec-") and "seq-" in string):
            # Handle sequence batch with multiple buttons
            if string.startswith("sec-"):
                channel_type = "secondary"
                string = string[4:]  # Remove sec- prefix
                if not client.secondary_channel:
                    return await message.reply("⚠️ Secondary channel not available. Please contact admin.")
                target_channel = client.secondary_channel
            else:
                channel_type = "primary"
                target_channel = client.db_channel
            
            # Decode the sequence batch
            start, end, titles = await decode_sequence_batch(string)
            
            if not start or not end or not titles:
                return await message.reply("❌ Invalid sequence batch format.")
            
            # Calculate actual message IDs
            channel_multiplier = abs(target_channel.id)
            start_id = int(start / channel_multiplier)
            end_id = int(end / channel_multiplier)
            
            # Generate IDs list
            if start_id <= end_id:
                ids = list(range(start_id, end_id + 1))
            else:
                ids = list(range(start_id, end_id - 1, -1))
            
            temp_msg = await message.reply(f"<b>📥 Fetching sequence batch from {channel_type} channel...</b>")
            
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
            
            # Create buttons for each file with custom titles
            file_buttons = []
            valid_messages = []
            valid_titles = []
            
            for idx, msg in enumerate(messages):
                if not msg:
                    continue
                
                valid_messages.append(msg)
                # Get custom title if available
                custom_title = titles[idx] if idx < len(titles) else f"File {idx+1}"
                valid_titles.append(custom_title)
                
                # Create button for this file
                file_buttons.append([
                    InlineKeyboardButton(
                        text=custom_title,
                        callback_data=f"getfile_{msg.id}_{channel_type}"
                    )
                ])
            
            if not valid_messages:
                return await message.reply("❌ No valid files found in this batch.")
            
            # Create main message with file list
            main_text = f"<b>📦 Sequence Batch</b>\n\n"
            main_text += f"<b>Channel:</b> {target_channel.title}\n"
            main_text += f"<b>Total Files:</b> {len(valid_messages)}\n\n"
            main_text += "<b>Click on any button to get the file:</b>"
            
            # Send the main message with file buttons
            await message.reply_text(
                main_text,
                reply_markup=InlineKeyboardMarkup(file_buttons)
            )
            
            return
        # ============= END SEQUENCE BATCH HANDLING =============
        
        # Regular batch handling (existing code)
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
                # Removed "Get file again" button and replaced with text message
                await notification_msg.edit(
                    "<b><i>⏰ Time is over\nYour files has been deleted ✅</i></b>"
                )
            except Exception as e:
                print(f"Error updating notification message: {e}")
    else:
        # Modified reply markup without "More Channels" button
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
            message_effect_id=5104841245755180586)  # 🔥
        
        return



#=====================================================================================##
# Don't Remove Credit @Yeon_Bots, @mrxeontg
# Ask Doubt on telegram @yeon_bots



# Create a global dictionary to store chat data
chat_data_cache = {}

async def not_joined(client: Client, message: Message):
    temp = await message.reply("<b><i>ᴡᴀɪᴛ ᴀ sᴇᴄ..</i></b>")

    user_id = message.from_user.id
    buttons = []
    count = 0

    try:
        all_channels = await db.show_channels()  # Should return list of (chat_id, mode) tuples
        for total, chat_id in enumerate(all_channels, start=1):
            mode = await db.get_channel_mode(chat_id)  # fetch mode 

            await message.reply_chat_action(ChatAction.TYPING)

            if not await is_sub(client, user_id, chat_id):
                try:
                    # Cache chat info
                    if chat_id in chat_data_cache:
                        data = chat_data_cache[chat_id]
                    else:
                        data = await client.get_chat(chat_id)
                        chat_data_cache[chat_id] = data

                    name = data.title

                    # Generate proper invite link based on the mode
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
                                expire_date=datetime.utcnow() + timedelta(seconds=FSUB_LINK_EXPIRY) if FSUB_LINK_EXPIRY else None)
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

        # Retry Button
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

#=====================================================================================##

@Bot.on_message(filters.command('commands') & filters.private & admin)
async def bcmd(bot: Bot, message: Message):        
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("• ᴄʟᴏsᴇ •", callback_data = "close")]])
    await message.reply(text=CMD_TXT, reply_markup = reply_markup, quote= True)
