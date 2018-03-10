import html
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User
from telegram.error import BadRequest
from telegram.ext import Filters, MessageHandler, CommandHandler, run_async
from telegram.utils.helpers import mention_html

from tg_bot import dispatcher
from tg_bot.modules.helper_funcs.chat_status import is_user_admin, user_admin, can_restrict
from tg_bot.modules.log_channel import loggable
from tg_bot.modules.sql import antiflood_sql as sql

FLOOD_GROUP = 3


@run_async
@loggable
def check_flood(bot: Bot, update: Update) -> str:
    user = update.effective_user  # type: Optional[User]
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]

    if not user:  # ignore channels
        return ""

    # ignore admins
    if is_user_admin(chat, user.id):
        sql.update_flood(chat.id, None)
        return ""

    should_ban = sql.update_flood(chat.id, user.id)
    if should_ban:
        try:
            chat.kick_member(user.id)
            msg.reply_text("Sel felaketini doğal afetlere bırakmak istiyorum. Ama sen sadece bir "
                           "hayal kırıklığısın. Defol.")

            return "<b>{}:</b>" \
                   "\n#BANNED" \
                   "\n<b>User:</b> {}" \
                   "\nFlooded the group.".format(html.escape(chat.title),
                                                 mention_html(user.id, user.first_name))

        except BadRequest:
            msg.reply_text("Burada insanları atmama izin ver! O zamana kadar, antiflood'u devre dışı bırakacağım.")
            sql.set_flood(chat.id, 0)
            return "<b>{}:</b>" \
                   "\n#INFO" \
                   "\nDon't have kick permissions, so automatically disabled antiflood.".format(chat.title)

    return ""


@run_async
@user_admin
@can_restrict
@loggable
def set_flood(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]

    if len(args) >= 1:
        val = args[0].lower()
        if val == "off" or val == "no" or val == "0":
            sql.set_flood(chat.id, 0)
            message.reply_text("Antiflood devre dışı bırakıldı.")

        elif val.isdigit():
            amount = int(val)
            if amount <= 0:
                sql.set_flood(chat.id, 0)
                message.reply_text("Antiflood devre dışı bırakıldı.")
                return "<b>{}:</b>" \
                       "\n#SETFLOOD" \
                       "\n<b>Admin:</b> {}" \
                       "\nDisabled antiflood.".format(html.escape(chat.title), mention_html(user.id, user.first_name))

            elif amount < 3:
                message.reply_text("Antiflood 0 (devre dışı) veya 3'ten büyük bir sayı olmalıdır.!")
                return ""

            else:
                sql.set_flood(chat.id, amount)
                message.reply_text("Antiflood güncellendi ve {} flooda ayarlandı".format(amount))
                return "<b>{}:</b>" \
                       "\n#SETFLOOD" \
                       "\n<b>Admin:</b> {}" \
                       "\nSet antiflood to <code>{}</code>.".format(html.escape(chat.title),
                                                                    mention_html(user.id, user.first_name), amount)

        else:
            message.reply_text("Tanınmayan argüman - lütfen bir sayı kullanın, kapatmak için 'off' veya 'no'.")

    return ""


@run_async
def flood(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]

    flood_settings = sql.get_flood(chat.id)
    if not flood_settings or flood_settings.limit == 0:
        update.effective_message.reply_text("Şuan floodu kontrol etmiyorum!")
    else:
        update.effective_message.reply_text(
            "Şu anda kullanıcıları {} ardışık mesajdan daha fazlasını gönderiyorlarsa yasaklıyorum.".format(flood_settings.limit))


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    flood_settings = sql.get_flood(chat_id)
    if not flood_settings or flood_settings.limit == 0:
        return "*Not* currently enforcing flood control."
    else:
        return "Antiflood is set to `{}` messages.".format(flood_settings.limit)


__help__ = """
 - /flood: Mevcut flood ayarlarını getir

*Admin only:*
 - /setflood <sayı/'no'/'off'>: Floodu aktifleştir veya devre dışı bırak
"""

__mod_name__ = "Flood Engelleme"

FLOOD_BAN_HANDLER = MessageHandler(Filters.all & ~Filters.status_update & Filters.group, check_flood)
SET_FLOOD_HANDLER = CommandHandler("setflood", set_flood, pass_args=True, filters=Filters.group)
FLOOD_HANDLER = CommandHandler("flood", flood, filters=Filters.group)

dispatcher.add_handler(FLOOD_BAN_HANDLER, FLOOD_GROUP)
dispatcher.add_handler(SET_FLOOD_HANDLER)
dispatcher.add_handler(FLOOD_HANDLER)
