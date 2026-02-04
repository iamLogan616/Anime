import asyncio
import os
import random
import sys
import time
from pyrogram import Client, filters, __version__
from pyrogram.enums import ParseMode, ChatAction, ChatMemberStatus, ChatType
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, ChatMemberUpdated, ChatPermissions
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant, InviteHashEmpty, ChatAdminRequired, PeerIdInvalid, UserIsBlocked, InputUserDeactivated
from bot import Bot
from config import *
from helper_func import *
from database.database import *

# Helper function to validate Telegram user IDs
def is_valid_telegram_id(user_id):
    """Check if a user ID is valid for Telegram"""
    try:
        uid = int(user_id)
        # Telegram IDs are positive integers (user IDs > 0, channel IDs are negative)
        return uid > 0
    except:
        return False

# Commands for adding admins by owner
@Bot.on_message(filters.command('add_admin') & filters.private & filters.user(OWNER_ID))
async def add_admins(client: Client, message: Message):
    pro = await message.reply("<b><i>ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ..</i></b>", quote=True)
    check = 0
    admin_ids = await db.get_all_admins()
    admins = message.text.split()[1:]

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")]])

    if not admins:
        return await pro.edit(
            "<b>You need to provide user ID(s) to add as admin.</b>\n\n"
            "<b>Usage:</b>\n"
            "<code>/add_admin [user_id]</code> — Add one or more user IDs\n\n"
            "<b>Example:</b>\n"
            "<code>/add_admin 1234567890 9876543210</code>",
            reply_markup=reply_markup
        )

    admin_list = ""
    successful_ids = []
    
    for id_str in admins:
        try:
            user_id = int(id_str)
        except ValueError:
            admin_list += f"<blockquote><b>❌ Invalid ID (not a number): <code>{id_str}</code></b></blockquote>\n"
            continue

        if user_id in admin_ids:
            admin_list += f"<blockquote><b>⚠️ ID <code>{user_id}</code> already exists in admin list.</b></blockquote>\n"
            continue

        # Check if it's a valid Telegram user ID (positive integer)
        if is_valid_telegram_id(user_id):
            try:
                # Try to add to database
                await db.add_admin(user_id)
                admin_list += f"<b><blockquote>✅ ID: <code>{user_id}</code> added successfully.</blockquote></b>\n"
                check += 1
                successful_ids.append(user_id)
            except Exception as e:
                admin_list += f"<blockquote><b>❌ Database error for ID <code>{user_id}</code>: {str(e)}</b></blockquote>\n"
        else:
            admin_list += f"<blockquote><b>❌ Invalid Telegram ID: <code>{id_str}</code> (must be positive number)</b></blockquote>\n"

    if check > 0:
        # Optional: Try to fetch user details for successful additions
        user_details = ""
        for uid in successful_ids:
            try:
                user = await client.get_users(uid)
                user_details += f"👤 <code>{uid}</code> → {user.mention}\n"
            except:
                user_details += f"👤 <code>{uid}</code> → (User hasn't interacted with bot yet)\n"
        
        final_message = f"<b>✅ Successfully added {check} admin(s):</b>\n\n{admin_list}"
        if user_details:
            final_message += f"\n<b>User Details:</b>\n{user_details}"
            
        await pro.edit(final_message, reply_markup=reply_markup)
    else:
        await pro.edit(
            f"<b>❌ Failed to add admins:</b>\n\n{admin_list.strip()}\n\n"
            "<b><i>Please check the IDs and try again.</i></b>",
            reply_markup=reply_markup
        )


