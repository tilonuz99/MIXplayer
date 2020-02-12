import telebot
import yandex_music
from os import path, makedirs, remove, mknod
from mutagen import mp3, id3
from time import sleep, strftime, localtime


# ID пользователя, которому будут отправляться уведомления о потери связи с прокси к ЯМузыке
adminTelegramID =
botToken =  # токен бота Телеграм
bot = telebot.TeleBot(botToken)
#   telebot.apihelper.proxy = {'https': 'type://login:password@address:port'} - прокси, если необходим

if not path.exists('./downloads/covers/'):
    makedirs('./downloads/covers/')

yandexProxy = None
#  yandexProxy = 'type://login:password@address:port' - прокси, если необходим
request = yandex_music.utils.request.Request(proxy_url=yandexProxy)
try:
    client = yandex_music.client.Client(request=request)  # Авторизация ЯМузыки
    if path.exists('./alert'):
        remove('./alert')
        bot.send_message(
            adminTelegramID, text='Подключение к ЯМузыке восстановлено')
except Exception:
    print('\nНе удалось подключиться к ЯМузыке')
    if not path.exists('./alert'):
        bot.send_message(
            adminTelegramID, text='Отсутствует подключение к ЯМузыке')
        mknod('alert')
    raise SystemExit

keyboardChoose = telebot.types.ReplyKeyboardMarkup(True, True)
keyboardChoose.one_time_keyboard = True
keyboardChoose.row('ВК', 'ЯМузыка')

usersState = {}
usersRequests = {}


def yandexmusic_search(message):
    global usersState, usersRequests
    try_counter = 5
    while try_counter > 0:
        try:
            answer = client.search(text=usersRequests[message.chat.id], type_='track')[
                'tracks']['results']
            try_counter = -1
        except Exception:
            try_counter -= 1
            sleep(5)
    if try_counter != -1 or answer is None:
        msg = bot.send_message(message.chat.id, 'По вашему запросу ничего не найдено. Попробуйте ввести другой запрос:',
                               reply_markup=telebot.types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, song_name_step)
        return
    usersState[message.chat.id] = [answer, 0, message.message_id + 1]
    bot.send_message(message.chat.id, text='По вашему запросу найдены следующие треки:',
                     reply_markup=yandex_keyboard_updater(answer=answer))


def track_tagger(track_path, title, artist, album, cover_path):
    track = mp3.EasyMP3(track_path)
    track['title'] = title
    track['artist'] = artist
    track['album'] = album
    track.save()
    cover_image = open(cover_path, 'rb').read()
    track = id3.ID3(track_path)
    track.add(id3.APIC(3, 'image/jpeg', 3, u'Cover', cover_image))
    track.save()
    remove(cover_path)


def track_sender(user_id, track_path):
    try_counter = 5
    while try_counter > 0:
        try:
            bot.send_audio(user_id, audio=open(track_path, 'rb'))
            try_counter = -1
        except Exception:
            try_counter -= 1
            sleep(5)
    if try_counter != -1:
        remove(track_path)
        msg = bot.send_message(user_id, 'Непредвидленная ошибка. Попробуйте ввести другой запрос:',
                               reply_markup=telebot.types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, song_name_step)
        return
    remove(track_path)


@bot.callback_query_handler(
    lambda query: query.data == 'toTheLeft' or query.data == 'toTheRight' or query.data == 'toBack')
