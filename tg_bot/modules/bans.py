import html
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User
from telegram.error import BadRequest
from telegram.ext import run_async, CommandHandler, Filters
from telegram.utils.helpers import mention_html

from tg_bot import dispatcher, BAN_STICKER, LOGGER
from tg_bot.modules.disable import DisableAbleCommandHandler
from tg_bot.modules.helper_funcs.chat_status import bot_admin, user_admin, is_user_ban_protected, can_restrict, \
    is_user_admin, is_user_in_chat
from tg_bot.modules.helper_funcs.extraction import extract_user_and_text
from tg_bot.modules.log_channel import loggable


@run_async
@bot_admin
@can_restrict
@user_admin
@loggable
def ban(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("Bir kullanıcıya atıfta bulunmuyorsunuz.")
        return ""

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "User not found":
            message.reply_text("Bu kullanıcıyı bulamıyorum")
            return ""
        else:
            raise

    if is_user_ban_protected(chat, user_id, member):
        message.reply_text("Keşke yöneticileri yasaklayabilseydim...")
        return ""

    if user_id == bot.id:
        update.effective_message.reply_text("Kendimi YASAKLAMAYACAĞIM, sen çıldırdın mı??")
        return ""

    log = "<b>{}:</b>" \
          "\n#BANNED" \
          "\n<b>Admin:</b> {}" \
          "\n<b>User:</b> {}".format(html.escape(chat.title), mention_html(user.id, user.first_name),
                                     mention_html(member.user.id, member.user.first_name))
    if reason:
        log += "\n<b>Sebep:</b> {}".format(reason)

    try:
        update.effective_chat.kick_member(user_id)
        bot.send_sticker(update.effective_chat.id, BAN_STICKER)  # banhammer marie sticker
        message.reply_text("Yasaklandı!")
        return log

    except BadRequest as excp:
        if excp.message == "Reply message not found":
            # Do not reply
            message.reply_text('Yasaklandı!', quote=False)
            return log
        else:
            LOGGER.warning(update)
            LOGGER.exception("ERROR banning user %s in chat %s (%s) due to %s", user_id, chat.title, chat.id,
                             excp.message)
            message.reply_text("Kahretsin, o kullanıcıyı yasaklayamam.")

    return ""


@run_async
@bot_admin
@can_restrict
@user_admin
@loggable
def kick(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        return ""

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "User not found":
            message.reply_text("Bu kullanıcıyı bulamıyorum")
            return ""
        else:
            raise

    if is_user_ban_protected(chat, user_id):
        message.reply_text("Keşke yöneticileri atabilseydim...")
        return ""

    if user_id == bot.id:
        update.effective_message.reply_text("Evet, bunu yapmayacağım *SALAK*")
        return ""

    res = update.effective_chat.unban_member(user_id)  # unban on current user = kick
    if res:
        bot.send_sticker(update.effective_chat.id, BAN_STICKER)  # banhammer marie sticker
        message.reply_text("Kicked!")
        log = "<b>{}:</b>" \
              "\n#KICKED" \
              "\n<b>Admin:</b> {}" \
              "\n<b>User:</b> {}".format(html.escape(chat.title),
                                         mention_html(user.id, user.first_name),
                                         mention_html(member.user.id, member.user.first_name))
        if reason:
            log += "\n<b>Sebep:</b> {}".format(reason)

        return log

    else:
        message.reply_text("Kahretsin, o kullanıcıyı atamam.")

    return ""


@run_async
@bot_admin
@can_restrict
def kickme(bot: Bot, update: Update):
    user_id = update.effective_message.from_user.id
    if is_user_admin(update.effective_chat, user_id):
        update.effective_message.reply_text("Keşke yapabilseydim ... ama sen bir yöneticisin.")
        return

    res = update.effective_chat.unban_member(user_id)  # unban on current user = kick
    if res:
        update.effective_message.reply_text("Sorun değil.")
    else:
        update.effective_message.reply_text("Ha? Yapamam:/")


@run_async
@bot_admin
@can_restrict
@user_admin
@loggable
def unban(bot: Bot, update: Update, args: List[str]) -> str:
    message = update.effective_message  # type: Optional[Message]
    user = update.effective_user  # type: Optional[User]
    chat = update.effective_chat  # type: Optional[Chat]

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        return ""

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "User not found":
            message.reply_text("Bu kullanıcıyı bulamıyorum")
            return ""
        else:
            raise

    if user_id == bot.id:
        update.effective_message.reply_text("Burada olmasaydım kendi yasağımı nasıl kaldırırdım...?")
        return ""

    if is_user_in_chat(chat, user_id):
        update.effective_message.reply_text("Neden zaten sohbetde olan birisini engelini açmaya çalışıyorsun??")
        return ""

    update.effective_chat.unban_member(user_id)
    message.reply_text("Evet, artık bu kullanıcı katılabilir!")

    log = "<b>{}:</b>" \
          "\n#UNBANNED" \
          "\n<b>Admin:</b> {}" \
          "\n<b>User:</b> {}".format(html.escape(chat.title),
                                     mention_html(user.id, user.first_name),
                                     mention_html(member.user.id, member.user.first_name))
    if reason:
        log += "\n<b>Sebep:</b> {}".format(reason)

    return log


__help__ = """
 - /kickme: komutu veren kullanıcıyı sohbetten atar

*Sadece yöneticiler:*
 - /ban <userhandle>: kullanıcıyı yasaklar. (Kullanıcı adı veya mesajı cevapla)
 - /unban <userhandle>: kullanıcının yasağını kaldır (Kullanıcı adı veya mesajı cevapla)
 - /kick <userhandle>: kullanıcı sohbetten at (Kullanıcı adı veya mesajı cevapla)
"""

__mod_name__ = "Yasaklamalar"

BAN_HANDLER = CommandHandler("ban", ban, pass_args=True, filters=Filters.group)
KICK_HANDLER = CommandHandler("kick", kick, pass_args=True, filters=Filters.group)
UNBAN_HANDLER = CommandHandler("unban", unban, pass_args=True, filters=Filters.group)
KICKME_HANDLER = DisableAbleCommandHandler("kickme", kickme, filters=Filters.group)

dispatcher.add_handler(BAN_HANDLER)
dispatcher.add_handler(KICK_HANDLER)
dispatcher.add_handler(UNBAN_HANDLER)
dispatcher.add_handler(KICKME_HANDLER)