@Bot.on_message(filters.command('deladmin') & filters.private & filters.user(OWNER_ID))
async def delete_admins(client: Client, message: Message):
    pro = await message.reply("<b><i>ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ..</i></b>", quote=True)
    admin_ids = await db.get_all_admins()
    admins = message.text.split()[1:]

    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")]])

    if not admins:
        return await pro.edit(
            "<b>Please provide valid admin ID(s) to remove.</b>\n\n"
            "<b>Usage:</b>\n"
            "<code>/deladmin [user_id]</code> — Remove specific IDs\n"
            "<code>/deladmin all</code> — Remove all admins",
            reply_markup=reply_markup
        )

    if len(admins) == 1 and admins[0].lower() == "all":
        if admin_ids:
            removed_list = ""
            for id in admin_ids:
                try:
                    await db.del_admin(id)
                    removed_list += f"<blockquote><code>{id}</code> ✅ Removed</blockquote>\n"
                except:
                    removed_list += f"<blockquote><code>{id}</code> ❌ Failed to remove</blockquote>\n"
            
            return await pro.edit(f"<b>⛔️ All admin removal results:</b>\n{removed_list}", reply_markup=reply_markup)
        else:
            return await pro.edit("<b><blockquote>No admin IDs to remove.</blockquote></b>", reply_markup=reply_markup)

    if admin_ids:
        passed = ''
        removed_count = 0
        for admin_id in admins:
            try:
                user_id = int(admin_id)
            except ValueError:
                passed += f"<blockquote><b>❌ Invalid ID (not a number): <code>{admin_id}</code></b></blockquote>\n"
                continue

            if user_id in admin_ids:
                try:
                    await db.del_admin(user_id)
                    passed += f"<blockquote><code>{user_id}</code> ✅ Removed</blockquote>\n"
                    removed_count += 1
                except Exception as e:
                    passed += f"<blockquote><code>{user_id}</code> ❌ Error: {str(e)}</blockquote>\n"
            else:
                passed += f"<blockquote><b>⚠️ ID <code>{user_id}</code> not found in admin list.</b></blockquote>\n"

        if removed_count > 0:
            await pro.edit(f"<b>✅ Successfully removed {removed_count} admin(s):</b>\n\n{passed}", reply_markup=reply_markup)
        else:
            await pro.edit(f"<b>❌ No admins were removed:</b>\n\n{passed}", reply_markup=reply_markup)
    else:
        await pro.edit("<b><blockquote>No admin IDs available to delete.</blockquote></b>", reply_markup=reply_markup)


@Bot.on_message(filters.command('admins') & filters.private & admin)
async def get_admins(client: Client, message: Message):
    pro = await message.reply("<b><i>ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ..</i></b>", quote=True)
    admin_ids = await db.get_all_admins()

    if not admin_ids:
        admin_list = "<b><blockquote>❌ No admins found.</blockquote></b>"
    else:
        admin_list = ""
        total_count = len(admin_ids)
        
        # Fetch user details for each admin
        for idx, uid in enumerate(admin_ids, 1):
            try:
                user = await client.get_users(uid)
                admin_list += f"<b>{idx}. 👤 {user.mention}</b>\n   <code>ID: {uid}</code>\n"
            except:
                admin_list += f"<b>{idx}. 👤 Unknown User</b>\n   <code>ID: {uid}</code> (hasn't interacted with bot)\n"
        
        admin_list = f"<b>Total Admins: {total_count}</b>\n\n{admin_list}"

    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_admins"),
         InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")]
    ])
    
    await pro.edit(f"<b>⚡ Current Admin List:</b>\n\n{admin_list}", reply_markup=reply_markup)


# Callback handler for refresh button
@Bot.on_callback_query(filters.regex("refresh_admins"))
async def refresh_admins_callback(client: Client, callback_query: CallbackQuery):
    await callback_query.answer("Refreshing admin list...")
    
    admin_ids = await db.get_all_admins()
    
    if not admin_ids:
        admin_list = "<b><blockquote>❌ No admins found.</blockquote></b>"
    else:
        admin_list = ""
        total_count = len(admin_ids)
        
        for idx, uid in enumerate(admin_ids, 1):
            try:
                user = await client.get_users(uid)
                admin_list += f"<b>{idx}. 👤 {user.mention}</b>\n   <code>ID: {uid}</code>\n"
            except:
                admin_list += f"<b>{idx}. 👤 Unknown User</b>\n   <code>ID: {uid}</code>\n"
        
        admin_list = f"<b>Total Admins: {total_count}</b>\n\n{admin_list}"

    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_admins"),
         InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")]
    ])
    
    await callback_query.message.edit_text(
        f"<b>⚡ Current Admin List (Refreshed):</b>\n\n{admin_list}",
        reply_markup=reply_markup
    )
