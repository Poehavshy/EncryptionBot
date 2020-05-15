import config
import pymysql
import const
import datetime
import cryptographer
import logging
from telegram.ext import Updater, Filters
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler
from telegram import ReplyKeyboardMarkup


logger = logging.getLogger(__name__)

i_handler = logging.FileHandler('info.log')
c_handler = logging.FileHandler('error.log')
f_handler = logging.FileHandler('error.log')
i_handler.setLevel(logging.INFO)
c_handler.setLevel(logging.WARNING)
f_handler.setLevel(logging.ERROR)

i_format = logging.Formatter('%(asctime)s - %(name)s - %(message)s')
c_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
i_handler.setFormatter(i_format)
c_handler.setFormatter(c_format)
f_handler.setFormatter(f_format)

logger.setLevel(logging.INFO)
logger.addHandler(i_handler)
logger.addHandler(c_handler)
logger.addHandler(f_handler)


def start(update, context):
    """
    Стартовый метод для бота. Сброс статуса или регистрация нового пользователя.

    :param update: Объект для работы с ботом.
    :param context: Контекст работы бота.
    """
    con = pymysql.connect(config.DB_SERVER, config.DB_USER, config.DB_PASSWORD, config.DB_DATABASE)
    with con:
        cur = con.cursor()
        cur.execute(f"SELECT * FROM `Users` WHERE `telegram_id` = '{update.message.from_user.id}';")
        if cur.rowcount == 0:
            cur.execute(f"INSERT INTO `Users` SET `telegram_id`='{update.message.from_user.id}',"
                        f"`name`='{update.message.from_user.first_name}', "
                        f"`status`='{const.State.START}', `image`=NULL, `text`=NULL, `crypto_key`=NULL;")
            logger.info(f'New user with id: {update.message.from_user.id}')
        else:
            cur.execute(f"UPDATE `Users` SET `name`='{update.message.from_user.first_name}', "
                        f"`status`='{const.State.START}', `image`=NULL, `text`=NULL, "
                        f"`crypto_key`=NULL WHERE `telegram_id`='{update.message.from_user.id}';")
        con.commit()
        reply_markup = ReplyKeyboardMarkup(
            [['Шифрование', 'Дешифрование']],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        update.message.reply_text(
            text="Приветствую, я CryptoBot, умею шифровать сообщение в картинку.",
            reply_markup=reply_markup
        )


def message(update, context):
    con = pymysql.connect(config.DB_SERVER, config.DB_USER, config.DB_PASSWORD, config.DB_DATABASE)
    with con:
        cur = con.cursor()
        cur.execute(f"SELECT `status` FROM `Users` WHERE `telegram_id` = '{update.message.from_user.id}';")
        if cur.rowcount == 0:
            return
        res = cur.fetchall()
        status = res[0][0]
        user_id = update.message.from_user.id
        mess = update.message.text.lower()
        logger.info(f'New message from user. User: {user_id}, state: {status}, message: {update.message.text}')

        # Выбор статуса шифрования
        if mess == "шифрование" and status == const.State.START:
            cur.execute(f"UPDATE `Users` set `status`='{const.State.ENCRYPT}' WHERE `telegram_id`='{user_id}';")
            con.commit()
            reply_markup = get_keyboard(user_id, cur)
            update.message.reply_text(text="Выбери, что установить.", reply_markup=reply_markup)
        # Выбор статуса дешифрования
        elif mess == "дешифрование" and status == const.State.START:
            cur.execute(f"UPDATE `Users` set `status`='{const.State.DECRYPT}' WHERE `telegram_id`='{user_id}';")
            con.commit()
            reply_markup = get_keyboard(user_id, cur)
            update.message.reply_text(text="Выбери, что установить.", reply_markup=reply_markup)
        # Неразобрано сообщение
        elif status == const.State.START:
            reply_markup = get_keyboard(user_id, cur)
            update.message.reply_text(text="Я не понимаю, выбери что делать.", reply_markup=reply_markup)
        # Выбор загрузки изображения для шифрования
        elif mess.endswith("изображение") and status == const.State.ENCRYPT:
            cur.execute(f"UPDATE `Users` set `status`='{const.State.ENC_IMAGE}' WHERE `telegram_id`='{user_id}';")
            con.commit()
            update.message.reply_text(text="Отправь изображение в формате png как документ!", reply_markup=None)
        # Выбор загрузки текста для шифрования
        elif mess.endswith("текст") and status == const.State.ENCRYPT:
            cur.execute(f"UPDATE `Users` set `status`='{const.State.ENC_TEXT}' WHERE `telegram_id`='{user_id}';")
            con.commit()
            update.message.reply_text(text="Отправь текст который будет зашифрован", reply_markup=None)
        # Загрузка текста для шифрования
        elif status == const.State.ENC_TEXT:
            cur.execute(f"UPDATE `Users` set `status`='{const.State.ENCRYPT}', `text`='{update.message.text}' "
                        f"WHERE `telegram_id`='{user_id}';")
            con.commit()
            reply_markup = get_keyboard(user_id, cur)
            update.message.reply_text(text="Выбери, что установить.", reply_markup=reply_markup)
        # Выбор загрузки ключа для шифрования
        elif mess.endswith("ключ") and status == const.State.ENCRYPT:
            cur.execute(f"UPDATE `Users` set `status`='{const.State.ENC_KEY}' WHERE `telegram_id`='{user_id}';")
            con.commit()
            update.message.reply_text(text="Отправьте ключ для шифрования", reply_markup=None)
        # Загрузка ключа для шифрования
        elif status == const.State.ENC_KEY:
            cur.execute(f"UPDATE `Users` set `status`='{const.State.ENCRYPT}', `crypto_key`='{update.message.text}' "
                        f"WHERE `telegram_id`='{user_id}';")
            con.commit()
            reply_markup = get_keyboard(user_id, cur)
            update.message.reply_text(text="Выбери, что установить.", reply_markup=reply_markup)
        # Завершение шифрования
        elif mess == "завершить" and status == const.State.ENCRYPT:
            cur.execute(f"SELECT `image`, `text`, `crypto_key` FROM `Users` WHERE `telegram_id` = '{user_id}';")
            res = cur.fetchall()[0]
            if res[0] is not None and res[1] is not None and res[2] is not None:
                update.message.reply_text(text="Идёт шифрование...", reply_markup=None)
                try:
                    crypto = cryptographer.Cryptographer(f"photo/encrypt/before/{res[0]}", res[2], res[1])
                    image = crypto.encrypt()
                except Exception as e:
                    logger.warning(f"Can't encrypt image. User: {user_id}, image: {res[0]}, key: {res[2]}, "
                                   f"text: {res[1]}")
                    update.message.reply_text(text="Ошибка при шифровании.", reply_markup=None)
                    return
                reply_markup = ReplyKeyboardMarkup([['В начало']], resize_keyboard=True, one_time_keyboard=True)
                update.message.reply_text(text="Зашифрованная картинка:", reply_markup=reply_markup)
                context.bot.send_document(chat_id=user_id, document=open(image, 'rb'))
                cur.execute(f"UPDATE `Users` SET `status`='{const.State.ENC_FINISH}' WHERE `telegram_id`='{user_id}';")
        # Переход в начало работы с ботом
        elif mess == "в начало" and (status == const.State.ENC_FINISH or status == const.State.DEC_FINISH):
            cur.execute(f"UPDATE `Users` SET `name`='{update.message.from_user.first_name}', "
                        f"`status`='{const.State.START}', `image`=NULL, `text`=NULL, `crypto_key`=NULL "
                        f"WHERE `telegram_id`='{user_id}';")
            con.commit()
            reply_markup = ReplyKeyboardMarkup(
                [['Шифрование', 'Дешифрование']],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            update.message.reply_text(
                text="Приветствую, я CryptoBot, умею шифровать сообщение в картинку.",
                reply_markup=reply_markup
            )
        # Выбор загрузки изображения для дешифрования
        elif mess.endswith("изображение") and status == const.State.DECRYPT:
            cur.execute(f"UPDATE `Users` set `status`='{const.State.DEC_IMAGE}' WHERE `telegram_id`='{user_id}';")
            con.commit()
            update.message.reply_text(text="Отправь изображение в формате png как документ!", reply_markup=None)
        # Выбор загрузки ключа для дешифрования
        elif mess.endswith("ключ") and status == const.State.DECRYPT:
            cur.execute(f"UPDATE `Users` set `status`='{const.State.DEC_KEY}' WHERE `telegram_id`='{user_id}';")
            con.commit()
            update.message.reply_text(text="Отправьте ключ для дешифрования", reply_markup=None)
        # Загрузка ключа для дешифрования
        elif status == const.State.DEC_KEY:
            cur.execute(f"UPDATE `Users` set `status`='{const.State.DECRYPT}', `crypto_key`='{update.message.text}' "
                        f"WHERE `telegram_id`='{user_id}';")
            con.commit()
            reply_markup = get_keyboard(user_id, cur)
            update.message.reply_text(text="Выбери, что установить.", reply_markup=reply_markup)
        # Завершение дешифрования
        elif mess == "завершить" and status == const.State.DECRYPT:
            cur.execute(f"SELECT `image`, `crypto_key` FROM `Users` WHERE `telegram_id` = '{user_id}';")
            res = cur.fetchall()[0]
            if res[0] is not None and res[1] is not None:
                update.message.reply_text(text="Идёт дешифрование...", reply_markup=None)
                try:
                    crypto = cryptographer.Cryptographer(f"photo/decrypt/before/{res[0]}", res[1])
                    text = crypto.decrypt
                except Exception as e:
                    logger.warning(f"Can't decrypt image. User: {user_id}, image: {res[0]}, key: {res[1]}")
                    update.message.reply_text(text="Ошибка при дешифровании.", reply_markup=None)
                    return
                reply_markup = ReplyKeyboardMarkup([['В начало']], resize_keyboard=True, one_time_keyboard=True)
                update.message.reply_text(text="Расшифрованный текст:", reply_markup=None)
                update.message.reply_text(text=text, reply_markup=reply_markup)
                cur.execute(f"UPDATE `Users` SET `status`='{const.State.DEC_FINISH}' WHERE `telegram_id`='{user_id}';")


def get_keyboard(user_id, cur):
    """
    Создание клавиатуры по статусу пользователя.

    :param user_id: id пользователя.
    :param cur: курсос для работы с бд.
    :return: Созданная клавиатура.
    """
    cur.execute(f"SELECT `status`, `image`, `text`, `crypto_key` FROM `Users` WHERE `telegram_id` = '{user_id}';")
    res = cur.fetchall()[0]
    logger.info(f'Creating keyboard with user state: {res[0]}')
    keyboard = [[]]
    reply_markup = None
    if res[0] == const.State.ENCRYPT:
        keyboard[0].append(('' if res[1] is None else u'\U00002705') + "Изображение")
        keyboard[0].append(('' if res[2] is None else u'\U00002705') + "Текст")
        keyboard[0].append(('' if res[3] is None else u'\U00002705') + "Ключ")
        if res[1] is not None and res[2] is not None and res[3] is not None:
            keyboard.append([])
            keyboard[1].append("Завершить")
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    if res[0] == const.State.DECRYPT:
        keyboard[0].append(('' if res[1] is None else u'\U00002705') + "Изображение")
        keyboard[0].append(('' if res[3] is None else u'\U00002705') + "Ключ")
        if res[1] is not None and res[3] is not None:
            keyboard.append([])
            keyboard[1].append("Завершить")
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    return reply_markup


def photo(update, context):
    """
    Загрузка изображения на сервер.

    :param update: Объект для работы с ботом.
    :param context: Контекст работы бота.
    """
    con = pymysql.connect(config.DB_SERVER, config.DB_USER, config.DB_PASSWORD, config.DB_DATABASE)
    with con:
        cur = con.cursor()
        cur.execute(f"SELECT `status` FROM `Users` WHERE `telegram_id` = '{update.message.from_user.id}';")
        if cur.rowcount == 0:
            return
        res = cur.fetchall()
        status = res[0][0]
        logger.info(f'Upload photo with user state: {status}')
        if status == const.State.ENC_IMAGE or status == const.State.DEC_IMAGE:
            try:
                update.message.reply_text(text="Загружаю изображение...", reply_markup=None)
                file_id = update.message.document.file_id
                file = context.bot.getFile(file_id)
                file_name = f"{update.message.from_user.id}_{datetime.datetime.now()}.png"
            except Exception as e:
                logger.warning(f"Can't load image. User: {update.message.from_user.id}, file_id: {file_id}")
                update.message.reply_text(text="Неудалось загрузить изображение.", reply_markup=None)
                return
        if status == const.State.ENC_IMAGE:
            file.download(f"photo/encrypt/before/{file_name}")
            cur.execute(f"UPDATE `Users` set `status`='{const.State.ENCRYPT}', `image`='{file_name}' "
                        f"WHERE `telegram_id`='{update.message.from_user.id}';")
            con.commit()
            reply_markup = get_keyboard(update.message.from_user.id, cur)
            update.message.reply_text(text="Выбери, что установить.", reply_markup=reply_markup)
        if status == const.State.DEC_IMAGE:
            file.download(f"photo/decrypt/before/{file_name}")
            cur.execute(f"UPDATE `Users` set `status`='{const.State.DECRYPT}', `image`='{file_name}' "
                        f"WHERE `telegram_id`='{update.message.from_user.id}';")
            con.commit()
            reply_markup = get_keyboard(update.message.from_user.id, cur)
            update.message.reply_text(text="Выбери, что установить.", reply_markup=reply_markup)


def error(update, context):
    """ Обработка ошибок """
    logger.error(context.error)
    print("ERROR: ", context.error)


def main():
    """ Запуск бота """
    updater = Updater(token=config.TOKEN, use_context=True, request_kwargs=config.REQUEST_KWARGS)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(MessageHandler(Filters.text, message))
    dp.add_handler(MessageHandler(Filters.document, photo))

    dp.add_error_handler(error)

    updater.start_polling(timeout=1000)

    updater.idle()

    logger.info('Bot starting')


if __name__ == "__main__":
    main()
