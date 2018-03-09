import html
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User
from telegram import ParseMode, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import MessageHandler, Filters, CommandHandler, run_async
from telegram.utils.helpers import mention_markdown, mention_html, escape_markdown

import tg_bot.modules.sql.welcome_sql as sql
from tg_bot import dispatcher, OWNER_ID, LOGGER
from tg_bot.modules.helper_funcs.chat_status import user_admin
from tg_bot.modules.helper_funcs.misc import build_keyboard
from tg_bot.modules.helper_funcs.string_handling import button_markdown_parser, markdown_parser, \
    escape_invalid_curly_brackets
from tg_bot.modules.log_channel import loggable

VALID_WELCOME_FORMATTERS = ['first', 'last', 'fullname', 'username', 'id', 'count', 'chatname', 'mention']

ENUM_FUNC_MAP = {
    sql.Types.TEXT.value: dispatcher.bot.send_message,
    sql.Types.BUTTON_TEXT.value: dispatcher.bot.send_message,
    sql.Types.STICKER.value: dispatcher.bot.send_sticker,
    sql.Types.DOCUMENT.value: dispatcher.bot.send_document,
    sql.Types.PHOTO.value: dispatcher.bot.send_photo,
    sql.Types.AUDIO.value: dispatcher.bot.send_audio,
    sql.Types.VOICE.value: dispatcher.bot.send_voice,
    sql.Types.VIDEO.value: dispatcher.bot.send_video
}


# do not async
def send(update, message, keyboard, backup_message):
    try:
        update.effective_message.reply_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    except IndexError:
        update.effective_message.reply_text(markdown_parser(backup_message +
                                                            "\nNot: Mevcut mesaj "
                                                            "Markdown sorunları nedeniyle geçersiz. "
                                                            "Kullanıcının adı nedeniyle olabilir."),
                                            parse_mode=ParseMode.MARKDOWN)
    except KeyError:
        update.effective_message.reply_text(markdown_parser(backup_message +
                                                            "\nNot: Mevcut mesaj "
                                                            "bazı yanlış yerleştirilmiş parantez sorunları nedeniyle geçersiz "
                                                            "Lütfen güncelle"),
                                            parse_mode=ParseMode.MARKDOWN)
    except BadRequest as excp:
        if excp.message == "Button_url_invalid":
            update.effective_message.reply_text(markdown_parser(backup_message +
                                                                "\nNot: Mevcut mesajın içindeki bir butonda geçersiz bir URL var "
                                                                "one of its buttons. Please update."),
                                                parse_mode=ParseMode.MARKDOWN)
        elif excp.message == "Unsupported url protocol":
            update.effective_message.reply_text(markdown_parser(backup_message +
                                                                "\nNot: Mevcut mesaj "
                                                                "telegram tarafından desteklenmeyen URL protokolleri var. "
                                                                "Lütfen güncelle"),
                                                parse_mode=ParseMode.MARKDOWN)
        elif excp.message == "Wrong url host":
            update.effective_message.reply_text(markdown_parser(backup_message +
                                                                "\nNot: Mevcut mesajın bazı hatalı URL'leri var. "
                                                                "Lütfen güncelle"),
                                                parse_mode=ParseMode.MARKDOWN)
            LOGGER.warning(message)
            LOGGER.warning(keyboard)
            LOGGER.exception("Could not parse! got invalid url host errors")
        else:
            update.effective_message.reply_text(markdown_parser(backup_message +
                                                                "\nNot: Özel mesaj gönderilirken bir sorun oluştu. "
                                                                "Lütfen güncelle."),
                                                parse_mode=ParseMode.MARKDOWN)
            LOGGER.exception()


