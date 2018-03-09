import html
from io import BytesIO
from typing import Optional, List

from telegram import Message, Update, Bot, User, Chat
from telegram.error import BadRequest, TelegramError
from telegram.ext import run_async, CommandHandler, MessageHandler, Filters
from telegram.utils.helpers import mention_html

import tg_bot.modules.sql.global_bans_sql as sql
from tg_bot import dispatcher, OWNER_ID, SUDO_USERS, SUPPORT_USERS, STRICT_GBAN
from tg_bot.modules.helper_funcs.chat_status import user_admin, is_user_admin
from tg_bot.modules.helper_funcs.extraction import extract_user, extract_user_and_text
from tg_bot.modules.helper_funcs.filters import CustomFilters
from tg_bot.modules.helper_funcs.misc import send_to_list
from tg_bot.modules.sql.users_sql import get_all_chats

GBAN_ENFORCE_GROUP = 6


@run_async
def gban(bot: Bot, update: Update, args: List[str]):
    message = update.effective_message  # type: Optional[Message]

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("Bir kullanıcıya atıf yapmıyor gibi görünüyorsun.")
        return

    if int(user_id) in SUDO_USERS:
        message.reply_text("Ben küçük gözümle casusluk yapıyorum... sudo kullanıcı savaşı! Neden birbirinizle savaşıyorsunuz?")
        return

    if int(user_id) in SUPPORT_USERS:
        message.reply_text("OOOH birisi bir destek kullanıcısını gbanlamaya çalışıyor! *patlamış mısır yer*")
        return

    if user_id == bot.id:
        message.reply_text("-_- Çok komik, kendimi gbanlıyorum, neden olmasın? Güzel deneme *SALAK*.")
        return

    try:
        user_chat = bot.get_chat(user_id)
    except BadRequest as excp:
        message.reply_text(excp.message)
        return

    if user_chat.type != 'private':
        message.reply_text("Bu bir kullanıcı değil!")
        return

    if sql.is_user_gbanned(user_id):
        if not reason:
            message.reply_text("Bu kullanıcı zaten yasaklanmış durumda; Sebebini değiştirirdim ama sen bana bir tane vermedin....")
            return

        success = sql.update_gban_reason(user_id, user_chat.username or user_chat.first_name, reason)
        if success:
            message.reply_text("Bu kullanıcı zaten yasaklanmış durumda; Gban nedenini gittim ve güncelledim!")
        else:
            message.reply_text("Tekrar denemek ister misin? Bu kişinin gbanlı olduğunu sanıyordum ama sonra değillerdi? "
                               "Kafam karıştı")

        return

    message.reply_text("*Ban çekicinin tozunu üfler* 😉")

    banner = update.effective_user  # type: Optional[User]
    send_to_list(bot, SUDO_USERS + SUPPORT_USERS,
                 "{} Gbanlıyor. Gbanlanan kullanıcı: {} "
                 "because:\n{}".format(mention_html(banner.id, banner.first_name),
                                       mention_html(user_chat.id, user_chat.first_name), reason or "No reason given"),
                 html=True)

    sql.gban_user(user_id, user_chat.username or user_chat.first_name, reason)

    chats = get_all_chats()
    for chat in chats:
        chat_id = chat.chat_id

        # Check if this group has disabled gbans
        if not sql.does_chat_gban(chat_id):
            continue

        try:
            bot.kick_chat_member(chat_id, user_id)
        except BadRequest as excp:
            if excp.message == "User is an administrator of the chat":
                pass
            elif excp.message == "Chat not found":
                pass
            elif excp.message == "Not enough rights to restrict/unrestrict chat member":
                pass
            elif excp.message == "User_not_participant":
                pass
            elif excp.message == "Peer_id_invalid":  # Suspect this happens when a group is suspended by telegram.
                pass
            elif excp.message == "Group chat was deactivated":
                pass
            elif excp.message == "Need to be inviter of a user to kick it from a basic group":
                pass
            else:
                message.reply_text("Could not gban due to: {}".format(excp.message))
                send_to_list(bot, SUDO_USERS + SUPPORT_USERS, "Could not gban due to: {}".format(excp.message))
                sql.ungban_user(user_id)
                return
        except TelegramError:
            pass

    send_to_list(bot, SUDO_USERS + SUPPORT_USERS, "Gban tamamlandı!")
    message.reply_text("Kullanıcı haritadan silindi.")


