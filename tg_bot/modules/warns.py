import html
import re
from typing import Optional, List

import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, User, CallbackQuery
from telegram import Message, Chat, Update, Bot
from telegram.error import BadRequest
from telegram.ext import CommandHandler, run_async, DispatcherHandlerStop, MessageHandler, Filters, CallbackQueryHandler
from telegram.utils.helpers import mention_html, mention_markdown, escape_markdown

from tg_bot import dispatcher, BAN_STICKER
from tg_bot.modules.disable import DisableAbleCommandHandler
from tg_bot.modules.helper_funcs.chat_status import is_user_admin, bot_admin, user_admin_no_reply, user_admin, \
    can_restrict
from tg_bot.modules.helper_funcs.extraction import extract_text, extract_user_and_text, extract_user
from tg_bot.modules.helper_funcs.filters import CustomFilters
from tg_bot.modules.helper_funcs.misc import split_message
from tg_bot.modules.helper_funcs.string_handling import split_quotes
from tg_bot.modules.log_channel import loggable
from tg_bot.modules.sql import warns_sql as sql

WARN_HANDLER_GROUP = 9
CURRENT_WARNING_FILTER_STRING = "*Bu sohbetteki mevcut uyarı filtreleri:*\n"


# Not async
def warn(user: User, chat: Chat, reason: str, message: Message, warner: User = None) -> str:
    if is_user_admin(chat, user.id):
        message.reply_text("Lanet yöneticiler, uyarılamazlar.!")
        return ""

    if warner:
        warner_tag = mention_html(warner.id, warner.first_name)
    else:
        warner_tag = "Automated warn filter."

    limit, soft_warn = sql.get_warn_setting(chat.id)
    num_warns, reasons = sql.warn_user(user.id, chat.id, reason)
    if num_warns >= limit:
        sql.reset_warns(user.id, chat.id)
        if soft_warn:  # kick
            chat.unban_member(user.id)
            reply = "{} uyarıya ulaştı, bu kullanıcı gruptan atıldı!".format(limit)

        else:  # ban
            chat.kick_member(user.id)
            reply = "{} uyarıya ulaştı, bu kullanıcı gruptan yasaklandı!".format(limit)

        message.bot.send_sticker(chat.id, BAN_STICKER)  # banhammer marie sticker
        keyboard = []
        reason = "<b>{}:</b>" \
                 "\n#WARN_BAN" \
                 "\n<b>Admin:</b> {}" \
                 "\n<b>User:</b> {}" \
                 "\n<b>Reason:</b> {}".format(html.escape(chat.title),
                                              warner_tag,
                                              mention_html(user.id, user.first_name), reason)

    else:
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Uyarıyı kaldır", callback_data="rm_warn({})".format(user.id))]])

        reply = "{} {}/{} uyarıya sahip... Dikkatli ol!".format(mention_markdown(user.id, user.first_name), num_warns,
                                                             limit)
        if reason:
            reply += "\nSon uyarının sebebi:\n{}".format(escape_markdown(reason))

        reason = "<b>{}:</b>" \
                 "\n#WARN" \
                 "\n<b>Admin:</b> {}" \
                 "\n<b>User:</b> {}" \
                 "\n<b>Reason:</b> {}".format(html.escape(chat.title),
                                              warner_tag,
                                              mention_html(user.id, user.first_name), reason)

    try:
        message.reply_text(reply, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    except BadRequest as excp:
        if excp.message == "Reply message not found":
            # Do not reply
            message.reply_text(reply, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN, quote=False)
        else:
            raise
    return reason


@run_async
@user_admin_no_reply
@bot_admin
@loggable
def button(bot: Bot, update: Update) -> str:
    query = update.callback_query  # type: Optional[CallbackQuery]
    user = update.effective_user  # type: Optional[User]
    match = re.match(r"rm_warn\((.+?)\)", query.data)
    if match:
        user_id = match.group(1)
        chat = update.effective_chat  # type: Optional[Chat]
        res = sql.remove_warn(user_id, chat.id)
        if res:
            update.effective_message.edit_text(
                "Uyarı {} tarafından kaldırıldı.".format(mention_markdown(user.id, user.first_name)),
                parse_mode=ParseMode.MARKDOWN)
            user_member = chat.get_member(user_id)
            return "<b>{}:</b>" \
                   "\n#UNWARN" \
                   "\n<b>Admin:</b> {}" \
                   "\n<b>User:</b> {}".format(html.escape(chat.title),
                                              mention_html(user.id, user.first_name),
                                              mention_html(user_member.user.id, user_member.user.first_name))
    return ""


@run_async
@user_admin
@can_restrict
@loggable
def warn_user(bot: Bot, update: Update, args: List[str]) -> str:
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    warner = update.effective_user  # type: Optional[User]

    user_id, reason = extract_user_and_text(message, args)

    if user_id:
        if message.reply_to_message and message.reply_to_message.from_user.id == user_id:
            return warn(message.reply_to_message.from_user, chat, reason, message.reply_to_message, warner)
        else:
            return warn(chat.get_member(user_id).user, chat, reason, message, warner)
    else:
        message.reply_text("Hiçbir kullanıcı belirlenmedi!")
    return ""


@run_async
@user_admin
@bot_admin
@loggable
def reset_warns(bot: Bot, update: Update, args: List[str]) -> str:
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]

    user_id = extract_user(message, args)
    if user_id:
        sql.reset_warns(user_id, chat.id)
        message.reply_text("Uyarılar sıfırlandı!")
        warned = chat.get_member(user_id).user
        return "<b>{}:</b>" \
               "\n#RESETWARNS" \
               "\n<b>Admin:</b> {}" \
               "\n<b>User:</b> {}".format(html.escape(chat.title),
                                          mention_html(user.id, user.first_name),
                                          mention_html(warned.id, warned.first_name))
    else:
        message.reply_text("Hiçbir kullanıcı belirlenmedi!")
    return ""


