#!/usr/bin/env python

# import import_ipynb
import logging
from time import sleep
import traceback
import sys
# import emoji
from html import escape

import pickledb

from telegram import ParseMode, TelegramError, Update
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

def social_link(update, context):
#     if msg['text'] == "link":
    bot = telepot.Bot(TOKEN)
    btn1 = BT(text = "Official Website", url = "https://xd.adobe.com/view/2314682e-3f11-491b-9c1e-1fe804a3e242-7647/", callback_data = "1")
    btn2 = BT(text = "Official Announcement Telegram Channel", url = "https://t.me/official_LUCK_announcement", callback_data = "2")
    btn3 = BT(text = "Official Twitter", url = "https://twitter.com/official_LUCK_", callback_data = "3")
    btn4 = BT(text = "Official Reddit", url = "https://www.reddit.com/user/official_LUCK_", callback_data = "4")
    mu = MU(inline_keyboard = [[btn1], [btn2], [btn3], [btn4]])

    try:
#         bot.sendMessage(chat_id = '@official_LUCK_community', 
#                          text = "💖 **WHY IS $LUCK TO SUCCESS?** 💖\n💌LUCKY CHAIN LETTERS are very effective in spreading our $LUCK. \n💌The reward system for ALL CONTRIBUTORS, both recipients and senders \n💌REFERRAL REWARDS = If someone accesses my link and goes through a simple procedure, the token is rewarded \n\n💰 **$LUCK Token** 💰\n💵1. REWARD for CONTRIBUTORS \n💶2. NFT Project : We will create a reward structure to drop tokens to NFT holders or NFTs to token holders. \n💷3. STAKING & GOVERNANCE \n \n🔗 **LUCK Official Links** 🔗\n▹Homepage : [https://luck.io/en/](https://luck.io/en/) \n▹LUCK Official Telegram : [https://t.me/luck](https://t.me/luck) \n▹LUCK Official Twitter : [https://twitter.com/luck](https://twitter.com/luck) \n▹Pre-sale : [https://www.pinksale.finance/#/launchpads?chain=BSC](https://www.pinksale.finance/#/launchpads?chain=BSC)", 
#                          reply_markup = mu, parse_mode = "Markdown")
        bot.sendPhoto(chat_id='@official_LUCK_community',
              photo="https://drive.google.com/file/d/1beWQBoRy3Cf5Wz3hLNQhE0w0ZsViEP26/view?usp=sharing",
              caption="💖 **WHY IS $LUCK TO SUCCESS?** 💖\n💌LUCKY CHAIN LETTERS are very effective in spreading our $LUCK. \n💌The reward system for ALL CONTRIBUTORS, both recipients and senders \n💌REFERRAL REWARDS = If someone accesses my link and goes through a simple procedure, the token is rewarded \n\n💰 **$LUCK Token** 💰\n💵1. REWARD for CONTRIBUTORS \n💶2. NFT Project : We will create a reward structure to drop tokens to NFT holders or NFTs to token holders. \n💷3. STAKING & GOVERNANCE \n \n🔗 **LUCK Official Links** 🔗\n▹Homepage : [https://luck.io/en/](https://luck.io/en/) \n▹LUCK Official Telegram : [https://t.me/official_LUCK_announcement](https://t.me/official_LUCK_announcement) \n▹LUCK Official Twitter : [https://twitter.com/official_LUCK_](https://twitter.com/official_LUCK_) \n▹LUCK Official Reddit : [https://www.reddit.com/user/official_LUCK_](https://www.reddit.com/user/official_LUCK_)",
              reply_markup = mu,
              parse_mode = "Markdown")
        
    except Exception as e:    # 모든 예외의 에러 메시지를 출력할 때는 Exception을 사용
        print('예외가 발생했습니다.', e)
    
    