@run_async
def ungban(bot: Bot, update: Update, args: List[str]):
    message = update.effective_message  # type: Optional[Message]

    user_id = extract_user(message, args)
    if not user_id:
        message.reply_text("Bir kullanıcıya atıf yapmıyor gibi görünüyorsun.")
        return

    user_chat = bot.get_chat(user_id)
    if user_chat.type != 'private':
        message.reply_text("Bu bir kullanıcı değil!")
        return

    if not sql.is_user_gbanned(user_id):
        message.reply_text("Bu kullanıcı zaten gbanlı değil!")
        return

    banner = update.effective_user  # type: Optional[User]

    message.reply_text("Bana bir saniye ver. *{}* banını kaldırıyorum, tamamen.".format(user_chat.first_name))

    send_to_list(bot, SUDO_USERS + SUPPORT_USERS,
                 "{} Ungbanlıyor. Ungbanlanan kullanıcı: {}".format(mention_html(banner.id, banner.first_name),
                                                   mention_html(user_chat.id, user_chat.first_name)),
                 html=True)

    chats = get_all_chats()
    for chat in chats:
        chat_id = chat.chat_id

        # Check if this group has disabled gbans
        if not sql.does_chat_gban(chat_id):
            continue

        try:
            member = bot.get_chat_member(chat_id, user_id)
            if member.status == 'kicked':
                bot.unban_chat_member(chat_id, user_id)

        except BadRequest as excp:
            if excp.message == "User is an administrator of the chat":
                pass
            elif excp.message == "Chat not found":
                pass
            elif excp.message == "Not enough rights to restrict/unrestrict chat member":
                pass
            elif excp.message == "User_not_participant":
                pass
            elif excp.message == "Method is available for supergroup and channel chats only":
                pass
            elif excp.message == "Not in the chat":
                pass
            elif excp.message == "Channel_private":
                pass
            else:
                message.reply_text("Could not un-gban due to: {}".format(excp.message))
                bot.send_message(OWNER_ID, "Could not un-gban due to: {}".format(excp.message))
                return
        except TelegramError:
            pass

    sql.ungban_user(user_id)

    send_to_list(bot, SUDO_USERS + SUPPORT_USERS, "un-gban tamamlandı!")

    message.reply_text("Kişi un-gbanlandı.")


@run_async
def gbanlist(bot: Bot, update: Update):
    banned_users = sql.get_gban_list()

    if not banned_users:
        update.effective_message.reply_text("Gbanlı kullanıcı yok! Beklediğimden daha kibarsın...")
        return

    banfile = 'Screw these guys.\n'
    for user in banned_users:
        banfile += "[x] {} - {}\n".format(user["name"], user["user_id"])
        if user["reason"]:
            banfile += "Reason: {}\n".format(user["reason"])

    with BytesIO(str.encode(banfile)) as output:
        output.name = "gbanlist.txt"
        update.effective_message.reply_document(document=output, filename="gbanlist.txt",
                                                caption="İşte sorunlu insancıklar.")


def check_and_ban(update, user_id, should_message=True):
    if sql.is_user_gbanned(user_id):
        update.effective_chat.kick_member(user_id)
        if should_message:
            update.effective_message.reply_text("Bu kötü bir insan, burada olmamalı!")


