import random
import json
import sqlalchemy
from sqlalchemy.orm import sessionmaker
import configparser
from models import create_tables, Client, Words
from telebot import types, TeleBot, custom_filters
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup


config = configparser.ConfigParser()
config.read("settings.ini")
login = config["DATA"]["login"]
password = config["DATA"]["password"]
db_name = config["DATA"]["db_name"]
localhost = config["DATA"]["localhost"]

DSN = f'postgresql://{login}:{password}@localhost:{localhost}/{db_name}'
engine = sqlalchemy.create_engine(DSN)

create_tables(engine)

Session = sessionmaker(bind=engine)
session = Session()

#
with open("words.json", encoding='utf-8') as f:
    json_reader = json.load(f)

for record in json_reader:
    if record.get('model') == "client":
        session.add(Client(name=record.get('name'), user_step=record.get('user_step')))
    elif record.get('model') == "words":
        session.add(Words(en_name=record.get('en_name'), ru_name=record.get('ru_name'), client_id=record.get('client_id')))
session.commit()


state_storage = StateMemoryStorage()
token_bot = config["TELEGRAM"]["token_bot"]
bot = TeleBot(token_bot, state_storage=state_storage)

en_word = ''
ru_word = ''
known_users = []
userStep = {}
buttons = []
for user in session.query(Client.name, Client.user_step).select_from(Client).all():
    known_users.append(int(user[0]))
    new_dict = {user[0]: user[1]}
    userStep.update(new_dict)


def show_hint(*lines):
    return '\n'.join(lines)


def show_target(data):
    return f"{data['target_word']} -> {data['translate_word']}"


class Command:
    ADD_WORD = 'Добавить слово ➕'
    DELETE_WORD = 'Удалить слово🔙'
    NEXT = 'Дальше ⏭'


class MyStates(StatesGroup):
    target_word = State()
    translate_word = State()
    another_words = State()


def get_user_step(uid):
    if uid in userStep:
        return userStep[uid]
    else:
        known_users.append(uid)
        userStep[uid] = 0
        print("New user detected, who hasn't used \"/start\" yet")
        return 0


@bot.message_handler(commands=['start'])
def create_cards(message):
    cid = message.chat.id
    if cid not in known_users:
        known_users.append(cid)
        userStep[cid] = 0
    markup = types.ReplyKeyboardMarkup(row_width=2)

    for search_name in session.query(Client.id, Client.user_step, Client.name).select_from(Client).all():
        if int(search_name[2]) == cid:
            req_step = search_name[1]

    x = 0
    all_words = []
    for search_word in session.query(Words.en_name, Words.ru_name).select_from(Words).filter(Words.client_id == 1).all():
        all_words.append(search_word[0])
        if x == req_step:
            target_word = search_word[0]
            translate = search_word[1]
        x += 1

    all_words.remove(target_word)

    random.shuffle(all_words)

    global buttons
    buttons = []
    target_word_btn = types.KeyboardButton(target_word)
    buttons.append(target_word_btn)
    others = [all_words[0], all_words[1], all_words[2]]  # брать из БД
    other_words_btns = [types.KeyboardButton(word) for word in others]
    buttons.extend(other_words_btns)
    random.shuffle(buttons)
    next_btn = types.KeyboardButton(Command.NEXT)
    add_word_btn = types.KeyboardButton(Command.ADD_WORD)
    delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
    buttons.extend([next_btn, add_word_btn, delete_word_btn])

    markup.add(*buttons) #изменить обновление кнопока, пока норм

    greeting = f"Выбери перевод слова:\n🇷🇺 {translate}"
    bot.send_message(message.chat.id, greeting, reply_markup=markup)
    bot.set_state(message.from_user.id, MyStates.target_word, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['target_word'] = target_word
        data['translate_word'] = translate
        data['other_words'] = others


@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_cards(message):
    cid = message.chat.id
    req_step = session.query(Client).filter(Client.name == str(cid)).first()
    user_id = req_step.id
    qty_words = session.query(Words).filter(Words.client_id == user_id).all()
    if req_step.user_step < len(qty_words)-1:
        req_step.user_step += 1
        session.commit()
        #Обновить счетчик юзера
    else:
        req_step.user_step = 0
        session.commit()
    create_cards(message)


@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_word(message):
    cid = message.chat.id
    req_step = session.query(Client).filter(Client.name == str(cid)).first()
    user_id = req_step.id
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        del_word = data['target_word']
        f_word = session.query(Words).filter(Words.en_name == str(del_word)).first()
        if f_word.client_id == user_id:
            session.delete(f_word)
        session.commit()
    bot.send_message(message.from_user.id, f'Слово {del_word} удалено.')

@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_en(message):
    bot.send_message(message.from_user.id, f'Введите слово на английском языке: ')
    bot.register_next_step_handler(message, add_ru)

def add_ru(message):
    global en_word
    en_word = message.text
    bot.send_message(message.from_user.id, f'Напиши перевод к слову {en_word}: ')
    bot.register_next_step_handler(message, add_word)

def add_word(message):
    global ru_word
    ru_word = message.text
    cid = message.chat.id
    req_step = session.query(Client).filter(Client.name == str(cid)).first()
    user_id = req_step.id
    new_word = (Words(en_name=en_word, ru_name=ru_word, client_id=user_id))
    session.add(new_word)
    qty_word = len(session.query(Words).filter(Words.client_id == user_id).all())
    bot.send_message(message.from_user.id, f'В словарь добавлено слово {en_word} -> {ru_word}.\nПользователь изучает {qty_word} слов, молодец!\nПродолжим? :)')
    session.commit()

@bot.message_handler(func=lambda message: True, content_types=['text'])
def message_reply(message):
    text = message.text
    markup = types.ReplyKeyboardMarkup(row_width=2)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        target_word = data['target_word']
        if text == target_word:
            hint = show_target(data)
            hint_text = ["Отлично!❤", hint]
            next_btn = types.KeyboardButton(Command.NEXT)
            add_word_btn = types.KeyboardButton(Command.ADD_WORD)
            delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
            buttons.extend([next_btn, add_word_btn, delete_word_btn])
            hint = show_hint(*hint_text)
        else:
            for btn in buttons:
                if btn.text == text:
                    btn.text = text + '❌'
                    break
            hint = show_hint("Допущена ошибка!",
                             f"Попробуй ещё раз вспомнить слово 🇷🇺{data['translate_word']}")
            markup.add(*buttons)
    bot.send_message(message.chat.id, hint, reply_markup=markup)


bot.add_custom_filter(custom_filters.StateFilter(bot))

bot.infinity_polling(skip_pending=True)