@run_async
def new_member(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]

    should_welc, cust_welcome, welc_type = sql.get_welc_pref(chat.id)
    if should_welc:
        new_members = update.effective_message.new_chat_members
        for new_mem in new_members:
            # Give the owner a special welcome
            if new_mem.id == OWNER_ID:
                update.effective_message.reply_text("Hoşgeldin Başkan. Partiyi başlatalım mı?")
                continue

            # Don't welcome yourself
            elif new_mem.id == bot.id:
                continue

            else:
                # If welcome message is media, send with appropriate function
                if welc_type != sql.Types.TEXT and welc_type != sql.Types.BUTTON_TEXT:
                    ENUM_FUNC_MAP[welc_type](chat.id, cust_welcome)
                    return
                # else, move on
                first_name = new_mem.first_name or "PersonWithNoName"  # edge case of empty name - occurs for some bugs.

                if cust_welcome:
                    if new_mem.last_name:
                        fullname = "{} {}".format(first_name, new_mem.last_name)
                    else:
                        fullname = first_name
                    count = chat.get_members_count()
                    mention = mention_markdown(new_mem.id, first_name)
                    if new_mem.username:
                        username = "@" + escape_markdown(new_mem.username)
                    else:
                        username = mention

                    valid_format = escape_invalid_curly_brackets(cust_welcome, VALID_WELCOME_FORMATTERS)
                    res = valid_format.format(first=escape_markdown(first_name),
                                              last=escape_markdown(new_mem.last_name or first_name),
                                              fullname=escape_markdown(fullname), username=username, mention=mention,
                                              count=count, chatname=escape_markdown(chat.title), id=new_mem.id)
                    buttons = sql.get_welc_buttons(chat.id)
                    keyb = build_keyboard(buttons)
                else:
                    res = sql.DEFAULT_WELCOME.format(first=first_name)
                    keyb = []

                keyboard = InlineKeyboardMarkup(keyb)

                send(update, res, keyboard, sql.DEFAULT_WELCOME.format(first=first_name))


