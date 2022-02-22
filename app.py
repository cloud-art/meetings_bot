import logging

import psycopg2
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import StateFilter
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import (KeyboardButton, ReplyKeyboardMarkup,
                           ReplyKeyboardRemove)
from psycopg2.errors import UniqueViolation

from config import API_TOKEN, PSQL_DBNAME, PSQL_HOST, PSQL_PASSWORD, PSQL_USER

logging.basicConfig(format=u"%(filename)s [LINE:%(lineno)d] #%(levelname)-8s [%(asctime)s] %(message)s", level=logging.INFO)

storage = MemoryStorage()

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)

con = psycopg2.connect(dbname=PSQL_DBNAME, user=PSQL_USER, password=PSQL_PASSWORD, host=PSQL_HOST)
cur = con.cursor()

# Работа с бд

def add_new_user(user_id, nickname, sex, city, age, descr, preference):
    args = (user_id, nickname, sex, city, age, descr, preference)
    try:
        cur.execute("INSERT INTO users (user_id, nickname, sex, city, age, descr, preference) VALUES(%s, %s, %s, %s, %s, %s, %s)", args)
        con.commit()
        logging.info(f"был добавлен новый пользователь с id = {user_id}")
    except UniqueViolation:
        pass

def add_to_react(user_id, reacted_user, reacted):
    args = (user_id, reacted_user, reacted)
    try:
        cur.execute("INSERT INTO reaction (user_id, reacted_user, reacted) VALUES(%s, %s, %s)", args)
        con.commit()
        logging.info(f"Пользователь {user_id} отреагировал на {reacted_user} так: {reacted}")
    except UniqueViolation:
        pass

def user_is_exist(user_id):
    cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    result = cur.fetchall()
    if result:
        return True
    else:
        return False

def data_of_this_user(user_id):
    cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    result = cur.fetchone()
    return result

def get_random_user(user_id):
    current_user = data_of_this_user(user_id)
    pref = current_user[6]
    sex = current_user[2]
    if pref == 'не важно':
        cur.execute("SELECT * FROM users WHERE user_id <> %s AND user_id NOT IN(SELECT reacted_user FROM reaction WHERE user_id=%s) \
            AND preference IN (%s, 'не важно') LIMIT 1", (user_id, user_id, sex))
    else:
        cur.execute("SELECT * FROM users WHERE user_id <> %s AND user_id NOT IN(SELECT reacted_user FROM reaction WHERE user_id=%s) \
            AND sex IN (%s, 'не важно') AND preference IN (%s, 'не важно') LIMIT 1", (user_id, user_id, pref, sex))
    result = cur.fetchone()
    return result

def show_reacted_users(user_id):
    args = (user_id, user_id, )
    cur.execute("SELECT user_id , nickname, sex, city, age, descr, preference, img FROM users WHERE user_id IN(SELECT user_id from reaction where reacted_user=%s AND reacted=True)\
        AND user_id NOT IN(SELECT reacted_user FROM reaction WHERE user_id=%s AND (reacted=True OR reacted=False)) LIMIT 1", args)
    result = cur.fetchone()
    return result

def react_on_reaction(user_id, reacted_user, answer):
    args = (answer, user_id, reacted_user)
    # try:
    cur.execute("UPDATE reaction SET answer=%s WHERE user_id=%s AND reacted_user=%s", args)
    # except UniqueViolation:
    #     pass



# def get_random_user(user_id):
#     cur.execute("SELECT * FROM users WHERE user_id <> %s AND user_id NOT IN\
#         (SELECT reacted_user FROM reaction WHERE user_id=%s) LIMIT 1", (user_id, user_id))
#     result = cur.fetchone()
#     return result

# Состояния

class Registration(StatesGroup):
    nickname = State()
    sex = State()
    city = State()
    age = State()
    descr = State()
    preference = State()
    img = State()

class Reaction(StatesGroup):
    find = State()
    react = State()
    show_react = State()
    react_to_them = State()

# вспомогательные функции
def is_int(str):
    try:
        int(str)
        return True
    except ValueError:
        return False

# Кнопки

sex = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Девушка"), KeyboardButton(text="Парень")]], resize_keyboard=True)
preference = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Ищу парня"), KeyboardButton(text="Ищу девушку"), KeyboardButton(text="Не важно")]], resize_keyboard=True)
reaction = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Нравится"), KeyboardButton(text="Не нравится"), KeyboardButton(text="Назад")]], resize_keyboard=True)


# Хэндлеры

@dp.message_handler(commands=["start"])
async def start_message(message: types.Message):
    await message.reply("Привет! Для просмотра команд напиши /help")

@dp.message_handler(commands=["help"])
async def help_commands(message: types.Message):
    await message.reply("Добро пожаловать.\n\
    Комманды бота:\n\
    /help - посмотреть список команд,\n\
    /registr - создать свою анкету\n\
    /me - посмотреть свою анкету\n\
    /search - найти знакомства")

@dp.message_handler(commands=["me"])
async def show_profile(message: types.Message):
    this_user = message.from_user.id
    if user_is_exist(this_user):
        data = data_of_this_user(this_user)
        await message.answer(f"{data[1]}, {data[2]} {data[4]} y.o из {data[3]}\n{data[5]}\nПредпочтения: {data[6]}")
    else:
        await message.answer("У вас нет анкеты")

# просмотр анкет

