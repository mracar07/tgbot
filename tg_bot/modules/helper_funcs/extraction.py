from typing import List, Optional

from telegram import Message, MessageEntity
from telegram.error import BadRequest

from tg_bot import LOGGER
from tg_bot.modules.users import get_user_id


def extract_user(message: Message, args: List[str]) -> Optional[int]:
    prev_message = message.reply_to_message

    if message.entities and message.parse_entities([MessageEntity.TEXT_MENTION]):
        entities = list(message.parse_entities([MessageEntity.TEXT_MENTION]))
        ent = entities[0]
        user_id = ent.user.id

    elif len(args) >= 1 and args[0][0] == '@':
        user = args[0]
        user_id = get_user_id(user)
        if not user_id:
            message.reply_text("Bu kullanıcıyı db'mde yok. Onlarla etkileşimde bulunmamı istiyorsanız "
                               "kişinin mesajını yanıtlarsınız veya o kullanıcının mesajlarından birini yönlendirirsiniz.")
            return
        else:
            user_id = user_id

    elif len(args) >= 1 and args[0].isdigit():
        user_id = int(args[0])

    elif prev_message:
        user_id = prev_message.from_user.id

    else:
        return None

    try:
        message.bot.get_chat(user_id)
    except BadRequest as excp:
        if excp.message in ("User_id_invalid", "Chat not found"):
            message.reply_text("Bu kullanıcıyla daha önce etkileşimde bulunmamış gibi görünüyorum - lütfen "
                               "kontrolü bana ver ! (Vudu bebeği gibi, yapabilmeleri için belirli komutları yürütmek "
                               "parçaya ihtiyacım var...)")
        else:
            LOGGER.exception("Exception %s on user %s", excp.message, user_id)

        return

    return user_id


def extract_user_and_text(message: Message, args: List[str]) -> (Optional[int], Optional[str]):
    prev_message = message.reply_to_message

    text = ""

    if message.entities and message.parse_entities([MessageEntity.TEXT_MENTION]):
        entities = list(message.parse_entities([MessageEntity.TEXT_MENTION]))
        ent = entities[0]
        user_id = ent.user.id
        text = message.text[ent.offset + ent.length:]

    elif len(args) >= 1 and args[0][0] == '@':
        user = args[0]
        user_id = get_user_id(user)
        if not user_id:
            message.reply_text("Bu kullanıcıyı db'mde yok. Onlarla etkileşimde bulunmamı istiyorsanız "
                               "kişinin mesajını yanıtlarsınız veya o kullanıcının mesajlarından birini yönlendirirsiniz..")
            return None, None

        else:
            user_id = user_id
            res = message.text.split(None, 2)
            if len(res) >= 3:
                text = res[2]

    elif len(args) >= 1 and args[0].isdigit():
        user_id = int(args[0])
        res = message.text.split(None, 2)
        if len(res) >= 3:
            text = res[2]

    elif prev_message:
        user_id = prev_message.from_user.id
        res = message.text.split(None, 1)
        if len(res) >= 2:
            text = res[1]

    else:
        return None, None

    try:
        message.bot.get_chat(user_id)
    except BadRequest as excp:
        if excp.message in ("User_id_invalid", "Chat not found"):
            message.reply_text("Bu kullanıcıyla daha önce etkileşimde bulunmamış gibi görünüyorum - lütfen "
                               "kontrolü bana ver ! (Vudu bebeği gibi, yapabilmeleri için belirli komutları yürütmek "
                               "parçaya ihtiyacım var...)")
        else:
            LOGGER.exception("Exception %s on user %s", excp.message, user_id)

        return None, None

    return user_id, text


def extract_text(message) -> str:
    return message.text or message.caption or (message.sticker.emoji if message.sticker else None)
