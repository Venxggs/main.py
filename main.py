import sqlite3
import logging
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# --- SOZLAMALAR ---
API_TOKEN = '8727688545:AAEqdbDei89oXVarSUSEsJw0zCEHhQMRn1I'
CREATORS = [6156296807, 8163861382]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- BAZA ---
def init_db():
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS animes (anime_id TEXT, file_id TEXT, part_num INTEGER)''')
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
                await asyncio.sleep(0.5)
            return
        else:
            await message.answer("Xatolik: ID topilmadi.")
            return

    await message.answer("Xush kelibsiz!", reply_markup=get_main_kb(user_id))

@dp.message_handler(lambda m: m.text == "Panel" and m.from_user.id in CREATORS, state="*")
async def panel_cmd(message: types.Message):
    await message.answer("Panelga xush kelibsiz!", reply_markup=get_panel_kb())

@dp.message_handler(lambda m: m.text == "Anime Yuklash" and m.from_user.id in CREATORS, state="*")
async def upload_start(message: types.Message):
    await AdminStates.waiting_for_videos.set()
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True).add("Tugatish", "Bekor qilish")
    await message.answer("Videolarni ketma-ket yuboring. Tugatgach 'Tugatish' bosing.", reply_markup=kb)

@dp.message_handler(content_types=['video'], state=AdminStates.waiting_for_videos)
async def get_videos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    v_list = data.get('video_list', [])
    v_list.append(message.video.file_id)
    await state.update_data(video_list=v_list)
    await message.answer(f"{len(v_list)}-qism qabul qilindi.")

@dp.message_handler(lambda m: m.text == "Tugatish", state=AdminStates.waiting_for_videos)
async def finish_upload(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if not data.get('video_list'):
        await message.answer("Video yubormadingiz!")
        return
    await AdminStates.waiting_for_id.set()
    await message.answer("Endi anime ID raqamini kiriting:")

@dp.message_handler(state=AdminStates.waiting_for_id)
async def save_anime_final(message: types.Message, state: FSMContext):
    anime_id = message.text
    data = await state.get_data()
    video_list = data.get('video_list')
    
    conn = sqlite3.connect('data.db')
    conn.execute("DELETE FROM animes WHERE anime_id=?", (anime_id,))
    for i, f_id in enumerate(video_list, 1):
        conn.execute("INSERT INTO animes VALUES (?, ?, ?)", (anime_id, f_id, i))
    conn.commit()
    conn.close()
    
    bot_info = await bot.get_me()
    await message.answer(f"Saqlandi!\nLink: https://t.me/{bot_info.username}?start={anime_id}", reply_markup=get_main_kb(message.from_user.id))
    await state.finish()

@dp.message_handler(lambda m: m.text == "Bekor qilish", state="*")
async def cancel_handler(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("Bekor qilindi.", reply_markup=get_main_kb(message.from_user.id))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
                