@run_async
def warns(bot: Bot, update: Update, args: List[str]):
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    user_id = extract_user(message, args) or update.effective_user.id
    result = sql.get_warns(user_id, chat.id)

    if result and result[0] != 0:
        num_warns, reasons = result
        limit, soft_warn = sql.get_warn_setting(chat.id)

        if reasons:
            text = "Bu kullanıcı {}/{} uyarıya sahip, aşağıdaki sebeplerden dolayı:".format(num_warns, limit)
            for reason in reasons:
                text += "\n - {}".format(reason)

            msgs = split_message(text)
            for msg in msgs:
                update.effective_message.reply_text(msg)
        else:
            update.effective_message.reply_text(
                "Bu kullanıcı {}/{} uyarıya sahip, ama hiçbir zaman sebep belirtilmemiş.".format(num_warns, limit))
    else:
        update.effective_message.reply_text("Bu kullanıcının herhangi bir uyarısı yok!")


# Dispatcher handler stop - do not async
@user_admin
def add_warn_filter(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]

    args = msg.text.split(None, 1)  # use python's maxsplit to separate Cmd, keyword, and reply_text

    if len(args) < 2:
        return

    extracted = split_quotes(args[1])

    if len(extracted) >= 2:
        # set trigger -> lower, so as to avoid adding duplicate filters with different cases
        keyword = extracted[0].lower()
        content = extracted[1]

    else:
        return

    # Note: perhaps handlers can be removed somehow using sql.get_chat_filters
    for handler in dispatcher.handlers.get(WARN_HANDLER_GROUP, []):
        if handler.filters == (keyword, chat.id):
            dispatcher.remove_handler(handler, WARN_HANDLER_GROUP)

    sql.add_warn_filter(chat.id, keyword, content)

    update.effective_message.reply_text("Otomatik uyarı '{}' kelimesi için aktif!".format(keyword))
    raise DispatcherHandlerStop


