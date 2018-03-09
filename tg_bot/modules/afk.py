from typing import Optional

from telegram import Message, Update, Bot, User
from telegram import MessageEntity
from telegram.ext import Filters, MessageHandler, run_async

from tg_bot import dispatcher
from tg_bot.modules.disable import DisableAbleCommandHandler, DisableAbleRegexHandler
from tg_bot.modules.sql import afk_sql as sql
from tg_bot.modules.users import get_user_id

AFK_GROUP = 7
AFK_REPLY_GROUP = 8


@run_async
def afk(bot: Bot, update: Update):
    args = update.effective_message.text.split(None, 1)
    if len(args) >= 2:
        reason = args[1]
    else:
        reason = ""

    sql.set_afk(update.effective_user.id, reason)
    update.effective_message.reply_text("{} şuan meşgul!".format(update.effective_user.first_name))


@run_async
def no_longer_afk(bot: Bot, update: Update):
    user = update.effective_user  # type: Optional[User]

    if not user:  # ignore channels
        return

    res = sql.rm_afk(user.id)
    if res:
        update.effective_message.reply_text("{} artık meşgul değil!".format(update.effective_user.first_name))


@run_async
def reply_afk(bot: Bot, update: Update):
    message = update.effective_message  # type: Optional[Message]
    if message.entities and message.parse_entities([MessageEntity.TEXT_MENTION]):
        entities = message.parse_entities([MessageEntity.TEXT_MENTION])
        for ent in entities:
            user_id = ent.user.id
            user = sql.check_afk_status(user_id)
            if user and user.is_afk:
                if not user.reason:
                    res = "{} şuan meşgul!".format(ent.user.first_name)
                else:
                    res = "{} şuan meşgul! Sebep:\n{}".format(ent.user.first_name, user.reason)
                message.reply_text(res)

    elif message.entities and message.parse_entities([MessageEntity.MENTION]):
        entities = message.parse_entities([MessageEntity.MENTION])
        for ent in entities:
            user_id = get_user_id(message.text[ent.offset:ent.offset + ent.length])
            if not user_id:
                # Should never happen, since for a user to become AFK they must have spoken. Maybe changed username?
                return
            user = sql.check_afk_status(user_id)
            if user and user.is_afk:
                chat = bot.get_chat(user_id)
                if not user.reason:
                    res = "{} şuan meşgul!".format(chat.first_name)
                else:
                    res = "{} şuan meşgul!\nSebep: {}".format(chat.first_name, user.reason)
                message.reply_text(res)

    else:
        return


__help__ = """
 - /afk <sebep>: kendini meşgul olarak işaretle.
 - brb <sebep>: afk komutu ile aynı - ama komut değil.

AFK olarak işaretlendiğinde, uygun olmadığınızı söyleyen bir mesajla herhangi bir görüşme yanıtlanacaktır.!
"""

__mod_name__ = "AFK"

AFK_HANDLER = DisableAbleCommandHandler("afk", afk)
AFK_REGEX_HANDLER = DisableAbleRegexHandler("(?i)brb", afk, friendly="afk")
NO_AFK_HANDLER = MessageHandler(Filters.all & Filters.group, no_longer_afk)
AFK_REPLY_HANDLER = MessageHandler(Filters.entity(MessageEntity.MENTION) | Filters.entity(MessageEntity.TEXT_MENTION),
                                   reply_afk)

dispatcher.add_handler(AFK_HANDLER, AFK_GROUP)
dispatcher.add_handler(AFK_REGEX_HANDLER, AFK_GROUP)
dispatcher.add_handler(NO_AFK_HANDLER, AFK_GROUP)
dispatcher.add_handler(AFK_REPLY_HANDLER, AFK_REPLY_GROUP)