@run_async
def enforce_gban(bot: Bot, update: Update):
    # Not using @restrict handler to avoid spamming - just ignore if cant gban.
    if sql.does_chat_gban(update.effective_chat.id) and update.effective_chat.get_member(bot.id).can_restrict_members:
        user = update.effective_user  # type: Optional[User]
        chat = update.effective_chat  # type: Optional[Chat]
        msg = update.effective_message  # type: Optional[Message]

        if user and not is_user_admin(chat, user.id):
            check_and_ban(update, user.id)

        if msg.new_chat_members:
            new_members = update.effective_message.new_chat_members
            for mem in new_members:
                check_and_ban(update, mem.id)

        if msg.reply_to_message:
            user = msg.reply_to_message.from_user  # type: Optional[User]
            if user and not is_user_admin(chat, user.id):
                check_and_ban(update, user.id, should_message=False)


@run_async
@user_admin
def gbanstat(bot: Bot, update: Update, args: List[str]):
    if len(args) > 0:
        if args[0].lower() in ["on", "yes"]:
            sql.enable_gbans(update.effective_chat.id)
            update.effective_message.reply_text("Bu grupta gbanları etkinleştirdim. Bu sizi korumaya yardımcı olacak "
                                                "spam gönderenlerden, hoş olmayan karakterlerden ve en büyük trollerden.")
        elif args[0].lower() in ["off", "no"]:
            sql.disable_gbans(update.effective_chat.id)
            update.effective_message.reply_text("Bu grupta gbaları devre dışı bıraktım. GBanlar, kullanıcılarınızı etkilemez "
                                                "Herhangi bir trol ve spam göndericiden daha az korunacaksınız "
                                                "Dikkatli ol!")
    else:
        update.effective_message.reply_text("Bir ayar seçmek için bazı argümanlar ver! on/off, yes/no!\n\n"
                                            "Şuanki ayar: {}\n"
                                            "True olduğunda, gerçekleşen tüm gbanlar da grubunuzda gerçekleşir. "
                                            "Yanlış olduğunda, sizi spam göndericilerin muhtemel merhametine "
                                            "bırakacağım.".format(sql.does_chat_gban(update.effective_chat.id)))


def __stats__():
    return "{} gbanned users.".format(sql.num_gbanned_users())


def __user_info__(user_id):
    is_gbanned = sql.is_user_gbanned(user_id)

    text = "Globally banned: <b>{}</b>"
    if is_gbanned:
        text = text.format("Yes")
        user = sql.get_gbanned_user(user_id)
        if user.reason:
            text += "\nReason: {}".format(html.escape(user.reason))
    else:
        text = text.format("No")
    return text


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    return "This chat is enforcing *gbans*: `{}`.".format(sql.does_chat_gban(chat_id))


__help__ = """
*Sadece yöneticiler:*
 - /gbanstat <on/off/yes/no>: Global yasakların grubunuz üzerindeki etkisini devre dışı bırakır veya geçerli ayarlarınızı gösterir.
 
Küresel yasaklar olarak da bilinen Gbans, bot sahipleri tarafından spam gruplarını tüm gruplara yasaklamak için kullanılıyor. Bu korunmaya yardımcı olur \
Spamcılar ve diğer toksik kişilerden sizi korur. \
"""

__mod_name__ = "Küresel Banlar"

GBAN_HANDLER = CommandHandler("gban", gban, pass_args=True,
                              filters=CustomFilters.sudo_filter | CustomFilters.support_filter)
UNGBAN_HANDLER = CommandHandler("ungban", ungban, pass_args=True,
                                filters=CustomFilters.sudo_filter | CustomFilters.support_filter)
GBAN_LIST = CommandHandler("gbanlist", gbanlist,
                           filters=CustomFilters.sudo_filter | CustomFilters.support_filter)

GBAN_STATUS = CommandHandler("gbanstat", gbanstat, pass_args=True, filters=Filters.group)

GBAN_ENFORCER = MessageHandler(Filters.all & Filters.group, enforce_gban)

dispatcher.add_handler(GBAN_HANDLER)
dispatcher.add_handler(UNGBAN_HANDLER)
dispatcher.add_handler(GBAN_LIST)
dispatcher.add_handler(GBAN_STATUS)

if STRICT_GBAN:  # enforce GBANS if this is set
    dispatcher.add_handler(GBAN_ENFORCER, GBAN_ENFORCE_GROUP)