def yandex_keyboard_updater(query=None, answer=None):
    global usersState
    if query is not None:
        if query.message.message_id != usersState[query.from_user.id][2]:
            return
        if query.data == 'toBack':
            msg = bot.send_message(
                query.from_user.id, 'Где будем искать?', reply_markup=keyboardChoose)
            bot.register_next_step_handler(msg, service_choose_step)
            return
        try:
            answer = usersState[query.from_user.id][0]
            page_number = usersState[query.from_user.id][1]
        except Exception:
            return
        if query.data == 'toTheLeft':
            page_number -= 1
        elif query.data == 'toTheRight':
            page_number += 1
        if page_number < 0 or page_number > 3:
            return
        usersState[query.from_user.id][1] = page_number
    else:
        page_number = 0
    keyboard_tracks = telebot.types.InlineKeyboardMarkup()
    correction = page_number * 5
    track_counter = 0
    for i in range(5):
        try:
            track_name = answer[correction + i]['artists'][0]['name'] + \
                ' - ' + answer[correction + i]['title']
            track_id = str(answer[correction + i]['id']) + ':' + str(
                answer[correction + i]['albums'][0]['id'])
        except Exception:
            break
        button_track = telebot.types.InlineKeyboardButton(
            text=track_name, callback_data=track_id)
        keyboard_tracks.add(button_track)
        track_counter += 1
    button_back = telebot.types.InlineKeyboardButton(
        text='Назад', callback_data='toBack')
    keyboard_tracks.add(button_back)
    buttons = []
    if page_number > 0:
        button_left = telebot.types.InlineKeyboardButton(
            text='<', callback_data='toTheLeft')
        buttons.append(button_left)
    buttons.append(telebot.types.InlineKeyboardButton(
        text=page_number + 1, callback_data='None'))
    if page_number < 3 and track_counter == 5:
        button_right = telebot.types.InlineKeyboardButton(
            text='>', callback_data='toTheRight')
        buttons.append(button_right)
    if len(buttons) == 3:
        keyboard_tracks.row(buttons[0], buttons[1], buttons[2])
    elif len(buttons) == 2:
        keyboard_tracks.row(buttons[0], buttons[1])
    else:
        keyboard_tracks.row(buttons[0])
    if query is None:
        return keyboard_tracks
    bot.edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id,
                          text="По вашему запросу найдены следующие треки:", reply_markup=keyboard_tracks)


@bot.callback_query_handler(lambda query: query.data is not None)
def yandex_track_getter(query):
    track = client.tracks([query.data])[0]
    track_path = './downloads/' + \
        track['artists'][0]['name'] + ' - ' + track['title'] + '.mp3'
    cover_path = './downloads/covers/' + \
        track['artists'][0]['name'] + ' - ' + track['title'] + '.jpeg'
    track_path = track_path.replace('?', '')
    cover_path = cover_path.replace('?', '')
    try_counter = 5
    while try_counter > 0:
        try:
            track.download(track_path)
            track.download_cover(cover_path)
            try_counter = -1
        except Exception:
            try_counter -= 1
            sleep(5)
    if try_counter != -1:
        remove(track_path)
        msg = bot.send_message(query.from_user.id, 'Непредвиденная ошибка. \nПопробуйте ввести другой запрос:',
                               reply_markup=telebot.types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, song_name_step)
        return
    title = track['title']
    artist = track['artists'][0]['name']
    album = track['albums'][0]['title']
    track_tagger(track_path, title, artist, album, cover_path)
    track_sender(query.from_user.id, track_path)


@bot.message_handler(commands=['start'])  # Реакция на команду start
def start_message(message):
    bot.send_message(message.chat.id,
                     'Добро пожаловать в MIXplayer!\nДля поиска трека воспользуйтесь коммандой /search или просто '
                     'начните вводить свой запрос\n',
                     reply_markup=telebot.types.ReplyKeyboardRemove())


@bot.message_handler(commands=['search'])
def search(message):
    msg = bot.send_message(message.chat.id, 'Напишите исполнителя или название трека:',
                           reply_markup=telebot.types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, song_name_step)


@bot.message_handler(content_types=["text"])
def song_name_step(message):
    global usersRequests
    if message.text == 'ВК' or message.text == 'ЯМузыка':
        return
    elif message.text == '/start':
        start_message(message)
    elif message.text == '/search':
        search(message)
    usersRequests[message.chat.id] = message.text
    msg = bot.send_message(
        message.chat.id, 'Где будем искать?', reply_markup=keyboardChoose)
    bot.register_next_step_handler(msg, service_choose_step)


def service_choose_step(message):
    if message.text == 'ВК':
        msg = bot.send_message(
            message.chat.id, 'ВК в разработке', reply_markup=keyboardChoose)
        bot.register_next_step_handler(msg, service_choose_step)
    elif message.text == 'ЯМузыка':
        yandexmusic_search(message)


try:
    print('\nBot is Online  ' + strftime('%d.%m.%Y %H:%M:%S', localtime()) + '\n')
    bot.polling(none_stop=True, interval=3)
except Exception:
    print('Critical error!  ' + strftime('%d.%m.%Y %H:%M:%S', localtime()) + '\n')
