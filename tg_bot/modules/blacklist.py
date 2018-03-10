import html
import re
from typing import Optional

from telegram import Message, Chat, Update, Bot, ParseMode
from telegram.ext import CommandHandler, MessageHandler, Filters, run_async

import tg_bot.modules.sql.blacklist_sql as sql
from tg_bot import dispatcher
from tg_bot.modules.helper_funcs.chat_status import user_admin, user_not_admin
from tg_bot.modules.helper_funcs.extraction import extract_text
from tg_bot.modules.helper_funcs.misc import split_message

BLACKLIST_GROUP = 11

BASE_BLACKLIST_STRING = "Şuan <b>karalistedeki</b> kelimeler:\n"


@run_async
def blacklist(bot: Bot, update: Update):
    msg = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]

    all_blacklisted = sql.get_chat_blacklist(chat.id)

    filter_list = BASE_BLACKLIST_STRING
    for handler in all_blacklisted:
        filter_list += " - <code>{}</code>\n".format(html.escape(handler.trigger))

    split_text = split_message(filter_list)
    for text in split_text:
        if text == BASE_BLACKLIST_STRING:
            msg.reply_text("Karalistede herhangi bir kelime yok!")
            return
        msg.reply_text(text, parse_mode=ParseMode.HTML)


@run_async
@user_admin
def add_blacklist(bot: Bot, update: Update):
    msg = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    words = msg.text.split(None, 1)
    if len(words) > 1:
        text = words[1]
        to_blacklist = list(set(trigger.strip() for trigger in text.split("\n") if trigger.strip()))
        for trigger in to_blacklist:
            sql.add_to_blacklist(chat.id, trigger.lower())

        if len(to_blacklist) == 1:
            msg.reply_text("<code>{}</code> Karalisteye eklendi!".format(html.escape(to_blacklist[0])),
                           parse_mode=ParseMode.HTML)

        else:
            msg.reply_text(
                "<code>{}</code> Tetikleyicisi karalisteye eklendi.".format(len(to_blacklist)), parse_mode=ParseMode.HTML)

    else:
        msg.reply_text("Kara listeden çıkarmak istediğiniz kelimeleri bana söyle.")


@run_async
@user_admin
def unblacklist(bot: Bot, update: Update):
    msg = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    words = msg.text.split(None, 1)
    if len(words) > 1:
        text = words[1]
        to_blacklist = text.split("\n")
        successful = 0
        for trigger in to_blacklist:
            success = sql.rm_from_blacklist(chat.id, trigger.lower())
            if success:
                successful += 1

        if len(to_blacklist) == 1:
            if successful:
                msg.reply_text("<code>{}</code> kelime karalistesinden kaldırıldı!".format(html.escape(to_blacklist[0])),
                               parse_mode=ParseMode.HTML)
            else:
                msg.reply_text("Bu kara listeye alınmış bir tetikleyici değil...!")

        elif successful == len(to_blacklist):
            msg.reply_text(
                "<code>{}</code> tetikleyicisi karalisteden kaldırıldı.".format(
                    successful), parse_mode=ParseMode.HTML)

        elif not successful:
            msg.reply_text(
                "Bu tetikleyicilerin hiçbiri mevcut değil, bu yüzden kaldırılmadılar.".format(
                    successful, len(to_blacklist) - successful), parse_mode=ParseMode.HTML)

        else:
            msg.reply_text(
                "<code>{}</code> tetikleyicisi karalisteden kaldırıldı. {} bulunamadı, "
                "bu yüzden kaldırılmadı.".format(successful, len(to_blacklist) - successful),
                parse_mode=ParseMode.HTML)
    else:
        msg.reply_text("Kara listeden çıkarmak istediğiniz kelimeleri söyle.")


@run_async
@user_not_admin
def del_blacklist(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]
    chat_filters = sql.get_chat_blacklist(chat.id)
    to_match = extract_text(message)
    if not to_match:
        return

    for filt in chat_filters:
        pattern = r"( |^|[^\w])" + re.escape(filt.trigger) + r"( |$|[^\w])"
        if re.search(pattern, to_match, flags=re.IGNORECASE):
            message.delete()


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    blacklisted = sql.num_blacklist_chat_filters(chat_id)
    return "Şuan karalistede {} kelime var.".format(blacklisted)


def __stats__():
    return "{} blacklist triggers, across {} chats.".format(sql.num_blacklist_filters(),
                                                            sql.num_blacklist_filter_chats())


__mod_name__ = "Sözcük Karalistesi"

__help__ = """
Kara listeler, belirli tetikleyicilerin bir grupta söylenmesini durdurmak için kullanılır. Tetikleyiciden bahsedildiği zaman, \
mesaj hemen silinecek. İyi bir kombinasyon için uyarı filtreleriyle eşleştirilebilir!

*NOT:* kara listeler grup yöneticilerini etkilemez.

 - /blacklist: Mevcut kara listeye alınmış kelimeleri görüntüleyin.

*Sadece yöneticiler:*
 - /addblacklist <kelime>: Kara listeye bir tetikleyici ekleyin. Her satır bir tetikleyici olarak kabul edilir. \
bir çok satır birden çok tetikleyici eklemenize izin verir.
 - /unblacklist <kelime>: Tetikleyicileri kara listeden kaldırın. Burada aynı yeni satır mantığı geçerlidir, böylece \
birden çok tetikleyici kaldırabilirsiniz.
 - /rmblacklist <kelime>: Yukarıdaki ile aynı.
"""

BLACKLIST_HANDLER = CommandHandler("blacklist", blacklist, filters=Filters.group)
ADD_BLACKLIST_HANDLER = CommandHandler("addblacklist", add_blacklist, filters=Filters.group)
UNBLACKLIST_HANDLER = CommandHandler(["unblacklist", "rmblacklist"], unblacklist, filters=Filters.group)
BLACKLIST_DEL_HANDLER = MessageHandler(
    (Filters.text | Filters.command | Filters.sticker | Filters.photo) & Filters.group, del_blacklist)

dispatcher.add_handler(BLACKLIST_HANDLER)
dispatcher.add_handler(ADD_BLACKLIST_HANDLER)
dispatcher.add_handler(UNBLACKLIST_HANDLER)
dispatcher.add_handler(BLACKLIST_DEL_HANDLER, group=BLACKLIST_GROUP)
