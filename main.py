import sqlite3
import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# --- SOZLAMALAR ---
API_TOKEN = '8727688545:AAHFx47Uq5eu4NkMisQ8Pwr2omHv4QP83hI'
CREATORS = [6156296807, 8163861382]
CREATOR_USERNAME = "@fakevenx" # O'zingizning usernameingizni bering

# Loggingni sozlash
logging.basicConfig(level=logging.INFO)

# Bot va Dispatcher
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- BAZANI SOZLASH ---
def init_db():
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS animes (id TEXT PRIMARY KEY, file_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ads (username TEXT PRIMARY KEY)''')
    conn.commit()
    conn.close()

init_db()

# --- HOLATLAR ---
class AdminStates(StatesGroup):
    waiting_for_video = State()
    waiting_for_id = State()
    waiting_for_ad = State()

# --- KLAVIATURALAR ---
def get_main_kb(user_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if user_id in CREATORS:
        kb.add(types.KeyboardButton("Panel"))
    return kb

def get_panel_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("Anime Yuklash", "Reklama")
    kb.add("Bekor qilish")
    return kb

# --- ASOSIY HANDLERLAR ---

@dp.message_handler(commands=['start'], state="*")
async def start_cmd(message: types.Message, state: FSMContext):
    await state.finish()
    user_id = message.from_user.id
    args = message.get_args()

    # 1. Majburiy obunani tekshirish (Faqat oddiy foydalanuvchilar uchun)
    if user_id not in CREATORS:
        conn = sqlite3.connect('data.db')
        ads = conn.execute("SELECT username FROM ads").fetchall()
        conn.close()
        
        not_subbed = []
        for ad in ads:
            try:
                member = await bot.get_chat_member(chat_id=ad[0], user_id=user_id)
                if member.status in ['left', 'kicked']:
                    not_subbed.append(ad[0])
            except:
                continue

        if not_subbed:
            markup = types.InlineKeyboardMarkup(row_width=1)
            for ch in not_subbed:
                markup.add(types.InlineKeyboardButton(text="Obuna bo'lish", url=f"https://t.me/{ch.replace('@','')}"))
            markup.add(types.InlineKeyboardButton(text="Tekshirish ✅", callback_data="check_sub"))
            await message.answer("Iltimos, homiylarimizga obuna bo'ling!", reply_markup=markup)
            return

    # 2. Anime ID orqali kelgan bo'lsa
    if args:
        conn = sqlite3.connect('data.db')
        res = conn.execute("SELECT file_id FROM animes WHERE id=?", (args,)).fetchone()
        conn.close()
        if res:
            await bot.send_video(user_id, res[0], caption=f"Qism {args}")
            return
        else:
            await message.answer("Video topilmadi!")
            return

    # 3. Oddiy start xabari
    if user_id in CREATORS:
        await message.answer("Xush kelibsiz Creator!", reply_markup=get_main_kb(user_id))
    else:
        await message.answer(f"Bu botga yozmang! Bu bot xabarlarni qabul qilmaydi! Reklama uchun: {CREATOR_USERNAME}")

@dp.callback_query_handler(text="check_sub")
async def check_sub(call: types.CallbackQuery):
    user_id = call.from_user.id
    conn = sqlite3.connect('data.db')
    ads = conn.execute("SELECT username FROM ads").fetchall()
    conn.close()
    
    is_all_subbed = True
    for ad in ads:
        try:
            member = await bot.get_chat_member(chat_id=ad[0], user_id=user_id)
            if member.status in ['left', 'kicked']:
                is_all_subbed = False
                break
        except: continue
        
    if is_all_subbed:
        await call.message.delete()
        await call.message.answer(f"Bu botga yozmang! Bu bot xabarlarni qabul qilmaydi! Reklama uchun: {CREATOR_USERNAME}")
    else:
        await call.answer("Siz hali obuna bo'lmagansiz!", show_alert=True)

# --- PANEL FUNKSIYALARI ---

@dp.message_handler(lambda m: m.text == "Panel" and m.from_user.id in CREATORS)
async def open_panel(message: types.Message):
    await message.answer("Panel bosildi. Tanlang:", reply_markup=get_panel_kb())

@dp.message_handler(lambda m: m.text == "Bekor qilish", state="*")
async def cancel_action(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("Amal bekor qilindi.", reply_markup=get_main_kb(message.from_user.id))

# ANIME YUKLASH
@dp.message_handler(lambda m: m.text == "Anime Yuklash" and m.from_user.id in CREATORS)
async def upload_anime_start(message: types.Message):
    await AdminStates.waiting_for_video.set()
    await message.answer("Iltimos, video tashlang (Bekor qilish uchun tugmani bosing):")

@dp.message_handler(content_types=['video'], state=AdminStates.waiting_for_video)
async def get_video(message: types.Message, state: FSMContext):
    await state.update_data(vid=message.video.file_id)
    await AdminStates.waiting_for_id.set()
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True).add("Saqlash", "Bekor qilish")
    await message.answer("Video qabul qilindi. Endi 'Saqlash' tugmasini bosing.", reply_markup=markup)

@dp.message_handler(lambda m: m.text == "Saqlash", state=AdminStates.waiting_for_id)
async def ask_id(message: types.Message):
    await message.answer("Iltimos id Kiriting, Faqat raqam:")

@dp.message_handler(state=AdminStates.waiting_for_id)
async def save_anime_final(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Iltimos, faqat raqam kiriting!")
        return
    
    data = await state.get_data()
    anime_id = message.text
    file_id = data.get('vid')
    
    conn = sqlite3.connect('data.db')
    try:
        conn.execute("INSERT INTO animes VALUES (?, ?)", (anime_id, file_id))
        conn.commit()
        await message.answer("Saqlandi!", reply_markup=get_main_kb(message.from_user.id))
        await state.finish()
    except sqlite3.IntegrityError:
        await message.answer("Bu ID oldin kiritilgan! Boshqa raqam bering:")
    finally:
        conn.close()

# REKLAMA (MAJBURIY OBUNA)
@dp.message_handler(lambda m: m.text == "Reklama" and m.from_user.id in CREATORS)
async def ad_start(message: types.Message):
    await AdminStates.waiting_for_ad.set()
    await message.answer("Kanal yoki guruh usernamesini yuboring (@belgisi bilan):")

@dp.message_handler(state=AdminStates.waiting_for_ad)
async def save_ad_channel(message: types.Message, state: FSMContext):
    username = message.text.strip()
    if not username.startswith("@"):
        await message.answer("Username @ bilan boshlanishi kerak!")
        return

    try:
        # Bot kanalda adminligini tekshirish (membersni ko'ra olishi uchun)
        bot_member = await bot.get_chat_member(chat_id=username, user_id=(await bot.get_me()).id)
        
        conn = sqlite3.connect('data.db')
        conn.execute("INSERT OR IGNORE INTO ads VALUES (?)", (username,))
        conn.commit()
        conn.close()
        
        await message.answer("Muvaffaqiyatli Reklama kiritildi", reply_markup=get_main_kb(message.from_user.id))
        await state.finish()
    except:
        await message.answer("Kanal/Guruh ga bot ulanmagan! (Botni o'sha yerda admin qilishingiz kerak)")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
