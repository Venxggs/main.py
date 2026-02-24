import sqlite3
import logging
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# --- SOZLAMALAR ---
API_TOKEN = '8727688545:AAFn3S3Bv1TXXYZcAmfGnlaYFydk9kC5wGw'
CREATORS = [6156296807, 8163861382]
CREATOR_USERNAME = "@fakevenx"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- BAZA ---
def init_db():
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    # Jadvalni o'zgartirdik: bitta ID ga bir nechta file_id va qism raqami tushadi
    c.execute('''CREATE TABLE IF NOT EXISTS animes 
                 (anime_id TEXT, file_id TEXT, part_num INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ads (username TEXT PRIMARY KEY)''')
    conn.commit()
    conn.close()

init_db()

class AdminStates(StatesGroup):
    waiting_for_videos = State()
    waiting_for_id = State()
    waiting_for_ad = State()

# --- KLAVIATURALAR ---
def get_main_kb(user_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if user_id in CREATORS:
        kb.add("Panel")
    return kb

def get_panel_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("Anime Yuklash", "Reklama")
    kb.add("Bekor qilish")
    return kb

# --- HANDLERLAR ---

@dp.message_handler(commands=['start'], state="*")
async def start_cmd(message: types.Message, state: FSMContext):
    await state.finish()
    user_id = message.from_user.id
    args = message.get_args()

    if user_id not in CREATORS:
        conn = sqlite3.connect('data.db')
        ads = conn.execute("SELECT username FROM ads").fetchall()
        conn.close()
        for ad in ads:
            try:
                member = await bot.get_chat_member(chat_id=ad[0], user_id=user_id)
                if member.status in ['left', 'kicked']:
                    markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Obuna bo'lish", url=f"https://t.me/{ad[0].replace('@','')}"))
                    await message.answer(f"Botdan foydalanish uchun {ad[0]} kanaliga obuna bo'ling!", reply_markup=markup)
                    return
            except: continue

    if args:
        conn = sqlite3.connect('data.db')
        videos = conn.execute("SELECT file_id, part_num FROM animes WHERE anime_id=? ORDER BY part_num ASC", (args,)).fetchall()
        conn.close()
        if videos:
            for v in videos:
                await bot.send_video(user_id, v[0], caption=f"Qism {v[1]}")
                await asyncio.sleep(0.5) # Telegram bloklamasligi uchun
            return
        else:
            await message.answer("Ushbu ID ostida videolar topilmadi!")
            return

    await message.answer("Xush kelibsiz!", reply_markup=get_main_kb(user_id))

# --- ANIME YUKLASH (KO'P VIDEOLI) ---

@dp.message_handler(lambda m: m.text == "Anime Yuklash" and m.from_user.id in CREATORS)
async def upload_start(message: types.Message):
    await AdminStates.waiting_for_video.set()
    await message.answer("Videolarni ketma-ket yuboring. Tugatgach 'Tugatish' tugmasini bosing.", 
                         reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Tugatish", "Bekor qilish"))

@dp.message_handler(content_types=['video'], state=AdminStates.waiting_for_video)
async def get_videos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    video_list = data.get('video_list', [])
    video_list.append(message.video.file_id)
    await state.update_data(video_list=video_list)
    await message.answer(f"{len(video_list)}-qism qabul qilindi.")

@dp.message_handler(lambda m: m.text == "Tugatish", state=AdminStates.waiting_for_video)
async def finish_videos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if not data.get('video_list'):
        await message.answer("Hech qanday video yubormadingiz!")
        return
    await AdminStates.waiting_for_id.set()
    await message.answer("Endi ushbu anime uchun umumiy ID kiriting (Faqat raqam):")

@dp.message_handler(state=AdminStates.waiting_for_id)
async def save_anime(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Faqat raqam kiriting!")
        return
    
    data = await state.get_data()
    anime_id = message.text
    video_list = data.get('video_list')
    
    conn = sqlite3.connect('data.db')
    # Oldin shu ID bo'lsa o'chirib tashlaymiz (yangilash uchun)
    conn.execute("DELETE FROM animes WHERE anime_id=?", (anime_id,))
    
    for index, file_id in enumerate(video_list, start=1):
        conn.execute("INSERT INTO animes VALUES (?, ?, ?)", (anime_id, file_id, index))
    
    conn.commit()
    conn.close()
    
    await state.finish()
    bot_user = await bot.get_me()
    await message.answer(f"Saqlandi! Hammasi bo'lib {len(video_list)} ta qism.\nLink: https://t.me/{bot_user.username}?start={anime_id}", 
                         reply_markup=get_main_kb(message.from_user.id))

# --- REKLAMA VA BOSHQALAR (O'zgarishsiz) ---
@dp.message_handler(lambda m: m.text == "Bekor qilish", state="*")
async def cancel(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("Bekor qilindi.", reply_markup=get_main_kb(message.from_user.id))

@dp.message_handler(lambda m: m.text == "Reklama" and m.from_user.id in CREATORS)
async def ad_start(message: types.Message):
    await AdminStates.waiting_for_ad.set()
    await message.answer("Kanal usernamesini yuboring (@kanal):")

@dp.message_handler(state=AdminStates.waiting_for_ad)
async def save_ad(message: types.Message, state: FSMContext):
    username = message.text.strip()
    if not username.startswith("@"):
        await message.answer("Xato! @ bilan boshlansin.")
        return
    try:
        await bot.get_chat_member(chat_id=username, user_id=(await bot.get_me()).id)
        conn = sqlite3.connect('data.db')
        conn.execute("INSERT OR IGNORE INTO ads VALUES (?)", (username,))
        conn.commit()
        conn.close()
        await message.answer("Reklama qo'shildi.", reply_markup=get_main_kb(message.from_user.id))
        await state.finish()
    except:
        await message.answer("Bot bu kanalda admin emas!")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
        