def rule(update, context):
    bot = telepot.Bot(TOKEN)
    bot.sendMessage(chat_id = '@official_LUCK_community', 
                    text = "**🍀Our 7 Rules🍀**\n\n1. Raise your LUCK's energy through fun and lucky words.\n2. Being kind to all other members, server staff, and hosts helps to make your LUCK positive.\n3. Don't discuss or ask about other LUCKY friends' personal information.\n4. Don't leak important information (phone number, email, wallet, address, wallet balance, seed statement, etc.) to protect your $LUCK.\n5. Rude and bad behavior becomes a factor that hinders the energy of your LUCK. (Hate of homosexuality, racism, and/or sexist remarks, abusive language, etc.)\n6. Don't send dangerous chats such as swear words, pornography, nudity, and gore. This place should be filled with only positive energy.\n7. FUD has no effect on your luck.",
                    parse_mode = "Markdown")

def airdrop(update, context):
    bot = telepot.Bot(TOKEN)
    bot.sendMessage(chat_id = '@official_LUCK_community',
                   text = "✨GIVEAWAY Event for Pre-sale Participants✨\n\n🎁$LUCK TOKENS GIVEAWAY FOR EARLY ADOPTERS!🎁\nLUCK is glad to announce the upcoming pre-sale of its utility token $LUCK with GIVEAWAY for Early adopters. The prize pool of the Giveaway is around 2,000,000 tokens which equal $2,000!\nThere will be around 800 winners. Giveaway is for Lucky friends and lasts till 21st Jan 2022 09:00 AM UTC. At this time there will be taken snapshots to determine loyalty of pre-sale participants.\n\n💕Who's eligible?💕\nWho made the minimum buy\n\n🏆Lucky winners🏆\n(a) 77,777 $LUCK tokens for 7 people who made the maximum buy\n(b) 7,777 $LUCK tokens for 77 people who purchase more than 1BNB (First-come, first-served basis)\n(c) 777 $LUCK tokens for 777 people who entered all the <selection questions>\n\n🔍Information🔍\nProgress period : ~2022.01.21 (until the end of presale)\nRewards payment period : the end of February 2022\nEvent contents or schedule may be adjusted depending on the number of event participants.\nEvent inquiry : [luck@luck.com](mailto:luck@luck.com)\n\nTo participate in the LUCK Giveaway please complete the tasks below.\n✔️If an illegal method (account/name theft, bug, abusing, etc.) is confirmed, it will be excluded from payment.\n✔️Please submit the Google Form only once for the first time.\n✔️You must stay in the Telegram room until the reward is paid.\n✔️Incorrect answers to the anti-abusing quiz may result in exclusion from winning. Please choose carefully.\n\n✔️Detail\n: [https://docs.google.com/document/d/1dqP2i4_yzv0VJFr39F2yGGJ0w1jNaUGHfKTk9qwIhk8/edit?usp=sharing](https://docs.google.com/document/d/1dqP2i4_yzv0VJFr39F2yGGJ0w1jNaUGHfKTk9qwIhk8/edit?usp=sharing)\n🍀Good luck!🍀",
                   parse_mode = "Markdown")
def main():
    # Create the Updater and pass it your bot's token.
    updater = Updater(TOKEN, workers=10, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher
    print("Operating well!")
    dp.add_handler(CommandHandler("shill", social_link))
    dp.add_handler(CommandHandler("rule", rule))
    dp.add_handler(CommandHandler("airdrop", airdrop))
#     dp.add_handler(CommandHandler("start", help))
#     dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("welcome", set_welcome))
#     dp.add_handler(CommandHandler("goodbye", set_goodbye))
#     dp.add_handler(CommandHandler("disable_goodbye", disable_goodbye))
#     dp.add_handler(CommandHandler("lock", lock))s
#     dp.add_handler(CommandHandler("unlock", unlock))
#     dp.add_handler(CommandHandler("quiet", quiet))
#     dp.add_handler(CommandHandler("unquiet", unquiet))

    dp.add_handler(MessageHandler(Filters.status_update, empty_message))

    dp.add_error_handler(error)

    updater.start_polling(timeout=30, clean=True)
    updater.idle()


if __name__ == "__main__":
    main()