@user_admin
def remove_warn_filter(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat  # type: Optional[Chat]

    if len(args) < 1:
        return

    chat_filters = sql.get_chat_warn_filters(chat.id)

    if not chat_filters:
        update.effective_message.reply_text("Burada hiçbir uyarı filtresi aktif değil!")
        return

    for filt in chat_filters:
        if filt.chat_id == str(chat.id) and filt.keyword == args[0]:
            sql.remove_warn_filter(chat.id, args[0])
            update.effective_message.reply_text("Evet, bunun için insanları uyarmayı bırakacağım.")
            raise DispatcherHandlerStop

    update.effective_message.reply_text("Bu geçerli bir uyarı filtresi değil - görmek için /warnlist \
    komutunu çalıştırın.")


@run_async
def list_warn_filters(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    all_handlers = sql.get_chat_warn_filters(chat.id)

    if not all_handlers:
        update.effective_message.reply_text("Burada hiçbir uyarı filtresi aktif değil!")
        return

    filter_list = CURRENT_WARNING_FILTER_STRING
    for handler in all_handlers:
        entry = " - {}\n".format(escape_markdown(handler.keyword))
        if len(entry) + len(filter_list) > telegram.MAX_MESSAGE_LENGTH:
            update.effective_message.reply_text(filter_list, parse_mode=ParseMode.MARKDOWN)
            filter_list = entry
        else:
            filter_list += entry

    if not filter_list == CURRENT_WARNING_FILTER_STRING:
        update.effective_message.reply_text(filter_list, parse_mode=ParseMode.MARKDOWN)


@run_async
@loggable
def reply_filter(bot: Bot, update: Update) -> str:
    chat_warn_filters = sql.get_chat_warn_filters(update.effective_chat.id)
    message = update.effective_message  # type: Optional[Message]
    to_match = extract_text(message)
    if not to_match:
        return ""

    for warn_filter in chat_warn_filters:
        pattern = r"( |^|[^\w])" + re.escape(warn_filter.keyword) + r"( |$|[^\w])"
        if re.search(pattern, to_match, flags=re.IGNORECASE):
            user = update.effective_user  # type: Optional[User]
            chat = update.effective_chat  # type: Optional[Chat]
            return warn(user, chat, warn_filter.reply, message)
    return ""


@run_async
@user_admin
@loggable
def set_warn_limit(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]

    if args:
        if args[0].isdigit():
            if int(args[0]) < 3:
                msg.reply_text("Minimum uyarı limiti 3!")
            else:
                sql.set_warn_limit(chat.id, int(args[0]))
                msg.reply_text("Updated the warn limit to {}".format(args[0]))
                return "<b>{}:</b>" \
                       "\n#SET_WARN_LIMIT" \
                       "\n<b>Admin:</b> {}" \
                       "\nSet the warn limit to <code>{}</code>".format(html.escape(chat.title),
                                                                        mention_html(user.id, user.first_name), args[0])
        else:
            msg.reply_text("Ayarlamam için bana bir sayı ver!")
    else:
        limit, soft_warn = sql.get_warn_setting(chat.id)

        msg.reply_text("Mevcut uyarı sınırı {}".format(limit))
    return ""


@run_async
@user_admin
def set_warn_strength(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]

    if args:
        if args[0].lower() in ("on", "yes"):
            sql.set_warn_strength(chat.id, False)
            msg.reply_text("Çok fazla uyarı, artık yasakla sonuçlanacak!")
            return "<b>{}:</b>\n" \
                   "<b>Admin:</b> {}\n" \
                   "Has enabled strong warns. Users will be banned.".format(html.escape(chat.title),
                                                                            mention_html(user.id, user.first_name))

        elif args[0].lower() in ("off", "no"):
            sql.set_warn_strength(chat.id, True)
            msg.reply_text("Çok fazla uyarı artık gruptan atılma ile sonuçlanacak! Kullanıcılar sonra tekrar katılabilecektir.")
            return "<b>{}:</b>\n" \
                   "<b>Admin:</b> {}\n" \
                   "Has disabled strong warns. Users will only be kicked.".format(html.escape(chat.title),
                                                                                  mention_html(user.id,
                                                                                               user.first_name))

        else:
            msg.reply_text("ben sadece on/yes/no/off komutlarını anlıyorum!")
    else:
        limit, soft_warn = sql.get_warn_setting(chat.id)
        if soft_warn:
            msg.reply_text("Uyarılar şu anda limitleri aştığında *gruptan at* olarak ayarlandı.",
                           parse_mode=ParseMode.MARKDOWN)
        else:
            msg.reply_text("Uyarılar şu anda limitleri aştığında *gruptan yasakla* olarak ayarlandı.",
                           parse_mode=ParseMode.MARKDOWN)
    return ""


def __stats__():
    return "{} overall warns, across {} chats.\n" \
           "{} warn filters, across {} chats.".format(sql.num_warns(), sql.num_warn_chats(),
                                                      sql.num_warn_filters(), sql.num_warn_filter_chats())


def __import_data__(chat_id, data):
    for user_id, count in data.get('warns', {}).items():
        for x in range(int(count)):
            sql.warn_user(user_id, chat_id)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    num_warn_filters = sql.num_warn_chat_filters(chat_id)
    limit, soft_warn = sql.get_warn_setting(chat_id)
    return "This chat has `{}` warn filters. It takes `{}` warns " \
           "before the user gets *{}*.".format(num_warn_filters, limit, "kicked" if soft_warn else "banned")


__help__ = """
 - /warns <kullanıcıadı>: Bir kullanıcının uyarılarını al.
 - /warnlist: tüm geçerli uyarı filtrelerinin listesi

*Sadece yöneticiler:*
 - /warn <userhandle>: Kullanıcıyı uyar. 3 uyarmadan sonra, kullanıcı gruptan yasaklanacak. Bir cevap olarak da kullanılabilir.
 - /resetwarn <userhandle>: Bir kullanıcı için uyarıları sıfırlayın. Bir cevap olarak da kullanılabilir.
 - /addwarn <keyword> <reply message>: Belirli bir anahtar kelime üzerinde bir uyarı filtresi ayarlayın. Anahtar kelimenizi \
bir cümle olarak tırnak içine alın, Yani: `/addwarn "küfür küfür" Küfür yasak`. 
 - /nowarn <keyword>: uyarı filtresini durdur
 - /warnlimit <num>: uyarı limitini ayarla
 - /strongwarn <on/yes/off/no>: Açık olarak ayarlanmışsa, uyarı limitini aşmak bir yasakla sonuçlanır. kapalı olarak ayarlanmışsa, gruptan atacak.
"""

__mod_name__ = "Uyarılar"

WARN_HANDLER = CommandHandler("warn", warn_user, pass_args=True, filters=Filters.group)
RESET_WARN_HANDLER = CommandHandler("resetwarn", reset_warns, pass_args=True, filters=Filters.group)
CALLBACK_QUERY_HANDLER = CallbackQueryHandler(button, pattern=r"rm_warn")
MYWARNS_HANDLER = DisableAbleCommandHandler("warns", warns, pass_args=True, filters=Filters.group)
ADD_WARN_HANDLER = CommandHandler("addwarn", add_warn_filter, filters=Filters.group)
RM_WARN_HANDLER = CommandHandler(["nowarn", "stopwarn"], remove_warn_filter, pass_args=True, filters=Filters.group)
LIST_WARN_HANDLER = DisableAbleCommandHandler("warnlist", list_warn_filters, filters=Filters.group)
WARN_FILTER_HANDLER = MessageHandler(CustomFilters.has_text & Filters.group, reply_filter)
WARN_LIMIT_HANDLER = CommandHandler("warnlimit", set_warn_limit, pass_args=True, filters=Filters.group)
WARN_STRENGTH_HANDLER = CommandHandler("strongwarn", set_warn_strength, pass_args=True, filters=Filters.group)

dispatcher.add_handler(WARN_HANDLER)
dispatcher.add_handler(CALLBACK_QUERY_HANDLER)
dispatcher.add_handler(RESET_WARN_HANDLER)
dispatcher.add_handler(MYWARNS_HANDLER)
dispatcher.add_handler(ADD_WARN_HANDLER)
dispatcher.add_handler(RM_WARN_HANDLER)
dispatcher.add_handler(LIST_WARN_HANDLER)
dispatcher.add_handler(WARN_LIMIT_HANDLER)
dispatcher.add_handler(WARN_STRENGTH_HANDLER)
dispatcher.add_handler(WARN_FILTER_HANDLER, WARN_HANDLER_GROUP)
