#!/usr/bin/env python

# import import_ipynb
import logging
from math import floor
from time import sleep
import traceback
import sys
# import emoji
from html import escape
import os
import csv
import os.path

import pickledb

from telegram import ParseMode, TelegramError, Update, chat
from telegram.ext import Updater, MessageHandler, CommandHandler, Filters
from telegram.ext.dispatcher import run_async

import sys
import telepot
from telepot.loop import MessageLoop
from telepot.namedtuple import InlineKeyboardMarkup as MU # 마크업
from telepot.namedtuple import InlineKeyboardButton as BT # 버튼
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler

from config import BOTNAME, TOKEN

help_text = (
    "Welcomes everyone that enters a group chat that this bot is a "
    "part of. By default, only the person who invited the bot into "
    "the group is able to change settings.\nCommands:\n\n"
    "/welcome - Set welcome message\n"
    "/goodbye - Set goodbye message\n"
    "/disable\\_goodbye - Disable the goodbye message\n"
    "/lock - Only the person who invited the bot can change messages\n"
    "/unlock - Everyone can change messages\n"
    '/quiet - Disable "Sorry, only the person who..." '
    "& help messages\n"
    '/unquiet - Enable "Sorry, only the person who..." '
    "& help messages\n\n"
    "You can use _$username_ and _$title_ as placeholders when setting"
    " messages. [HTML formatting]"
    "(https://core.telegram.org/bots/api#formatting-options) "
    "is also supported.\n"
)

"""
Create database object
Database schema:
<chat_id> -> welcome message
<chat_id>_bye -> goodbye message
<chat_id>_adm -> user id of the user who invited the bot
<chat_id>_lck -> boolean if the bot is locked or unlocked
<chat_id>_quiet -> boolean if the bot is quieted
chats -> list of chat ids where the bot has received messages in.
"""
# Create database object
db = pickledb.load("bot.db", True)

if not db.get("chats"):
    db.set("chats", [])

# Set up logging
root = logging.getLogger()
root.setLevel(logging.INFO)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


@run_async
def send_async(context, *args, **kwargs):
    context.bot.send_message(*args, **kwargs)


def check(update, context, override_lock=None):
    """
    Perform some checks on the update. If checks were successful, returns True,
    else sends an error message to the chat and returns False.
    """

    chat_id = update.message.chat_id
    chat_str = str(chat_id)

    if chat_id > 0:
        send_async(
            context, chat_id=chat_id, text="Please add me to a group first!",
        )
        return False

    locked = override_lock if override_lock is not None else db.get(chat_str + "_lck")

    if locked and db.get(chat_str + "_adm") != update.message.from_user.id:
        if not db.get(chat_str + "_quiet"):
            send_async(
                context,
                chat_id=chat_id,
                text="Sorry, only the person who invited me can do that.",
            )
        return False

    return True


# Welcome a user to the chat
def welcome(update, context, new_member):
    """ Welcomes a user to the chat """

    message = update.message
    chat_id = message.chat.id
    logger.info(
        "%s joined to chat %d (%s)",
        escape(new_member.first_name),
        chat_id,
        escape(message.chat.title),
    )

    # Pull the custom message for this chat from the database
    text = db.get(str(chat_id))

    # Use default message if there's no custom one set
    if text is None:
        text = "Hello $username! Welcome to $title 😊"

    # Replace placeholders and send message
    text = text.replace("$username", new_member.first_name)
    text = text.replace("$title", message.chat.title)
    send_async(context, chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)


# Welcome a user to the chat
def goodbye(update, context):
    """ Sends goodbye message when a user left the chat """

    message = update.message
    chat_id = message.chat.id
    logger.info(
        "%s left chat %d (%s)",
        escape(message.left_chat_member.first_name),
        chat_id,
        escape(message.chat.title),
    )

    # Pull the custom message for this chat from the database
    text = db.get(str(chat_id) + "_bye")

    # Goodbye was disabled
    if text is False:
        return

    # Use default message if there's no custom one set
    if text is None:
        text = "Goodbye, $username!"

    # Replace placeholders and send message
    text = text.replace("$username", message.left_chat_member.first_name)
    text = text.replace("$title", message.chat.title)
    send_async(context, chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)


# Introduce the bot to a chat its been added to
def introduce(update, context):
    """
    Introduces the bot to a chat its been added to and saves the user id of the
    user who invited us.
    """

    chat_id = update.message.chat.id
    invited = update.message.from_user.id

    logger.info(
        "Invited by %s to chat %d (%s)", invited, chat_id, update.message.chat.title,
    )

    db.set(str(chat_id) + "_adm", invited)
    db.set(str(chat_id) + "_lck", True)

    text = (
        f"Hello {update.message.chat.title}! "
        "I will now greet anyone who joins this chat with a "
        "nice message 😊 \nCheck the /help command for more info!"
    )
    send_async(context, chat_id=chat_id, text=text)