@run_async
def left_member(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    should_goodbye, cust_goodbye, goodbye_type = sql.get_gdbye_pref(chat.id)
    if should_goodbye:
        left_mem = update.effective_message.left_chat_member
        if left_mem:
            # Ignore bot being kicked
            if left_mem.id == bot.id:
                return

            # Give the owner a special goodbye
            if left_mem.id == OWNER_ID:
                update.effective_message.reply_text("Görüşürüz Başkan")
                return

            # if media goodbye, use appropriate function for it
            if goodbye_type != sql.Types.TEXT and goodbye_type != sql.Types.BUTTON_TEXT:
                ENUM_FUNC_MAP[goodbye_type](chat.id, cust_goodbye)
                return

            first_name = left_mem.first_name or "PersonWithNoName"  # edge case of empty name - occurs for some bugs.
            if cust_goodbye:
                if left_mem.last_name:
                    fullname = "{} {}".format(first_name, left_mem.last_name)
                else:
                    fullname = first_name
                count = chat.get_members_count()
                mention = mention_markdown(left_mem.id, first_name)
                if left_mem.username:
                    username = "@" + escape_markdown(left_mem.username)
                else:
                    username = mention

                valid_format = escape_invalid_curly_brackets(cust_goodbye, VALID_WELCOME_FORMATTERS)
                res = valid_format.format(first=escape_markdown(first_name),
                                          last=escape_markdown(left_mem.last_name or first_name),
                                          fullname=escape_markdown(fullname), username=username, mention=mention,
                                          count=count, chatname=escape_markdown(chat.title), id=left_mem.id)
                buttons = sql.get_gdbye_buttons(chat.id)
                keyb = build_keyboard(buttons)

            else:
                res = sql.DEFAULT_GOODBYE
                keyb = []

            keyboard = InlineKeyboardMarkup(keyb)

            send(update, res, keyboard, sql.DEFAULT_GOODBYE)


@run_async
@user_admin
def welcome(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat  # type: Optional[Chat]
    # if no args, show current replies.
    if len(args) == 0:
        pref, welcome_m, welcome_type = sql.get_welc_pref(chat.id)
        update.effective_message.reply_text(
            "Bu sohbet şuna ayarlandı: `{}`.\n*Şuanki hoşgeldin mesajı:*".format(pref),
            parse_mode=ParseMode.MARKDOWN)

        if welcome_type == sql.Types.BUTTON_TEXT:
            buttons = sql.get_welc_buttons(chat.id)
            keyb = build_keyboard(buttons)
            keyboard = InlineKeyboardMarkup(keyb)

            send(update, welcome_m, keyboard, sql.DEFAULT_WELCOME)

        else:
            ENUM_FUNC_MAP[welcome_type](chat.id, welcome_m)

    elif len(args) >= 1:
        if args[0].lower() in ("on", "yes"):
            sql.set_welc_preference(str(chat.id), True)
            update.effective_message.reply_text("Kibar olurum!")

        elif args[0].lower() in ("off", "no"):
            sql.set_welc_preference(str(chat.id), False)
            update.effective_message.reply_text("Suratsızım, artık merhaba demiyorum.")

        else:
            # idek what you're writing, say yes or no
            update.effective_message.reply_text("Ben sadece 'on/yes' veya 'off/no' anlıyorum!")


@run_async
@user_admin
def goodbye(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat  # type: Optional[Chat]

    if len(args) == 0:
        pref, goodbye_m, goodbye_type = sql.get_gdbye_pref(chat.id)
        update.effective_message.reply_text(
            "Bu sohbet için, elveda ayarı: `{}`.\n*Şuan ayrılma mesajı:*".format(pref),
            parse_mode=ParseMode.MARKDOWN)

        if goodbye_type == sql.Types.BUTTON_TEXT:
            buttons = sql.get_gdbye_buttons(chat.id)
            keyb = build_keyboard(buttons)

            keyboard = InlineKeyboardMarkup(keyb)

            send(update, goodbye_m, keyboard, sql.DEFAULT_GOODBYE)

        else:
            ENUM_FUNC_MAP[goodbye_type](chat.id, goodbye_m)

    elif len(args) >= 1:
        if args[0].lower() in ("on", "yes"):
            sql.set_gdbye_preference(str(chat.id), True)
            update.effective_message.reply_text("Insanlar ayrılırken üzgün olacağım!")

        elif args[0].lower() in ("off", "no"):
            sql.set_gdbye_preference(str(chat.id), False)
            update.effective_message.reply_text("Ayrıldılar, benim için öldüler.")

        else:
            # idek what you're writing, say yes or no
            update.effective_message.reply_text("Ben sadece 'on/yes' veya 'off/no' anlıyorum!")


@run_async
@user_admin
@loggable
def set_welcome(bot: Bot, update: Update) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]
    raw_text = msg.text
    args = raw_text.split(None, 1)  # use python's maxsplit to separate cmd and args

    buttons = []
    # determine what the contents of the filter are - text, image, sticker, etc
    if len(args) >= 2:
        offset = len(args[1]) - len(msg.text)  # set correct offset relative to command + notename
        content, buttons = button_markdown_parser(args[1], entities=msg.parse_entities(), offset=offset)
        if buttons:
            data_type = sql.Types.BUTTON_TEXT
        else:
            data_type = sql.Types.TEXT

    elif msg.reply_to_message and msg.reply_to_message.sticker:
        content = msg.reply_to_message.sticker.file_id
        data_type = sql.Types.STICKER

    elif msg.reply_to_message and msg.reply_to_message.document:
        content = msg.reply_to_message.document.file_id
        data_type = sql.Types.DOCUMENT

    elif msg.reply_to_message and msg.reply_to_message.photo:
        content = msg.reply_to_message.photo[-1].file_id  # last elem = best quality
        data_type = sql.Types.PHOTO

    elif msg.reply_to_message and msg.reply_to_message.audio:
        content = msg.reply_to_message.audio.file_id
        data_type = sql.Types.AUDIO

    elif msg.reply_to_message and msg.reply_to_message.voice:
        content = msg.reply_to_message.voice.file_id
        data_type = sql.Types.VOICE

    elif msg.reply_to_message and msg.reply_to_message.video:
        content = msg.reply_to_message.video.file_id
        data_type = sql.Types.VIDEO

    else:
        msg.reply_text("Neyle yanıt vereceğinizi belirtmediniz!")
        return ""

    sql.set_custom_welcome(chat.id, content, data_type, buttons)
    update.effective_message.reply_text("Özel karşılama mesajı başarıyla ayarlandı!")

    return "<b>{}:</b>" \
           "\n#SET_WELCOME" \
           "\n<b>Admin:</b> {}" \
           "\nSet the welcome message.".format(html.escape(chat.title),
                                               mention_html(user.id, user.first_name))


@run_async
@user_admin
@loggable
def reset_welcome(bot: Bot, update: Update) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    sql.set_custom_welcome(chat.id, sql.DEFAULT_WELCOME, sql.Types.TEXT)
    update.effective_message.reply_text("Karşılama mesajını varsayılan olarak sıfırlandı!")
    return "<b>{}:</b>" \
           "\n#RESET_WELCOME" \
           "\n<b>Admin:</b> {}" \
           "\nReset the welcome message to default.".format(html.escape(chat.title),
                                                            mention_html(user.id, user.first_name))


@run_async
@user_admin
@loggable
def set_goodbye(bot: Bot, update: Update) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]
    raw_text = msg.text
    args = raw_text.split(None, 1)  # use python's maxsplit to separate cmd and args

    buttons = []
    # determine what the contents of the filter are - text, image, sticker, etc
    if len(args) >= 2:
        offset = len(args[1]) - len(msg.text)  # set correct offset relative to command + notename
        content, buttons = button_markdown_parser(args[1], entities=msg.parse_entities(), offset=offset)
        if buttons:
            data_type = sql.Types.BUTTON_TEXT
        else:
            data_type = sql.Types.TEXT

    elif msg.reply_to_message and msg.reply_to_message.sticker:
        content = msg.reply_to_message.sticker.file_id
        data_type = sql.Types.STICKER

    elif msg.reply_to_message and msg.reply_to_message.document:
        content = msg.reply_to_message.document.file_id
        data_type = sql.Types.DOCUMENT

    elif msg.reply_to_message and msg.reply_to_message.photo:
        content = msg.reply_to_message.photo[-1].file_id  # last elem = best quality
        data_type = sql.Types.PHOTO

    elif msg.reply_to_message and msg.reply_to_message.audio:
        content = msg.reply_to_message.audio.file_id
        data_type = sql.Types.AUDIO

    elif msg.reply_to_message and msg.reply_to_message.voice:
        content = msg.reply_to_message.voice.file_id
        data_type = sql.Types.VOICE

    elif msg.reply_to_message and msg.reply_to_message.video:
        content = msg.reply_to_message.video.file_id
        data_type = sql.Types.VIDEO

    else:
        msg.reply_text("Ne cevap vereceğinizi belirtmedinizh!")
        return ""

    sql.set_custom_gdbye(chat.id, content, data_type, buttons)
    update.effective_message.reply_text("Özel hoşçakal mesajı başarıyla ayarlandı!")
    return "<b>{}:</b>" \
           "\n#SET_GOODBYE" \
           "\n<b>Admin:</b> {}" \
           "\nSet the goodbye message.".format(html.escape(chat.title),
                                               mention_html(user.id, user.first_name))


@run_async
@user_admin
@loggable
def reset_goodbye(bot: Bot, update: Update) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    sql.set_custom_gdbye(chat.id, sql.DEFAULT_GOODBYE, sql.Types.TEXT)
    update.effective_message.reply_text("Hoşçakal mesajını varsayılan olarak sıfırlandı!")
    return "<b>{}:</b>" \
           "\n#RESET_GOODBYE" \
           "\n<b>Admin:</b> {}" \
           "\nReset the goodbye message.".format(html.escape(chat.title),
                                                 mention_html(user.id, user.first_name))


WELC_HELP_TXT = "Grubumuzun karşılama / güle güle mesajları çok yönlü kişiselleştirilebilir. Bu mesajları ayarlamak istiyorsan" \
                " Varsayılan karşılama mesajı gibi bireysel olarak oluşturulmak için * bu * değişkenleri kullanabilirsiniz:\n" \
                " - `{{first}}`: Bu, kullanıcının * ilk * adını temsil eder\n" \
                " - `{{last}}`: Bu kullanıcının * son * adını temsil eder. " \
                "Eğer sahip değilse ilk adı kullanır.\n" \
                " - `{{fullname}}`: Bu kullanıcının * tam * adını temsil eder. Kullanıcı adı yoksa * ilk ad * için varsayılan değerdir " \
                ".\n" \
                " - `{{username}}`: Bu kullanıcının * kullanıcı adını * temsil eder. Kullanıcının * bahsine * göre belirlenen değerler" \
                "KUllanıcı adı yoksa ilk isim kullanılır.\n" \
                " - `{{mention}}`: Bu basitçe * bir kullanıcı - ilk adlarıyla onları etiketlediğinden bahseder.\n" \
                " - `{{id}}`: Bu kullanıcının *id*\n" \
                " - `{{count}}`: Bu, kullanıcının * üye numarasını temsil eder *.\n" \
                " - `{{chatname}}`: bu * geçerli sohbet adını temsil eder *.\n" \
                "\nHer değişken, değiştirilmek üzere {{}} `ile çevrelenmelidir ZORUNLU.\n" \
                "Hoş geldiniz mesajları ayrıca işaretlemeyi de destekler, böylece herhangi bir öğeyi kalın / italik / kod / bağlantılar yapabilirsiniz." \
                "Düğmeler de destekleniyor, bu yüzden hoş intro ile hoş görünmenizi sağlayabilirsiniz." \
                ".\n" \
                "Kurallarınıza bağlanan bir düğme oluşturmak için bunu kullanın: `[Rules](buttonurl://t.me/{}?start=group_id)`. " \
                "'Group_id' ifadesini grubunuzun kimliğiyle değiştirin. Bu, /id yoluyla edinilebilir. " \
                "Grup kimlikleri genellikle bir `-` işareti ile önceliğe sahiptir; bu gerekli, lütfen " \
                "bunu kaldırmayın.\n" \
                "Eğlenceli hissediyorsanız, hoş geldiniz mesajı olarak görüntüleri / gifleri / videoları / sesli mesajları bile ayarlayabilirsiniz " \
                "İstenen medyaya /setwelcome ile cevap vererek ayarlayabilirsiniz".format(dispatcher.bot.username)


@run_async
@user_admin
def welcome_help(bot: Bot, update: Update):
    update.effective_message.reply_text(WELC_HELP_TXT, parse_mode=ParseMode.MARKDOWN)


# TODO: get welcome data from group butler snap
# def __import_data__(chat_id, data):
#     welcome = data.get('info', {}).get('rules')
#     welcome = welcome.replace('$username', '{username}')
#     welcome = welcome.replace('$name', '{fullname}')
#     welcome = welcome.replace('$id', '{id}')
#     welcome = welcome.replace('$title', '{chatname}')
#     welcome = welcome.replace('$surname', '{lastname}')
#     welcome = welcome.replace('$rules', '{rules}')
#     sql.set_custom_welcome(chat_id, welcome, sql.Types.TEXT)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    welcome_pref, _, _ = sql.get_welc_pref(chat_id)
    goodbye_pref, _, _ = sql.get_gdbye_pref(chat_id)
    return "This chat has it's welcome preference set to `{}`.\n" \
           "It's goodbye preference is `{}`.".format(welcome_pref, goodbye_pref)


__help__ = """
{}

*Sadece yöneticiler:*
 - /welcome <on/off>: karşılama mesajlarını etkinleştir / devre dışı bırak. Arg olmadan kullanılırsa, geçerli ayarları gösterir.
 - /goodbye <on/off>: Hoşçakal mesajlarını etkinleştir / devre dışı bırak. Arg olmadan kullanılırsa, geçerli ayarları gösterir.
 - /setwelcome <sometext>: özel bir karşılama mesajı ayarlayın. Medyaya yanıt olarak kullanılıyorsa, o medyayı kullanır.
 - /setgoodbye <sometext>: özel bir hoşçakal mesajı ayarla. Medyaya yanıt olarak kullanılıyorsa, o medyayı kullanır.
 - /resetwelcome: Varsayılan karşılama mesajına sıfırla.
 - /resetgoodbye: Varsayılan hoşçakal mesajına sıfırla.
 
 - /welcomehelp: özel karşılama / güle güle iletileri için daha fazla biçimlendirme bilgisi görüntüleyin.
""".format(WELC_HELP_TXT)

__mod_name__ = "Hoşgeldin/Veda Mesajları"

NEW_MEM_HANDLER = MessageHandler(Filters.status_update.new_chat_members, new_member)
LEFT_MEM_HANDLER = MessageHandler(Filters.status_update.left_chat_member, left_member)
WELC_PREF_HANDLER = CommandHandler("welcome", welcome, pass_args=True, filters=Filters.group)
GOODBYE_PREF_HANDLER = CommandHandler("goodbye", goodbye, pass_args=True, filters=Filters.group)
SET_WELCOME = CommandHandler("setwelcome", set_welcome, filters=Filters.group)
SET_GOODBYE = CommandHandler("setgoodbye", set_goodbye, filters=Filters.group)
RESET_WELCOME = CommandHandler("resetwelcome", reset_welcome, filters=Filters.group)
RESET_GOODBYE = CommandHandler("resetgoodbye", reset_goodbye, filters=Filters.group)
WELCOME_HELP = CommandHandler("welcomehelp", welcome_help)

dispatcher.add_handler(NEW_MEM_HANDLER)
dispatcher.add_handler(LEFT_MEM_HANDLER)
dispatcher.add_handler(WELC_PREF_HANDLER)
dispatcher.add_handler(GOODBYE_PREF_HANDLER)
dispatcher.add_handler(SET_WELCOME)
dispatcher.add_handler(SET_GOODBYE)
dispatcher.add_handler(RESET_WELCOME)
dispatcher.add_handler(RESET_GOODBYE)
dispatcher.add_handler(WELCOME_HELP)