@dp.message_handler(commands=["search"])
async def search(message: types.Message, state:FSMContext):
    this_user = message.from_user.id
    if user_is_exist(this_user):
        data = get_random_user(this_user)
        if data:
            await message.answer(f"{data[1]}, {data[2]} {data[4]} y.o из {data[3]}\n{data[5]}\nПредпочтения: {data[6]}", reply_markup=reaction)
            await state.update_data(reaction_user_id=this_user)
            await state.update_data(reaction_reacted_user=data[0])
            await Reaction.react.set()
        else:
            await message.answer("На данный момент никаких анкет нет", reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer("У вас нет анкеты")

@dp.message_handler(state = Reaction.react)
async def react(message: types.Message, state:FSMContext):
    if message.text.lower() == "нравится":
        react_data = await state.get_data()
        add_to_react(react_data['reaction_user_id'], react_data['reaction_reacted_user'], True)

        await state.finish()
        await search(message, state)
    elif message.text.lower() == "не нравится":
        react_data = await state.get_data()
        add_to_react(react_data['reaction_user_id'], react_data['reaction_reacted_user'], False)
        await state.finish()
        await search(message, state)
    elif message.text.lower() == "назад":
        await message.answer("Что делаем дальше?", reply_markup=ReplyKeyboardRemove())
        await state.finish()
    else:
        await message.answer("Выберите вариант из списка")
        return

# если на reacted пользователь так же реагирует то выдется ссылка на профиль
@dp.message_handler(commands=["answer"])
async def answer(message: types.Message, state:FSMContext):
    this_user = message.from_user.id
    data = show_reacted_users(this_user)
    if data:
        await message.answer(f"{data[1]}, {data[2]} {data[4]} y.o из {data[3]}\n{data[5]}\nПредпочтения: {data[6]}", reply_markup=reaction)
        await state.update_data(reaction_user_id=data[0])
        await state.update_data(reaction_reacted_user=this_user)
        await Reaction.show_react.set()
    else:
        await message.answer("На данный момент никаких анкет нет", reply_markup=ReplyKeyboardRemove())

@dp.message_handler(state = Reaction.show_react)
async def react(message: types.Message, state:FSMContext):
    if message.text.lower() == "нравится":
        react_data = await state.get_data()
        react_on_reaction(react_data['reaction_user_id'], react_data['reaction_reacted_user'], True)
        await state.finish()
        await answer(message, state)
    elif message.text.lower() == "не нравится":
        react_data = await state.get_data()
        react_on_reaction(react_data['reaction_user_id'], react_data['reaction_reacted_user'], False)
        await state.finish()
        await answer(message, state)
    elif message.text.lower() == "назад":
        await message.answer("Что делаем дальше?", reply_markup=ReplyKeyboardRemove())
        await state.finish()
    else:
        await message.answer("Выберите вариант из списка")
        return    
    

# -> регистрация в боте

@dp.message_handler(commands=["registr"], state=None)
async def registration(message: types.Message):
    if user_is_exist(message.from_user.id):
        await message.answer("У тебя уже есть анкета")
    else:
        await message.answer("Как вас зовут?")
        await Registration.nickname.set()

@dp.message_handler(state=Registration.nickname)
async def reg_nickname(message: types.Message, state: FSMContext):
    if len(message.text) > 50:
        await message.answer("Слишком длинное имя")
        return
    answer = message.text
    await state.update_data(nickname=answer)
    await message.answer("Ты девушка/парень?", reply_markup=sex)
    await Registration.sex.set()

@dp.message_handler(state=Registration.sex)
async def reg_nickname(message: types.Message, state: FSMContext):
    if message.text.lower() != "девушка" and message.text.lower() != "парень":
        await message.answer("Выберите из списка")
        return
    if message.text.lower() == "девушка":
        answer = 'девушка'
    else:
        answer = 'парень'
    await state.update_data(sex=answer)
    await message.answer("Напишите из какого вы города", reply_markup=ReplyKeyboardRemove())
    await Registration.city.set()

@dp.message_handler(state=Registration.city)
async def reg_city(message: types.Message, state: FSMContext):
    if len(message.text) > 50:
        await message.answer("Слишком длинное название")
        return
    answer = message.text
    await state.update_data(city=answer.lower())
    await message.answer("Сколько вам лет?")
    await Registration.age.set()

@dp.message_handler(state=Registration.age)
async def reg_age(message: types.Message, state: FSMContext):
    if len(message.text) > 2 or not is_int(message.text):
        await message.answer("Введите корректный возраст")
        return
    answer = message.text
    await state.update_data(age=answer)
    await message.answer("Описание")
    await Registration.descr.set()

@dp.message_handler(state=Registration.descr)
async def reg_descr(message: types.Message, state: FSMContext):
    if len(message.text) > 255:
        await message.answer("Введите описание покороче")
        return
    answer = message.text
    await state.update_data(descr=answer)
    await message.answer("Кого бы вы предпочли найти? парня, девушку или вам не важно?", reply_markup=preference)
    await Registration.preference.set()

@dp.message_handler(state=Registration.preference)
async def reg_preference(message: types.Message, state: FSMContext):
    if message.text.lower() != "ищу девушку" and message.text.lower() != "ищу парня" and message.text.lower() != "не важно":
        await message.answer("Введите корректное предпотчение")
        return
    if message.text.lower() == "ищу девушку":
        answer = 'девушка'
    elif message.text.lower() == "ищу парня":
        answer = 'парень'
    else:
        answer = 'не важно'

    await state.update_data(preference=answer.lower())
    await state.update_data(user_id=message.from_user.id)
    user_data = await state.get_data()
    add_new_user(user_data['user_id'], user_data['nickname'], user_data["sex"], user_data['city'], user_data['age'], user_data['descr'], user_data['preference'])
    await message.answer("Анкета создана ;)", reply_markup=ReplyKeyboardRemove())
    await state.finish()

# -> \регистрация в боте

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