# Print help text
def help(update, context):
    """ Prints help text """

    chat_id = update.message.chat.id
    chat_str = str(chat_id)
    if (
        not db.get(chat_str + "_quiet")
        or db.get(chat_str + "_adm") == update.message.from_user.id
    ):
        send_async(
            context,
            chat_id=chat_id,
            text=help_text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )


# Set custom message
def set_welcome(update, context):
    """ Sets custom welcome message """

    chat_id = update.message.chat.id

    # Check admin privilege and group context
    if not check(update, context):
        return

    print(update.message.text)
    # Split message into words and remove mentions of the bot
    message = update.message.text.partition(" ")[2]

    # Only continue if there's a message
    if not message:
        send_async(
            context,
            chat_id=chat_id,
            text="You need to send a message, too! For example:\n"
            "<code>/welcome Hello $username, welcome to "
            "$title!</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    # Put message into database
    db.set(str(chat_id), message)

    send_async(context, chat_id=chat_id, text="Got it!")


# Set custom message
def set_goodbye(update, context):
    """ Enables and sets custom goodbye message """

    chat_id = update.message.chat.id

    # Check admin privilege and group context
    if not check(update, context):
        return

    # Split message into words and remove mentions of the bot
    message = update.message.text.partition(" ")[2]

    # Only continue if there's a message
    if not message:
        send_async(
            context,
            chat_id=chat_id,
            text="You need to send a message, too! For example:\n"
            "<code>/goodbye Goodbye, $username!</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    # Put message into database
    db.set(str(chat_id) + "_bye", message)

    send_async(context, chat_id=chat_id, text="Got it!")


def disable_goodbye(update, context):
    """ Disables the goodbye message """

    chat_id = update.message.chat.id

    # Check admin privilege and group context
    if not check(update, context):
        return

    # Disable goodbye message
    db.set(str(chat_id) + "_bye", False)

    send_async(context, chat_id=chat_id, text="Got it!")


def lock(update, context):
    """ Locks the chat, so only the invitee can change settings """

    chat_id = update.message.chat.id

    # Check admin privilege and group context
    if not check(update, context, override_lock=True):
        return

    # Lock the bot for this chat
    db.set(str(chat_id) + "_lck", True)

    send_async(context, chat_id=chat_id, text="Got it!")


def quiet(update, context):
    """ Quiets the chat, so no error messages will be sent """

    chat_id = update.message.chat.id

    # Check admin privilege and group context
    if not check(update, context, override_lock=True):
        return

    # Lock the bot for this chat
    db.set(str(chat_id) + "_quiet", True)

    send_async(context, chat_id=chat_id, text="Got it!")


def unquiet(update, context):
    """ Unquiets the chat """

    chat_id = update.message.chat.id

    # Check admin privilege and group context
    if not check(update, context, override_lock=True):
        return

    # Lock the bot for this chat
    db.set(str(chat_id) + "_quiet", False)

    send_async(context, chat_id=chat_id, text="Got it!")


def unlock(update, context):
    """ Unlocks the chat, so everyone can change settings """

    chat_id = update.message.chat.id

    # Check admin privilege and group context
    if not check(update, context):
        return

    # Unlock the bot for this chat
    db.set(str(chat_id) + "_lck", False)

    send_async(context, chat_id=chat_id, text="Got it!")


def empty_message(update, context):
    """
    Empty messages could be status messages, so we check them if there is a new
    group member, someone left the chat or if the bot has been added somewhere.
    """

    # Keep chatlist
    chats = db.get("chats")

    if update.message.chat.id not in chats:
        chats.append(update.message.chat.id)
        db.set("chats", chats)
        logger.info("I have been added to %d chats" % len(chats))

    if update.message.new_chat_members:
        for new_member in update.message.new_chat_members:
            # Bot was added to a group chat
            if new_member.username == BOTNAME:
                return introduce(update, context)
            # Another user joined the chat
            else:
                return welcome(update, context, new_member)

    # Someone left the chat
    elif update.message.left_chat_member is not None:
        if update.message.left_chat_member.username != BOTNAME:
            return goodbye(update, context)


def error(update, context, **kwargs):
    """ Error handling """
    error = context.error

    try:
        if isinstance(error, TelegramError) and (
            error.message == "Unauthorized"
        ):
            chats = db.get("chats")
            chats.remove(update.message.chat_id)
            db.set("chats", chats)
            logger.info("Removed chat_id %s from chat list" % update.message.chat_id)
        else:
            logger.error("An error (%s) occurred: %s" % (type(error), error.message))
    except:
        pass

# def social_link(update, context):
#     bot = telepot.Bot(TOKEN)
#     btn1 = BT(text = "🍀 Official Website 🍀", url = "https://xd.adobe.com/view/2314682e-3f11-491b-9c1e-1fe804a3e242-7647/", callback_data = "1")
#     btn2 = BT(text = "🍀 Official Announcement Telegram Channel 🍀", url = "https://t.me/official_LUCK_announcement", callback_data = "2")
#     btn3 = BT(text = "🍀 Official Twitter 🍀", url = "https://twitter.com/official_LUCK_", callback_data = "3")
#     btn4 = BT(text = "🍀 Official Reddit 🍀", url = "https://www.reddit.com/user/official_LUCK_", callback_data = "4")
#     mu = MU(inline_keyboard = [[btn1], [btn2], [btn3], [btn4]])

#     try:
#         bot.sendVideo(chat_id = '@official_LUCK_community',
#             video="https://t.me/official_LUCK_community/282",
#             caption="*💖 WHY IS $LUCK TO SUCCESS? 💖*\n🎁 Chain Letter Protocol(CLP) is the most powerful marketing protocol covering crypto & real world \n🎁 The amazing reward system for ALL CONTRIBUTORS, sender, receiver, and staker \n🎁 REFERRAL REWARDS : 💵Sender💵 🔗 💌Lucky Chain Letter💌 🔗 💶Receiver💶 \n\n*💰 $LUCK Token 💰*\n💵 1. REWARD for CONTRIBUTORS : Pledge referral and mission rewards to senders and receivers, Various benefits \n💶 2. STAKING : Apply a high level of consistent APY \n💷 3. BUYBACK : $LUCK continues to increase in value through Buyback\n💴 4. TIER System : The more lucky chain letters you spread, the higher the tier you are assigned, which leads to higher rewards\n\n",
#             reply_markup = mu,
#             parse_mode = "Markdown")

#     except Exception as e:    # 모든 예외의 에러 메시지를 출력할 때는 Exception을 사용
#         print('예외가 발생했습니다.', e)

def tothemoon(update, context):
    bot = telepot.Bot(TOKEN)
    btn1 = BT(text = "🍀 Official Website 🍀", url = "http://www.lucktoken.io/", callback_data = "1")
    btn2 = BT(text = "🍀 Official Community 🍀", url = "https://t.me/official_LUCK_community", callback_data = "2")
    btn3 = BT(text = "🍀 Official Announcement Telegram Channel 🍀", url = "https://t.me/official_LUCK_announcement", callback_data = "3")
    btn4 = BT(text = "🍀 Official Twitter 🍀", url = "https://twitter.com/official_LUCK_", callback_data = "4")
    btn5 = BT(text = "🍀 Official Reddit 🍀", url = "https://www.reddit.com/user/official_LUCK_", callback_data = "5")
    mu = MU(inline_keyboard = [[btn1], [btn2], [btn3], [btn4], [btn5]])

    try:
        bot.sendVideo(chat_id = '@official_LUCK_community',
            video="https://t.me/official_LUCK_community/643",
            caption="*💖 WHY IS $LUCK TO SUCCESS? 💖*\n\n*🎁 Spread to Earn 🎁*\nGreat spreading rewards for holders (At least $10 per 1 spreader)\n*Spreading reward + Spread of luck = Mooning luck = GET RICH*\n\n*🎁 Endless Buyback 🎁*\nBuyback the profits generated on the platform to guarantee HOLDERS’ profit.\n\n*🎁 REFERRAL REWARDS 🎁*\n💵Sender💵 🔗 💌Lucky Chain Letter💌 🔗 💶Receiver💶 \n\n\n*💰 $LUCK Token 💰*\n\n*💵 1. REWARD for CONTRIBUTORS 💵*\nPledge referral and mission rewards + Huge Benefits \n\n*💶 2. STAKING 💶*\nApply a high level of consistent APY\n\n*💷 3. BUYBACK 💷*\n$LUCK continues to increase in value\n\n*💴 4. TIER System 💴*\nRaise tiers according to your efforts and get more rewards",
            reply_markup = mu,
            parse_mode = "Markdown")
        # bot.sendMessage(chat_id = '@official_LUCK_community',
        #     text = "*💖 WHY IS $LUCK TO SUCCESS? 💖*\n\n*🎁 Chain Letter Protocol(CLP) 🎁*\nThe most powerful marketing protocol in crypto & real world \n\n*🎁 The amazing reward system 🎁*\n For ALL LUCK Ecosystem CONTRIBUTORS\n\n*🎁 REFERRAL REWARDS 🎁*\n💵Sender💵 🔗 💌Lucky Chain Letter💌 🔗 💶Receiver💶 \n\n\n*💰 $LUCK Token 💰*\n\n*💵 1. REWARD for CONTRIBUTORS 💵*\nPledge referral and mission rewards + Huge Benefits \n\n*💶 2. STAKING 💶*\nApply a high level of consistent APY\n\n*💷 3. BUYBACK 💷*\n$LUCK continues to increase in value\n\n*💴 4. TIER System 💴*\nRaise tiers according to your efforts and get more rewards\n\n",
        #     reply_markup = mu,
        #     parse_mode = "Markdown")

    except Exception as e:    # 모든 예외의 에러 메시지를 출력할 때는 Exception을 사용
        print('예외가 발생했습니다.', e)

def spread(update, context):
    bot = telepot.Bot(TOKEN)
    btn1 = BT(text = "🍀 Official Website 🍀", url = "http://www.lucktoken.io/", callback_data = "1")
    btn2 = BT(text = "🍀 Official Community 🍀", url = "https://t.me/official_LUCK_community", callback_data = "2")
    btn3 = BT(text = "🍀 Official Announcement Telegram Channel 🍀", url = "https://t.me/official_LUCK_announcement", callback_data = "3")
    btn4 = BT(text = "🍀 Official Twitter 🍀", url = "https://twitter.com/official_LUCK_", callback_data = "4")
    btn5 = BT(text = "🍀 Official Reddit 🍀", url = "https://www.reddit.com/user/official_LUCK_", callback_data = "5")
    mu = MU(inline_keyboard = [[btn1], [btn2], [btn3], [btn4], [btn5]])

    try:
        bot.sendPhoto(chat_id = '@official_LUCK_community',
            photo="https://t.me/official_LUCK_community/509",
            caption="*💖 WHY IS $LUCK TO SUCCESS? 💖*\n\n*🎁 Spread to Earn 🎁*\nGreat spreading rewards for holders (At least $10 per 1 spreader)\n*Spreading reward + Spread of luck = Mooning luck = GET RICH*\n\n*🎁 Endless Buyback 🎁*\nBuyback the profits generated on the platform to guarantee HOLDERS’ profit.\n\n*🎁 REFERRAL REWARDS 🎁*\n💵Sender💵 🔗 💌Lucky Chain Letter💌 🔗 💶Receiver💶 \n\n\n*💰 $LUCK Token 💰*\n\n*💵 1. REWARD for CONTRIBUTORS 💵*\nPledge referral and mission rewards + Huge Benefits \n\n*💶 2. STAKING 💶*\nApply a high level of consistent APY\n\n*💷 3. BUYBACK 💷*\n$LUCK continues to increase in value\n\n*💴 4. TIER System 💴*\nRaise tiers according to your efforts and get more rewards\n\n[🍀 Official Website 🍀](http://www.lucktoken.io/)\n[🍀 Official Community 🍀](https://t.me/official_LUCK_community)\n[🍀 Official Twitter 🍀](https://twitter.com/official_LUCK_",
            reply_markup = mu,
            parse_mode = "Markdown")
        # bot.sendMessage(chat_id = '@official_LUCK_community',
        #     text = "*💖 WHY IS $LUCK TO SUCCESS? 💖*\n\n*🎁 Chain Letter Protocol(CLP) 🎁*\nThe most powerful marketing protocol in crypto & real world \n\n*🎁 The amazing reward system 🎁*\n For ALL LUCK Ecosystem CONTRIBUTORS\n\n*🎁 REFERRAL REWARDS 🎁*\n💵Sender💵 🔗 💌Lucky Chain Letter💌 🔗 💶Receiver💶 \n\n\n*💰 $LUCK Token 💰*\n\n*💵 1. REWARD for CONTRIBUTORS 💵*\nPledge referral and mission rewards + Huge Benefits \n\n*💶 2. STAKING 💶*\nApply a high level of consistent APY\n\n*💷 3. BUYBACK 💷*\n$LUCK continues to increase in value\n\n*💴 4. TIER System 💴*\nRaise tiers according to your efforts and get more rewards\n\n",
        #     reply_markup = mu,
        #     parse_mode = "Markdown")

    except Exception as e:    # 모든 예외의 에러 메시지를 출력할 때는 Exception을 사용
        print('예외가 발생했습니다.', e)


def social_link(update, context):
    bot = telepot.Bot(TOKEN)
    btn1 = BT(text = "🍀 Official Website 🍀", url = "http://www.lucktoken.io/", callback_data = "1")
    btn2 = BT(text = "🍀 Official Community 🍀", url = "https://t.me/official_LUCK_community", callback_data = "2")
    btn3 = BT(text = "🍀 Official Announcement Telegram Channel 🍀", url = "https://t.me/official_LUCK_announcement", callback_data = "3")
    btn4 = BT(text = "🍀 Official Twitter 🍀", url = "https://twitter.com/official_LUCK_", callback_data = "4")
    btn5 = BT(text = "🍀 Official Reddit 🍀", url = "https://www.reddit.com/user/official_LUCK_", callback_data = "5")
    btn6 = BT(text = "🍀 Audit 🍀", url = "https://auditrate.tech/images/pdf/Luck_0x596eFdFF4bc365d1d32d0EcED114C41789f18b37.pdf", callback_data = "6")
    btn7 = BT(text = "🍀 KYC 🍀", url = "https://auditrate.tech/certificate/certificate_Luck.html", callback_data = "7")
    mu = MU(inline_keyboard = [[btn1], [btn2], [btn3], [btn4], [btn5], [btn6, btn7]])

    try:
        bot.sendPhoto(chat_id = '@official_LUCK_community',
            photo="https://t.me/official_LUCK_community/509",
            caption="*💖 WHY IS $LUCK TO SUCCESS? 💖*\n\n*🎁 Spread to Earn 🎁*\nGreat spreading rewards for holders (At least $10 per 1 spreader)\n*Spreading reward + Spread of luck = Mooning luck = GET RICH*\n\n*🎁 Endless Buyback 🎁*\nBuyback the profits generated on the platform to guarantee HOLDERS’ profit.\n\n*🎁 REFERRAL REWARDS 🎁*\n💵Sender💵 🔗 💌Lucky Chain Letter💌 🔗 💶Receiver💶 \n\n\n*💰 $LUCK Token 💰*\n\n*💵 1. REWARD for CONTRIBUTORS 💵*\nPledge referral and mission rewards + Huge Benefits \n\n*💶 2. STAKING 💶*\nApply a high level of consistent APY\n\n*💷 3. BUYBACK 💷*\n$LUCK continues to increase in value\n\n*💴 4. TIER System 💴*\nRaise tiers according to your efforts and get more rewards",
            reply_markup = mu,
            parse_mode = "Markdown")
        # bot.sendMessage(chat_id = '@official_LUCK_community',
        #     text = "*💖 WHY IS $LUCK TO SUCCESS? 💖*\n\n*🎁 Chain Letter Protocol(CLP) 🎁*\nThe most powerful marketing protocol in crypto & real world \n\n*🎁 The amazing reward system 🎁*\n For ALL LUCK Ecosystem CONTRIBUTORS\n\n*🎁 REFERRAL REWARDS 🎁*\n💵Sender💵 🔗 💌Lucky Chain Letter💌 🔗 💶Receiver💶 \n\n\n*💰 $LUCK Token 💰*\n\n*💵 1. REWARD for CONTRIBUTORS 💵*\nPledge referral and mission rewards + Huge Benefits \n\n*💶 2. STAKING 💶*\nApply a high level of consistent APY\n\n*💷 3. BUYBACK 💷*\n$LUCK continues to increase in value\n\n*💴 4. TIER System 💴*\nRaise tiers according to your efforts and get more rewards\n\n",
        #     reply_markup = mu,
        #     parse_mode = "Markdown")

    except Exception as e:    # 모든 예외의 에러 메시지를 출력할 때는 Exception을 사용
        print('예외가 발생했습니다.', e)
    
    
def rule(update, context):
    bot = telepot.Bot(TOKEN)
    bot.sendMessage(chat_id = '@official_LUCK_community', 
                    text = "*🍀 Our 7 Rules 🍀*\n\n1. Raise your LUCK's energy through fun and lucky words.\n2. Being kind to all other members, server staff, and hosts helps to make your LUCK positive.\n3. Don't discuss or ask about other LUCKY friends' personal information.\n4. Don't leak important information (phone number, email, wallet, address, wallet balance, seed statement, etc.) to protect your $LUCK.\n5. Rude and bad behavior becomes a factor that hinders the energy of your LUCK. (Hate of homosexuality, racism, and/or sexist remarks, abusive language, etc.)\n6. Don't send dangerous chats such as swear words, pornography, nudity, and gore. This place should be filled with only positive energy.\n7. FUD has no effect on your luck.",
                    parse_mode = "Markdown")

def airdrop(update, context):
    bot = telepot.Bot(TOKEN)
    btn = BT(text = "🍀 Visit LUCK AIRDROP page 🍀", url = "", callback_data = "1")
    mu = MU(inline_keyboard = [[btn]])
    bot.sendMessage(chat_id = '@official_LUCK_community',
                   text = "*✨ AIRDROP Event for Pre-sale Participants ✨*\n\n*🎁 $LUCK TOKENS AIRDROP FOR EARLY ADOPTERS! 🎁*\n✔️ AIRDROP Event starts 2022-03-01\n✔️ AIRDROP Event ends 2022-03-04\n✔️ Airdrop Link: Go to Airdrop\n✔️ Total value: 50,000,000 $LUCK +a\n\n*💕 Who's eligible? 💕*\nPre-sale Participants\n\n*🏆 Lucky winners 🏆*\n✨ 7,777,777 $LUCK tokens for 3 people who made the maximum buy\n✨ 777,777 $LUCK tokens for 7 people who purchase more than 1BNB (First-come, first-served basis)\n✨ 77,777 $LUCK tokens for all people who submit this form\n\n*Visit this LUCK airdrop page*\n👉 (link)\n\n Requirements:\n✔️ E-Mail required\n✔️ Wallet address required\n✔️ Made a minimum buy on pink sale\n✔️ Solve Anti-Abusing Quiz\n\n*🍀 Good luck! 🍀*",
                   reply_markup = mu,
                   parse_mode = "Markdown")

def whitelist(update, context):
    bot = telepot.Bot(TOKEN)
    btn = BT(text = "🍀 Visit LUCK WHITELIST page 🍀", url = "https://lucktoken.io/giveaway", callback_data = "1")
    mu = MU(inline_keyboard = [[btn]])
    # bot.sendMessage(chat_id = '@official_LUCK_community',
    #                text = "*✨ WHITELIST ANNOUNCEMENT ✨*\n\n*Please join the campaign quickly ：*\n👉 https://lucktoken.io/giveaway\n\n🍀 Participate to be on the $LUCK Whitelist!\n🍀 Apply for the whitelist, create your referral link, and get $LUCK!\n\n*⏰ DEADLINE ⏰*\nWhitelist registration ends at: 09:00 AM UTC, *March 3rd*.\n\nWINNERS WILL BE ANNOUNCED OUR OFFICIAL CHANNEL AFTER THE END OF THIS EVENT\n\n*🗣 The more friends you refer, greater the chances you'll win!*\n🔸 1st place: 1 BNB (full allocation)\n🔸 2nd place: 0.7 BNB (half allocation)\n🔸 3rd place:  0.3 BNB (one third allocation)\n\n",
    #                reply_markup = mu,
    #                parse_mode = "Markdown")

    bot.sendVideo(chat_id = '@official_LUCK_community',
                video="https://t.me/official_LUCK_community/1513",
                caption="*✨ WHITELIST ANNOUNCEMENT ✨*\n\n*Please join the campaign quickly ：*\n👉 https://lucktoken.io/giveaway\n\n🍀 Participate to be on the $LUCK Whitelist!\n🍀 Apply for the whitelist, create your referral link, and get $LUCK!\n\n*⏰ DEADLINE ⏰*\nWhitelist registration ends at: 09:00 AM UTC, *March 10th*.\n\nWINNERS WILL BE ANNOUNCED OUR OFFICIAL CHANNEL AFTER THE END OF THIS EVENT\n\n*🗣 The more friends you refer, greater the chances you'll win!*\n🔸 1st place: 1 BNB (full allocation)\n🔸 2nd place: 0.7 BNB (half allocation)\n🔸 3rd place:  0.3 BNB (one third allocation)\n\n",
                reply_markup = mu,
                parse_mode = "Markdown")


def presale(update, context):
    bot = telepot.Bot(TOKEN)
    btn = BT(text = "🍀 PRESALE ANNOUNCEMENT 🍀", url = "https://www.pinksale.finance/#/launchpad\n\n", callback_data = "1")
    mu = MU(inline_keyboard = [[btn]])
    bot.sendMessage(chat_id = '@official_LUCK_community',
                text = "*✨ PRESALE ANNOUNCEMENT ✨*\n\n🚨 OFFICIAL LINK FOR PRESALE 🚨\n👉 [Visit LUCK Presale page](https://www.pinksale.finance/#/launchpad)\n\nWe will have the following structure:\n\n*- First Come First Served ( FCFS )*\n\n*- SOFT CAP   : 50 BNB*\n*- HARD CAP  : 100 BNB*\n\n*- MIN BUY     : 0.1 BNB*\n*- MAX BUY    : 2 BNB*\n\n🍀 Part 1 : *WHITELIST ROUND*\n         START TIME : 09:00 AM UTC 01 Mar\n         END TIME    : 09:00 AM UTC 02 Mar\n\n🍀 Part 2 : *PUBLIC ROUND*\n         START TIME : 09:00 AM UTC 03 Mar\n         END TIME    : 09:00 AM UTC 04 Mar\n\n🍀 Part 3 : You will be able to *trade $LUCK on PANCAKESWAP* at 10:00 AM UTC 04 Mar\n\n*🍀 LUCK Token Address (BEP-20)*\n👉(token address)\n\n🚀 *Presale Rate　: 1 BNB* = 30,000,000 *LUCK*\n🚀 *Listing Rate  : 1 BNB* = 25,510,000 *LUCK*\n\n*Unsold Tokens : BURN🔥*\n",
                reply_markup = mu,
                parse_mode = "Markdown")

def marketing(update, context):
    bot = telepot.Bot(TOKEN)
    btn = BT(text = "🍀 Send marketing proposal to clever 🍀", url = "https://t.me/luckclever", callback_data = "1")
    mu = MU(inline_keyboard = [[btn]])
    bot.sendMessage(chat_id = '@official_LUCK_community',
                   text = "If you have a marketing proposal to present to Project LUCK, DM to @luckclever",
                   reply_markup = mu,
                   parse_mode = "Markdown")

def luck(update, context):
    bot = telepot.Bot(TOKEN)
    btn1 = BT(text = "🍀 Official Website 🍀", url = "http://www.lucktoken.io/", callback_data = "1")
    btn2 = BT(text = "🍀 Official Announcement Telegram Channel 🍀", url = "https://t.me/official_LUCK_announcement", callback_data = "2")
    btn3 = BT(text = "🍀 Official Twitter 🍀", url = "https://twitter.com/official_LUCK_", callback_data = "3")
    btn4 = BT(text = "🍀 Official Reddit 🍀", url = "https://www.reddit.com/user/official_LUCK_", callback_data = "4")
    mu = MU(inline_keyboard = [[btn1], [btn2], [btn3], [btn4]])
    
    bot.sendMessage(chat_id = '@official_LUCK_community',
                   text = "*🎰 What is $LUCK? 🎰*\n\n*$LUCK is Referral Marketing Platform, inspired by network marketing.*\n👨‍👩‍👧‍👦 For users of platform, we guarantee referral rewards.\n🏢 For advertisers, we provide pool of referral marketers and various marketing tools.\n\n*🚀 How does $LUCK work? 🚀*\n\n1️⃣ Advertisers offer their referral events and deposit rewards to $LUCK's pool.\n2️⃣ Platform users do referral marketing for the Advertisers.\n3️⃣ Users get massive referral rewards from $LUCK's pool.\n4️⃣ Users will get more rewards when their friends do marketing.\n5️⃣ Advertisers get marketed by platform users.\n\n$LUCK aim to create synergy by connecting marketers and advertisers.\n*🍀 Join LUCK, Grow together. $LUCK will make your wallet LUCKY 🍀*",
                   reply_markup = mu,
                   parse_mode = "Markdown")

def baby(update, context):
    bot = telepot.Bot(TOKEN)
    bot.sendVideo(chat_id = '@official_LUCK_community',
            video = 'https://t.me/official_LUCK_community/643')

def baby_get_luck(update, context):
    bot = telepot.Bot(TOKEN)
    bot.sendVideo(chat_id = '@official_LUCK_community',
            video = 'https://t.me/official_LUCK_community/794')

def lucky_chain_letter(update, context):
    bot = telepot.Bot(TOKEN)
    bot.sendVideo(chat_id = '@official_LUCK_community',
            video = 'https://t.me/official_LUCK_community/650')

def push(update, context):
    bot = telepot.Bot(TOKEN)
    btn1 = BT(text = "🍀 Official Website 🍀", url = "http://www.lucktoken.io/", callback_data = "1")
    btn2 = BT(text = "🍀 Official Community 🍀", url = "https://t.me/official_LUCK_community", callback_data = "2")
    btn3 = BT(text = "🍀 Official Announcement Telegram Channel 🍀", url = "https://t.me/official_LUCK_announcement", callback_data = "3")
    btn4 = BT(text = "🍀 Official Twitter 🍀", url = "https://twitter.com/official_LUCK_", callback_data = "4")
    btn5 = BT(text = "🍀 Official Reddit 🍀", url = "https://www.reddit.com/user/official_LUCK_", callback_data = "5")
    mu = MU(inline_keyboard = [[btn1], [btn2], [btn3], [btn4], [btn5]])

    bot.sendPhoto(chat_id = '@hermes_test_group',
        photo="https://t.me/hermes_test_group/171",
        caption="*💖 PUSH THE COMMAND 💖*\n\n /shill \n /rule \n /tothemoon \n /luck \n /marketing \n /baby \n /baby_get_luck \n /lucky_chain_letter",
        reply_markup = mu,
        parse_mode = "Markdown")
    
def referral(update, context):
    bot = telepot.Bot(TOKEN)
    btn1 = BT(text = "🍀 Event Link 🍀", url = "https://lucktoken.io/giveaway", callback_data = "1")
    mu = MU(inline_keyboard = [[btn1]])

    bot.sendMessage(chat_id = '@official_LUCK_community',
                    text = "*🎰 What is the Referral Reward? 🎰*\n\n*👨‍👩‍👧‍👦 Refer Your Friends! 👨‍👩‍👧‍👦*\nBring a friend through your referral link and you can get the *Referral Rewards*!\nIf your friend brings another friend, you can get the *Bonus Referral Rewards*!\n\n*✏️ Complete the mission!*\nRegister your wallet address to receive rewards, and complete a simple SNS follow-up procedure to receive *REWARDS* for mission completion!\n\n*🚀 How to get Referral Rewards? 🚀*\n1️⃣ Complete a very simple mission!\n2️⃣ You'll get a reward!\n3️⃣ Issue a referral link!\n4️⃣ Send me a link!\n5️⃣ Get plenty of reward!\n\n*👇LINK👇*\nlucktoken.io/giveaway\n\n*🍀 Join LUCK, Grow together. $LUCK will make your wallet LUCKY 🍀*",
                    reply_markup = mu,
                    parse_mode = "Markdown")

def launch(update, context):
    bot = telepot.Bot(TOKEN)
    btn1 = BT(text = "🍀 Go to PCS 🍀", url = "https://pancakeswap.finance/", callback_data = "1")
    mu = MU(inline_keyboard = [[btn1]])

    bot.sendMessage(chat_id = '@official_LUCK_community',
                    text = "We will launch on March 8th at *Pancakeswap*.\n *STAY TUNED!*",
                    reply_markup = mu,
                    parse_mode = "Markdown")

def doxx(update, context):
    bot = telepot.Bot(TOKEN)
    btn1 = BT(text = "🍀 Audit 🍀", url = "https://auditrate.tech/images/pdf/Luck_0x596eFdFF4bc365d1d32d0EcED114C41789f18b37.pdf", callback_data = "1")
    btn2 = BT(text = "🍀 KYC 🍀", url = "https://auditrate.tech/certificate/certificate_Luck.html", callback_data = "2")
    mu = MU(inline_keyboard = [[btn1, btn2]])

    try:
        bot.sendMessage(chat_id = '@official_LUCK_community',
                    text = "Doxx(*Audit & KYC*) of project $LUCK can be checked through the next button.\n\n*✨ Get $LUCK & Getting Lucky! ✨*",
                    reply_markup = mu,
                    parse_mode = "Markdown")

    except Exception as e:    # 모든 예외의 에러 메시지를 출력할 때는 Exception을 사용
        print('예외가 발생했습니다.', e)

def main():
    # Create the Updater and pass it your bot's token.
    updater = Updater(TOKEN, workers=10, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher
    print("Operating well!")
    dp.add_handler(CommandHandler("shill", social_link))
    dp.add_handler(CommandHandler("spread", spread))
    dp.add_handler(CommandHandler("tothemoon", tothemoon))
    dp.add_handler(CommandHandler("rule", rule))
    # dp.add_handler(CommandHandler("airdrop", airdrop)) # airdrop page 작성해야함
    dp.add_handler(CommandHandler("whitelist", whitelist))
    # dp.add_handler(CommandHandler("presale", presale)) #presale 링크 작성, token address 적용
    dp.add_handler(CommandHandler("luck", luck))
    dp.add_handler(CommandHandler("marketing", marketing))
    dp.add_handler(CommandHandler("baby", baby))
    dp.add_handler(CommandHandler("baby_get_luck", baby_get_luck))
    dp.add_handler(CommandHandler("lucky_chain_letter", lucky_chain_letter))
    dp.add_handler(CommandHandler("push", push))
    dp.add_handler(CommandHandler("launch", launch))
    dp.add_handler(CommandHandler("referral", referral))
    dp.add_handler(CommandHandler("audit", doxx))
    dp.add_handler(CommandHandler("kyc", doxx))
    # dp.add_handler(CommandHandler("keyword", keyword))
    # dp.add_handler(CommandHandler("marketing", sir))
    # dp.add_handler(CommandHandler("proposal", sir))
#     dp.add_handler(CommandHandler("start", help))
#     dp.add_handler(CommandHandler("help", help))
    # dp.add_handler(CommandHandler("welcome", set_welcome))
#     dp.add_handler(CommandHandler("goodbye", set_goodbye))
#     dp.add_handler(CommandHandler("disable_goodbye", disable_goodbye))
#     dp.add_handler(CommandHandler("lock", lock))
#     dp.add_handler(CommandHandler("unlock", unlock))
#     dp.add_handler(CommandHandler("quiet", quiet))
#     dp.add_handler(CommandHandler("unquiet", unquiet))

    dp.add_handler(MessageHandler(Filters.status_update, empty_message))

    dp.add_error_handler(error)

    updater.start_polling(timeout=30, clean=True)
    updater.idle()


if __name__ == "__main__":
    main()

