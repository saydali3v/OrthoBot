"""
OrthoTrack Bot v4
Роли: старший админ (все функции), продавщица (только подтверждение), врач
"""
import asyncio, sqlite3, random, string, os, json
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove, FSInputFile
)

load_dotenv()

BOT_TOKEN    = os.getenv("BOT_TOKEN", "")
SENIOR_ADMINS = [int(x) for x in os.getenv("SENIOR_ADMINS", "127036820").split(",") if x.strip()]
STAFF_IDS     = [int(x) for x in os.getenv("STAFF_IDS", "").split(",") if x.strip()]
BONUS_PCT     = float(os.getenv("BONUS_PCT", "18"))
DB_PATH       = "orthotrack.db"

def is_senior(uid): return uid in SENIOR_ADMINS
def is_staff(uid):  return uid in STAFF_IDS
def is_admin(uid):  return is_senior(uid) or is_staff(uid)

# ─────────────────────────────────────────────
# КАТАЛОГ ТОВАРОВ
# ─────────────────────────────────────────────
CATEGORIES = {
    "🦴 Позвоночник и спина": [
        ("AR540",  "Корсет грудопоясничный AR 540",    480_000),
        ("AR542",  "Корсет поясничный мягкий AR 542",  225_000),
        ("AR544",  "Корсет грудной AR 544",             330_000),
        ("AR573",  "Корсет поясничный AR 573",          300_000),
        ("AR541",  "Послеоперационный бандаж AR 541",   250_000),
        ("AR532",  "Ортопедическая подушка AR 532",     110_000),
        ("ORT_PODUSHKA", "Ортопедическая подушка",      350_000),
    ],
    "🧣 Шея": [
        ("AR546",      "Воротник шейный AR 546",        195_000),
        ("AR545",      "Воротник детский AR 545",        120_000),
        ("FILADELFIA", "Воротник Филадельфия",           300_000),
        ("NADUV",      "Надувной воротник",              185_000),
    ],
    "🦵 Колено и нога": [
        ("AR556",     "Ортез на колено AR 556",          280_000),
        ("AR575SH",   "Ортез колено с шарнирами AR 575", 385_000),
        ("AR575ST",   "Ортез колено со стержнями AR 575",385_000),
        ("REG_KOLENO","Регулируемый ортез на колено",    850_000),
        ("AR562",     "Голеностопный бандаж AR 562",     290_000),
        ("ROMWALKER", "Голеностопный ортез ROM Walker", 1_500_000),
        ("DEROT",     "Деротационный ортез",             655_000),
        ("DEROT_DET", "Деротационный ортез (детский)",   655_000),
    ],
    "🖐 Рука и запястье": [
        ("AR551","Ортез на запястье AR 551",             300_000),
        ("AR552","Ортез на запястье AR 552",             360_000),
        ("AR560","Ортез на руку AR 560",                 110_000),
        ("AR579","Ортез на руку AR 579",                 200_000),
        ("AR534","Ортез на руку AR 534",                 235_000),
    ],
    "🦶 Стопа": [
        ("STELNKI_ORT",  "Ортопедические стельки",       370_000),
        ("STELNKI_PLSK", "Стельки от плоскостопия",       50_000),
        ("AR604",        "Стельки AR 604",               200_000),
        ("NOSOCHKI",     "Носочки от плоскостопия",       70_000),
        ("VALGUS_MAN",   "Вальгусная манжетка",           70_000),
        ("VALGUS_RASP",  "Вальгусная распорка",           90_000),
        ("FIKSATOR",     "Фиксатор большого пальца",     100_000),
        ("OBUV_GIPS",    "Обувь для гипса",              400_000),
        ("OBUV580",      "Обувь 580",                    650_000),
    ],
    "🤰 Для беременных": [
        ("BAND_BERE","Бандаж для беременных",            250_000),
        ("BAND_GRUD","Бандаж для грудины",               325_000),
        ("BAND_TAZ", "Тазобедренный бандаж",             650_000),
    ],
    "🧦 Компрессия": [
        ("COMP_CHULKI","Компрессионные чулки",           430_000),
        ("COMP_KOLT",  "Компрессионные колготки",        440_000),
    ],
    "🚶 Опора и движение": [
        ("TROST",       "Трость",                        200_000),
        ("HODUNKI",     "Ходунки",                       550_000),
        ("KOSTYLI",     "Костыли",                       280_000),
        ("SHINA_FREIKA","Шина Фрейка",                   285_000),
    ],
    "💆 Массаж и восстановление": [
        ("ORT_KRUG",  "Ортопедический круг",              40_000),
        ("ORT_KOVRIK","Ортопедический коврик",           250_000),
        ("KUZNECOV",  "Аппликатор Кузнецова",            380_000),
        ("MASSAJ_VAL","Массажные валики",                200_000),
    ],
}

PRODUCTS: dict[str, tuple[str, int]] = {}
for _items in CATEGORIES.values():
    for _code, _name, _price in _items:
        PRODUCTS[_code] = (_name, _price)

HOURS_OPTIONS = ["1 час","2 часа","3 часа","4 часа","5 часов","6 часов","7 часов","8 часов","Завтра","На этой неделе"]

def fmt(amount: int) -> str:
    return f"{int(amount):,}".replace(",", " ") + " сум"

def cart_to_text(items_json: str) -> str:
    items = json.loads(items_json)
    lines = []
    total = 0
    for code, qty in items:
        name, price = PRODUCTS.get(code, (code, 0))
        sub = price * qty
        total += sub
        lines.append(f"  • {name} x{qty} = {fmt(sub)}")
    lines.append(f"\n💵 Итого: {fmt(total)}")
    return "\n".join(lines)

# ─────────────────────────────────────────────
# БАЗА ДАННЫХ
# ─────────────────────────────────────────────
def db():
    return sqlite3.connect(DB_PATH)

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS doctors (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id      INTEGER UNIQUE,
            full_name  TEXT NOT NULL,
            clinic     TEXT,
            phone      TEXT NOT NULL,
            code       TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            is_active  INTEGER DEFAULT 1,
            paid_bonus REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS referrals (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id    INTEGER NOT NULL,
            items_json   TEXT NOT NULL,
            total_price  INTEGER NOT NULL,
            expected_in  TEXT NOT NULL,
            status       TEXT DEFAULT 'pending',
            sent_at      TEXT DEFAULT (datetime('now','localtime')),
            bought_at    TEXT,
            bonus        REAL DEFAULT 0,
            ref_number   TEXT UNIQUE NOT NULL,
            confirmed_by INTEGER,
            FOREIGN KEY (doctor_id) REFERENCES doctors(id)
        );
        CREATE TABLE IF NOT EXISTS payments (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id  INTEGER NOT NULL,
            amount     REAL NOT NULL,
            paid_at    TEXT DEFAULT (datetime('now','localtime')),
            paid_by    INTEGER,
            note       TEXT,
            FOREIGN KEY (doctor_id) REFERENCES doctors(id)
        );
        """)

def unique_code():
    with db() as con:
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not con.execute("SELECT 1 FROM doctors WHERE code=?", (code,)).fetchone():
                return code

def unique_ref():
    with db() as con:
        while True:
            num = "ORD-" + ''.join(random.choices(string.digits, k=6))
            if not con.execute("SELECT 1 FROM referrals WHERE ref_number=?", (num,)).fetchone():
                return num

def doctor_by_tg(tg_id):
    with db() as con:
        return con.execute("SELECT * FROM doctors WHERE tg_id=?", (tg_id,)).fetchone()

def doctor_stats(doctor_id):
    with db() as con:
        r = con.execute("""
            SELECT COUNT(*),
                   SUM(CASE WHEN status='bought' THEN 1 ELSE 0 END),
                   COALESCE(SUM(CASE WHEN status='bought' THEN bonus ELSE 0 END),0)
            FROM referrals WHERE doctor_id=?
        """, (doctor_id,)).fetchone()
        paid = con.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE doctor_id=?", (doctor_id,)).fetchone()[0]
    return r[0], r[1] or 0, r[2] or 0, paid or 0

def pending_refs():
    with db() as con:
        return con.execute("""
            SELECT r.id, d.full_name, d.clinic, d.phone,
                   r.items_json, r.total_price, r.expected_in, r.sent_at, r.ref_number, d.id
            FROM referrals r JOIN doctors d ON d.id=r.doctor_id
            WHERE r.status='pending' ORDER BY r.sent_at ASC
        """).fetchall()

def all_doctors():
    with db() as con:
        return con.execute("""
            SELECT d.id, d.full_name, d.clinic, d.phone,
                   COUNT(r.id) AS total,
                   SUM(CASE WHEN r.status='bought' THEN 1 ELSE 0 END) AS bought,
                   COALESCE(SUM(CASE WHEN r.status='bought' THEN r.bonus ELSE 0 END),0) AS earned,
                   COALESCE((SELECT SUM(amount) FROM payments WHERE doctor_id=d.id),0) AS paid
            FROM doctors d
            LEFT JOIN referrals r ON r.doctor_id=d.id
            WHERE d.is_active=1
            GROUP BY d.id ORDER BY (earned - COALESCE((SELECT SUM(amount) FROM payments WHERE doctor_id=d.id),0)) DESC
        """).fetchall()

def global_stats():
    with db() as con:
        docs  = con.execute("SELECT COUNT(*) FROM doctors WHERE is_active=1").fetchone()[0]
        refs  = con.execute("""
            SELECT COUNT(*),
                   SUM(CASE WHEN status='bought'  THEN 1 ELSE 0 END),
                   SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END),
                   COALESCE(SUM(CASE WHEN status='bought' THEN bonus ELSE 0 END),0)
            FROM referrals
        """).fetchone()
        today = datetime.now().strftime("%Y-%m-%d")
        today_r = con.execute("""
            SELECT COUNT(*), SUM(CASE WHEN status='bought' THEN 1 ELSE 0 END)
            FROM referrals WHERE sent_at LIKE ?
        """, (f"{today}%",)).fetchone()
    return docs, refs, today_r

# ─────────────────────────────────────────────
# КЛАВИАТУРЫ
# ─────────────────────────────────────────────
def kb_senior():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="⏳ Ожидаемые клиенты"), KeyboardButton(text="👨‍⚕️ Все врачи")],
        [KeyboardButton(text="💰 Выплатить бонус"),   KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="📋 История"),            KeyboardButton(text="💾 Бэкап")],
    ])

def kb_staff():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="⏳ Ожидаемые клиенты")],
        [KeyboardButton(text="📊 Статистика")],
    ])

def kb_doctor():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="📤 Отправить клиента")],
        [KeyboardButton(text="📊 Мои показатели"), KeyboardButton(text="🕐 Мои направления")],
    ])

def main_kb(uid):
    if is_senior(uid): return kb_senior()
    if is_staff(uid):  return kb_staff()
    return kb_doctor()

def kb_categories():
    buttons = [[KeyboardButton(text=cat)] for cat in CATEGORIES.keys()]
    buttons.append([KeyboardButton(text="🛒 Корзина"), KeyboardButton(text="✅ Отправить направление")])
    buttons.append([KeyboardButton(text="◀️ Отмена")])
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=buttons)

def kb_products(category):
    items = CATEGORIES.get(category, [])
    buttons = [[KeyboardButton(text=f"{name} — {fmt(price)}")] for _, name, price in items]
    buttons.append([KeyboardButton(text="🛒 Корзина"), KeyboardButton(text="✅ Отправить направление")])
    buttons.append([KeyboardButton(text="◀️ К категориям")])
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=buttons)

def kb_hours():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text=h) for h in HOURS_OPTIONS[:4]],
        [KeyboardButton(text=h) for h in HOURS_OPTIONS[4:8]],
        [KeyboardButton(text=HOURS_OPTIONS[8]), KeyboardButton(text=HOURS_OPTIONS[9])],
        [KeyboardButton(text="◀️ Назад")],
    ])

def inline_sale(ref_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Купил",    callback_data=f"bought:{ref_id}"),
        InlineKeyboardButton(text="❌ Не купил", callback_data=f"nobuy:{ref_id}"),
    ]])

def inline_doctors_pay():
    doctors = all_doctors()
    buttons = []
    for did, name, clinic, phone, total, bought, earned, paid in doctors:
        balance = earned - paid
        if balance > 0:
            buttons.append([InlineKeyboardButton(
                text=f"{name} — {fmt(balance)}",
                callback_data=f"paydoc:{did}"
            )])
    if not buttons:
        return None
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ─────────────────────────────────────────────
# FSM
# ─────────────────────────────────────────────
class RegDoctor(StatesGroup):
    last_name  = State()
    first_name = State()
    patronymic = State()
    clinic     = State()
    phone      = State()

class SendClient(StatesGroup):
    shopping = State()
    hours    = State()
    confirm  = State()

class PayBonus(StatesGroup):
    amount = State()
    photo  = State()

# ─────────────────────────────────────────────
# БОТ
# ─────────────────────────────────────────────
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp  = Dispatcher(storage=MemoryStorage())

# ── /start ────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(msg: types.Message, state: FSMContext):
    await state.clear()
    uid = msg.from_user.id
    if is_admin(uid):
        role = "👑 Старший администратор" if is_senior(uid) else "🏪 Сотрудник магазина"
        await msg.answer(f"👋 <b>Добро пожаловать!</b>\n{role}", reply_markup=main_kb(uid))
        return
    doc = doctor_by_tg(uid)
    if doc:
        total, bought, earned, paid = doctor_stats(doc[0])
        balance = earned - paid
        conv = round(bought/total*100) if total else 0
        await msg.answer(
            f"👋 С возвращением, <b>Dr. {doc[2]}</b>!\n"
            f"🏥 {doc[3]}  |  📱 {doc[4]}\n\n"
            f"📤 Направлений: <b>{total}</b>  ✅ Купили: <b>{bought}</b> ({conv}%)\n"
            f"💰 Заработано: <b>{fmt(int(earned))}</b>\n"
            f"✅ Выплачено: <b>{fmt(int(paid))}</b>\n"
            f"💵 К выплате: <b>{fmt(int(balance))}</b>",
            reply_markup=kb_doctor()
        )
    else:
        await msg.answer("👋 <b>Добро пожаловать!</b>\n\nВведите вашу <b>Фамилию</b>:")
        await state.set_state(RegDoctor.last_name)

# ── Регистрация врача ─────────────────────────
@dp.message(RegDoctor.last_name)
async def reg_last(msg: types.Message, state: FSMContext):
    val = msg.text.strip()
    if len(val) < 2 or ' ' in val:
        await msg.answer("❌ Введите только <b>Фамилию</b> одним словом\nНапример: <b>Иванов</b>"); return
    await state.update_data(last_name=val)
    await msg.answer("✅ Принято.\n\nВведите ваше <b>Имя</b>:")
    await state.set_state(RegDoctor.first_name)

@dp.message(RegDoctor.first_name)
async def reg_first(msg: types.Message, state: FSMContext):
    val = msg.text.strip()
    if len(val) < 2 or ' ' in val:
        await msg.answer("❌ Введите только <b>Имя</b> одним словом\nНапример: <b>Иван</b>"); return
    await state.update_data(first_name=val)
    await msg.answer("✅ Принято.\n\nВведите ваше <b>Отчество</b>:")
    await state.set_state(RegDoctor.patronymic)

@dp.message(RegDoctor.patronymic)
async def reg_pat(msg: types.Message, state: FSMContext):
    val = msg.text.strip()
    if len(val) < 2 or ' ' in val:
        await msg.answer("❌ Введите только <b>Отчество</b> одним словом\nНапример: <b>Иванович</b>"); return
    await state.update_data(patronymic=val)
    await msg.answer("✅ Принято.\n\n🏥 Название клиники или больницы:")
    await state.set_state(RegDoctor.clinic)

@dp.message(RegDoctor.clinic)
async def reg_clinic(msg: types.Message, state: FSMContext):
    await state.update_data(clinic=msg.text.strip())
    await msg.answer("📱 Ваш номер телефона:\n<i>Можно написать полный или последние 4 цифры</i>")
    await state.set_state(RegDoctor.phone)

@dp.message(RegDoctor.phone)
async def reg_phone(msg: types.Message, state: FSMContext):
    phone  = msg.text.strip()
    digits = ''.join(c for c in phone if c.isdigit())
    if len(digits) < 4:
        await msg.answer("❌ Введите хотя бы <b>4 цифры</b> номера телефона"); return
    data      = await state.get_data()
    full_name = f"{data['last_name']} {data['first_name']} {data['patronymic']}"
    code      = unique_code()
    with db() as con:
        con.execute("INSERT INTO doctors (tg_id,full_name,clinic,phone,code) VALUES (?,?,?,?,?)",
                    (msg.from_user.id, full_name, data["clinic"], phone, code))
    await state.clear()
    await msg.answer(
        f"✅ <b>Регистрация завершена!</b>\n\n"
        f"👤 {full_name}\n🏥 {data['clinic']}\n📱 {phone}\n\n"
        f"За каждую покупку клиента — <b>{BONUS_PCT:.0f}% бонус</b> 💰",
        reply_markup=kb_doctor()
    )
    for aid in SENIOR_ADMINS:
        try:
            await bot.send_message(aid, f"🆕 <b>Новый врач!</b>\n👤 {full_name}\n🏥 {data['clinic']}\n📱 {phone}")
        except: pass

# ── Отправить клиента (корзина) ───────────────
@dp.message(F.text == "📤 Отправить клиента")
async def send_start(msg: types.Message, state: FSMContext):
    doc = doctor_by_tg(msg.from_user.id)
    if not doc:
        await msg.answer("❌ Сначала зарегистрируйтесь — /start"); return
    await state.update_data(doctor_id=doc[0], doctor_name=doc[2], doctor_tg=msg.from_user.id, cart=[], current_cat=None)
    await msg.answer(
        "🛒 <b>Добавьте товары в корзину</b>\n\n"
        "Выберите категорию → товар → добавится в корзину\n"
        "Когда готово — нажмите <b>✅ Отправить направление</b>",
        reply_markup=kb_categories()
    )
    await state.set_state(SendClient.shopping)

@dp.message(SendClient.shopping)
async def shopping(msg: types.Message, state: FSMContext):
    text = msg.text
    data = await state.get_data()
    cart: list = data.get("cart", [])

    if text == "◀️ Отмена":
        await state.clear()
        await msg.answer("Отменено.", reply_markup=kb_doctor()); return

    if text == "◀️ К категориям":
        await state.update_data(current_cat=None)
        await msg.answer("Выберите категорию:", reply_markup=kb_categories()); return

    if text == "🛒 Корзина":
        if not cart:
            await msg.answer("🛒 Корзина пуста."); return
        total = sum(PRODUCTS.get(c,("",0))[1]*q for c,q in cart)
        lines = ["🛒 <b>Корзина:</b>\n"]
        for code, qty in cart:
            name, price = PRODUCTS.get(code,(code,0))
            lines.append(f"• {name} x{qty} = {fmt(price*qty)}")
        lines.append(f"\n💵 <b>Итого: {fmt(total)}</b>")
        await msg.answer("\n".join(lines)); return

    if text == "✅ Отправить направление":
        if not cart:
            await msg.answer("🛒 Корзина пуста! Добавьте товар."); return
        total = sum(PRODUCTS.get(c,("",0))[1]*q for c,q in cart)
        lines = ["✅ <b>Товары:</b>\n"]
        for code, qty in cart:
            name, price = PRODUCTS.get(code,(code,0))
            lines.append(f"• {name} x{qty} = {fmt(price*qty)}")
        lines.append(f"\n💵 <b>Итого: {fmt(total)}</b>\n\n⏰ <b>Через сколько придёт клиент?</b>")
        await msg.answer("\n".join(lines), reply_markup=kb_hours())
        await state.set_state(SendClient.hours); return

    if text in CATEGORIES:
        await state.update_data(current_cat=text)
        cnt = sum(q for _,q in cart)
        hint = f"🛒 {cnt} товаров в корзине\n\n" if cnt else ""
        await msg.answer(f"{hint}📋 <b>{text}</b>\nВыберите товар:", reply_markup=kb_products(text)); return

    current_cat = data.get("current_cat")
    if current_cat and current_cat in CATEGORIES:
        for code, name, price in CATEGORIES[current_cat]:
            if text == f"{name} — {fmt(price)}":
                found = False
                for i,(c,q) in enumerate(cart):
                    if c == code:
                        cart[i] = (c, q+1); found = True; break
                if not found: cart.append((code, 1))
                await state.update_data(cart=cart)
                total = sum(PRODUCTS.get(c,("",0))[1]*q for c,q in cart)
                await msg.answer(
                    f"✅ <b>{name}</b> добавлен!\n"
                    f"🛒 {sum(q for _,q in cart)} товаров | 💵 {fmt(total)}\n\n"
                    f"Добавьте ещё или нажмите <b>✅ Отправить направление</b>"
                ); return
    await msg.answer("Выберите из списка:")

@dp.message(SendClient.hours)
async def send_hours(msg: types.Message, state: FSMContext):
    if msg.text == "◀️ Назад":
        await msg.answer("Выберите категорию:", reply_markup=kb_categories())
        await state.set_state(SendClient.shopping); return
    if msg.text not in HOURS_OPTIONS:
        await msg.answer("Выберите время из списка:"); return
    await state.update_data(hours=msg.text)
    data  = await state.get_data()
    cart  = data["cart"]
    total = sum(PRODUCTS.get(c,("",0))[1]*q for c,q in cart)
    lines = ["📋 <b>Подтвердите направление:</b>\n"]
    for code, qty in cart:
        name, price = PRODUCTS.get(code,(code,0))
        lines.append(f"• {name} x{qty} = {fmt(price*qty)}")
    lines.append(f"\n💵 <b>Итого: {fmt(total)}</b>")
    lines.append(f"⏰ Клиент придёт: <b>{msg.text}</b>")
    await msg.answer("\n".join(lines), reply_markup=ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="✅ Подтвердить")], [KeyboardButton(text="◀️ Назад")]
    ]))
    await state.set_state(SendClient.confirm)

@dp.message(SendClient.confirm)
async def send_confirm(msg: types.Message, state: FSMContext):
    if msg.text == "◀️ Назад":
        await msg.answer("Выберите время:", reply_markup=kb_hours())
        await state.set_state(SendClient.hours); return
    if msg.text != "✅ Подтвердить": return
    data       = await state.get_data()
    cart       = data["cart"]
    hours      = data["hours"]
    items_json = json.dumps(cart)
    total      = sum(PRODUCTS.get(c,("",0))[1]*q for c,q in cart)
    ref_num    = unique_ref()
    sent_time  = datetime.now().strftime("%d.%m.%Y %H:%M")
    with db() as con:
        cur = con.execute("INSERT INTO referrals (doctor_id,items_json,total_price,expected_in,ref_number) VALUES (?,?,?,?,?)",
                          (data["doctor_id"], items_json, total, hours, ref_num))
        ref_id = cur.lastrowid
    await state.clear()
    lines = [f"✅ <b>Направление отправлено!</b>\n",
             f"🔖 <b>{ref_num}</b>  |  📅 {sent_time}\n"]
    for code, qty in cart:
        name, _ = PRODUCTS.get(code,(code,0))
        lines.append(f"• {name} x{qty}")
    lines.append(f"\n💵 {fmt(total)}\n⏰ Клиент придёт: {hours}")
    await msg.answer("\n".join(lines), reply_markup=kb_doctor())

    all_admins = list(set(SENIOR_ADMINS + STAFF_IDS))
    adm_lines = [f"🔔 <b>Новый клиент от врача!</b>\n",
                 f"👨‍⚕️ <b>{data['doctor_name']}</b>",
                 f"⏰ <b>{hours}</b>  |  🔖 {ref_num}  |  📅 {sent_time}\n",
                 f"<b>Товары:</b>"]
    for code, qty in cart:
        name, price = PRODUCTS.get(code,(code,0))
        adm_lines.append(f"• {name} x{qty} = {fmt(price*qty)}")
    adm_lines.append(f"\n💵 <b>Итого: {fmt(total)}</b>")
    for aid in all_admins:
        try:
            await bot.send_message(aid, "\n".join(adm_lines), reply_markup=inline_sale(ref_id))
        except: pass

# ── Купил / Не купил ──────────────────────────
@dp.callback_query(F.data.startswith("bought:"))
async def cb_bought(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа"); return
    ref_id = int(call.data.split(":")[1])
    with db() as con:
        ref = con.execute(
            "SELECT r.*,d.full_name,d.tg_id FROM referrals r JOIN doctors d ON d.id=r.doctor_id WHERE r.id=?",
            (ref_id,)
        ).fetchone()
    if not ref or ref[5] != "pending":
        await call.answer("Уже обработано"); return
    bought_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    bonus = round(ref[3] * BONUS_PCT / 100)
    with db() as con:
        con.execute("UPDATE referrals SET status='bought',bought_at=?,bonus=?,confirmed_by=? WHERE id=?",
                    (bought_time, bonus, call.from_user.id, ref_id))
    _, bought_cnt, total_earned, total_paid = doctor_stats(ref[1])
    balance = total_earned - total_paid
    await call.message.edit_text(
        f"✅ <b>Продажа подтверждена!</b>\n\n"
        f"👨‍⚕️ {ref[10]}\n🔖 {ref[9]}\n"
        f"📅 <b>{bought_time}</b>\n\n"
        f"{cart_to_text(ref[2])}\n\n"
        f"💰 Бонус врача: <b>{fmt(bonus)}</b>"
    )
    await call.answer("✅ Записано!")
    if ref[11]:
        try:
            await bot.send_message(ref[11],
                f"🎉 <b>Ваш клиент совершил покупку!</b>\n\n"
                f"🔖 {ref[9]}\n📅 <b>{bought_time}</b>\n\n"
                f"{cart_to_text(ref[2])}\n\n"
                f"💰 Начислено: <b>{fmt(bonus)}</b>\n"
                f"💵 К выплате: <b>{fmt(int(balance))}</b>"
            )
        except: pass

@dp.callback_query(F.data.startswith("nobuy:"))
async def cb_nobuy(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа"); return
    ref_id = int(call.data.split(":")[1])
    with db() as con:
        ref = con.execute(
            "SELECT r.*,d.full_name,d.tg_id FROM referrals r JOIN doctors d ON d.id=r.doctor_id WHERE r.id=?",
            (ref_id,)
        ).fetchone()
        if ref and ref[5] == "pending":
            con.execute("UPDATE referrals SET status='notbought',bought_at=datetime('now','localtime'),confirmed_by=? WHERE id=?",
                        (call.from_user.id, ref_id))
    if ref:
        nobuy_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        await call.message.edit_text(
            f"❌ <b>Не купил</b>\n\n👨‍⚕️ {ref[10]}\n🔖 {ref[9]}\n📅 {nobuy_time}\n\n{cart_to_text(ref[2])}"
        )
        if ref[11]:
            try:
                await bot.send_message(ref[11],
                    f"📊 <b>Отчёт</b>\n🔖 {ref[9]}\n📅 {nobuy_time}\n\n{cart_to_text(ref[2])}\n\n❌ Клиент не купил. Бонус не начислен.")
            except: pass
    await call.answer()

# ── Выплата бонуса ────────────────────────────
@dp.message(F.text == "💰 Выплатить бонус")
async def pay_bonus_start(msg: types.Message, state: FSMContext):
    if not is_senior(msg.from_user.id): return
    kb = inline_doctors_pay()
    if not kb:
        await msg.answer("💰 Нет врачей с невыплаченными бонусами."); return
    await msg.answer("👨‍⚕️ <b>Выберите врача для выплаты:</b>", reply_markup=kb)

@dp.callback_query(F.data.startswith("paydoc:"))
async def pay_select_doctor(call: types.CallbackQuery, state: FSMContext):
    if not is_senior(call.from_user.id):
        await call.answer("Нет доступа"); return
    doc_id = int(call.data.split(":")[1])
    with db() as con:
        doc = con.execute("SELECT * FROM doctors WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        await call.answer("Врач не найден"); return
    total, bought, earned, paid = doctor_stats(doc_id)
    balance = earned - paid
    await state.update_data(pay_doctor_id=doc_id, pay_doctor_name=doc[2],
                            pay_doctor_tg=doc[1], pay_balance=balance)
    await call.message.edit_text(
        f"👨‍⚕️ <b>{doc[2]}</b>\n🏥 {doc[3]}  |  📱 {doc[4]}\n\n"
        f"💰 Заработано: <b>{fmt(int(earned))}</b>\n"
        f"✅ Выплачено ранее: <b>{fmt(int(paid))}</b>\n"
        f"💵 К выплате: <b>{fmt(int(balance))}</b>\n\n"
        f"Введите <b>сумму выплаты</b> в сумах:"
    )
    await state.set_state(PayBonus.amount)
    await call.answer()

@dp.message(PayBonus.amount)
async def pay_amount(msg: types.Message, state: FSMContext):
    if not is_senior(msg.from_user.id): return
    try:
        amount = float(msg.text.replace(" ","").replace(",",".").replace("сум","").strip())
        if amount <= 0: raise ValueError
    except ValueError:
        await msg.answer("❌ Введите корректную сумму, например: 150000"); return
    data = await state.get_data()
    if amount > data["pay_balance"]:
        await msg.answer(f"❌ Сумма превышает баланс врача ({fmt(int(data['pay_balance']))})\nВведите меньшую сумму:"); return
    await state.update_data(pay_amount=amount)
    await msg.answer(
        f"📸 Теперь отправьте <b>фото чека</b> или скриншот перевода\n\n"
        f"Сумма выплаты: <b>{fmt(int(amount))}</b>\n"
        f"Врач: <b>{data['pay_doctor_name']}</b>"
    )
    await state.set_state(PayBonus.photo)

@dp.message(PayBonus.photo, F.photo)
async def pay_photo(msg: types.Message, state: FSMContext):
    if not is_senior(msg.from_user.id): return
    data   = await state.get_data()
    amount = data["pay_amount"]
    doc_id = data["pay_doctor_id"]
    paid_time = datetime.now().strftime("%d.%m.%Y %H:%M")

    with db() as con:
        con.execute("INSERT INTO payments (doctor_id,amount,paid_by) VALUES (?,?,?)",
                    (doc_id, amount, msg.from_user.id))

    _, _, earned, paid_total = doctor_stats(doc_id)
    balance = earned - paid_total

    await state.clear()

    # Подтверждение для старшего админа
    await msg.answer(
        f"✅ <b>Выплата записана!</b>\n\n"
        f"👨‍⚕️ {data['pay_doctor_name']}\n"
        f"💰 Выплачено: <b>{fmt(int(amount))}</b>\n"
        f"💵 Остаток: <b>{fmt(int(balance))}</b>\n"
        f"📅 {paid_time}"
    )

    # Уведомление всем старшим админам с фото чека
    photo_id = msg.photo[-1].file_id
    caption = (
        f"💰 <b>Выплата бонуса врачу</b>\n\n"
        f"👨‍⚕️ {data['pay_doctor_name']}\n"
        f"💰 Выплачено: <b>{fmt(int(amount))}</b>\n"
        f"💵 Остаток: <b>{fmt(int(balance))}</b>\n"
        f"📅 {paid_time}"
    )
    for aid in SENIOR_ADMINS:
        if aid != msg.from_user.id:
            try:
                await bot.send_photo(aid, photo_id, caption=caption)
            except: pass

    # Уведомление врачу с фото чека
    if data.get("pay_doctor_tg"):
        try:
            await bot.send_photo(
                data["pay_doctor_tg"], photo_id,
                caption=f"✅ <b>Вам выплачен бонус!</b>\n\n"
                        f"💰 Выплачено: <b>{fmt(int(amount))}</b>\n"
                        f"💵 Остаток к выплате: <b>{fmt(int(balance))}</b>\n"
                        f"📅 {paid_time}"
            )
        except: pass

@dp.message(PayBonus.photo)
async def pay_photo_wrong(msg: types.Message):
    await msg.answer("📸 Пожалуйста, отправьте <b>фото</b> чека или скриншот перевода")

# ── Кнопки врача ──────────────────────────────
@dp.message(F.text == "📊 Мои показатели")
async def doc_stats(msg: types.Message):
    doc = doctor_by_tg(msg.from_user.id)
    if not doc: return
    total, bought, earned, paid = doctor_stats(doc[0])
    balance = earned - paid
    notbought = total - bought
    conv = round(bought/total*100) if total else 0
    await msg.answer(
        f"📊 <b>Ваша статистика</b>\n\n"
        f"👤 {doc[2]}\n🏥 {doc[3]}\n📱 {doc[4]}\n\n"
        f"📤 Направлений: <b>{total}</b>\n"
        f"✅ Купили: <b>{bought}</b>  ❌ Не купили: <b>{notbought}</b>\n"
        f"📈 Конверсия: <b>{conv}%</b>\n\n"
        f"💰 Заработано: <b>{fmt(int(earned))}</b>\n"
        f"✅ Выплачено: <b>{fmt(int(paid))}</b>\n"
        f"💵 <b>К выплате: {fmt(int(balance))}</b>"
    )

@dp.message(F.text == "🕐 Мои направления")
async def doc_refs(msg: types.Message):
    doc = doctor_by_tg(msg.from_user.id)
    if not doc: return
    with db() as con:
        refs = con.execute("""
            SELECT items_json,expected_in,status,bonus,sent_at,bought_at,ref_number
            FROM referrals WHERE doctor_id=? ORDER BY sent_at DESC LIMIT 10
        """, (doc[0],)).fetchall()
    if not refs:
        await msg.answer("📭 Направлений пока нет."); return
    sm = {"pending":"⏳","bought":"✅","notbought":"❌"}
    lines = ["🕐 <b>Последние направления:</b>\n"]
    for items_json, hours, status, bonus, sent_at, bought_at, ref_num in refs:
        b  = f" | 💰 {fmt(int(bonus))}" if status=="bought" else ""
        dt = f"\n   📅 {bought_at}" if status=="bought" and bought_at else ""
        items = json.loads(items_json)
        names = ", ".join(PRODUCTS.get(c,(c,0))[0] for c,_ in items)
        lines.append(f"{sm.get(status,'?')} <b>{ref_num}</b>{b}\n   📦 {names}{dt}\n   🕐 {sent_at[:16]}\n")
    await msg.answer("\n".join(lines))

# ── Кнопки администратора ─────────────────────
@dp.message(F.text == "⏳ Ожидаемые клиенты")
async def admin_pending(msg: types.Message):
    if not is_admin(msg.from_user.id): return
    refs = pending_refs()
    if not refs:
        await msg.answer("📭 Нет ожидаемых клиентов."); return
    await msg.answer(f"⏳ <b>Ожидаемых: {len(refs)}</b>")
    for ref_id, name, clinic, phone, items_json, total, hours, sent_at, ref_num, doc_id in refs:
        await msg.answer(
            f"👨‍⚕️ <b>{name}</b>  ({clinic})\n📱 {phone}\n"
            f"🔖 {ref_num}  |  ⏰ {hours}  |  🕐 {sent_at[11:16]}\n\n"
            f"{cart_to_text(items_json)}",
            reply_markup=inline_sale(ref_id)
        )

@dp.message(F.text == "👨‍⚕️ Все врачи")
async def admin_doctors(msg: types.Message):
    if not is_senior(msg.from_user.id): return
    doctors = all_doctors()
    if not doctors:
        await msg.answer("📭 Врачей пока нет."); return
    lines = ["👨‍⚕️ <b>Все врачи:</b>\n"]
    for i, (did, name, clinic, phone, total, bought, earned, paid) in enumerate(doctors, 1):
        balance = earned - paid
        conv = round(bought/total*100) if total else 0
        lines.append(
            f"{i}. <b>{name}</b>\n"
            f"   🏥 {clinic}  |  📱 {phone}\n"
            f"   📤 {total} | ✅ {bought} ({conv}%)\n"
            f"   💰 Заработано: {fmt(int(earned))}  |  💵 К выплате: <b>{fmt(int(balance))}</b>\n"
        )
    text = "\n".join(lines)
    for chunk in [text[i:i+4000] for i in range(0,len(text),4000)]:
        await msg.answer(chunk)

@dp.message(F.text == "📊 Статистика")
async def admin_stats(msg: types.Message):
    if not is_admin(msg.from_user.id): return
    docs, (total,bought,pending,bonus), (td_total,td_bought) = global_stats()
    conv = round((bought or 0)/total*100) if total else 0
    await msg.answer(
        f"📊 <b>Статистика магазина</b>\n\n"
        f"👨‍⚕️ Врачей: <b>{docs}</b>\n\n"
        f"📤 Направлений: <b>{total}</b>\n"
        f"✅ Купили: <b>{bought or 0}</b> ({conv}%)\n"
        f"⏳ Ожидаются: <b>{pending or 0}</b>\n"
        f"💰 Бонусов начислено: <b>{fmt(int(bonus or 0))}</b>\n\n"
        f"📅 <b>Сегодня:</b>  📤 {td_total}  |  ✅ {td_bought or 0}"
    )

@dp.message(F.text == "📋 История")
async def admin_history(msg: types.Message):
    if not is_admin(msg.from_user.id): return
    with db() as con:
        refs = con.execute("""
            SELECT d.full_name, r.items_json, r.status, r.bonus, r.sent_at, r.bought_at, r.ref_number
            FROM referrals r JOIN doctors d ON d.id=r.doctor_id
            ORDER BY r.sent_at DESC LIMIT 15
        """).fetchall()
    if not refs:
        await msg.answer("📭 Истории нет."); return
    sm = {"pending":"⏳","bought":"✅","notbought":"❌"}
    lines = ["📋 <b>Последние 15:</b>\n"]
    for name, items_json, status, bonus, sent_at, bought_at, ref_num in refs:
        items = json.loads(items_json)
        names = ", ".join(PRODUCTS.get(c,(c,0))[0] for c,_ in items)
        b  = f" | 💰{fmt(int(bonus))}" if status=="bought" else ""
        dt = f"\n   📅 {bought_at}" if status=="bought" and bought_at else ""
        lines.append(f"{sm.get(status,'?')} <b>{name}</b> — {ref_num}{b}\n   📦 {names}{dt}\n   🕐 {sent_at[:16]}\n")
    await msg.answer("\n".join(lines))

# ── Бэкап ─────────────────────────────────────
async def send_backup(chat_id: int):
    if not os.path.exists(DB_PATH):
        await bot.send_message(chat_id, "❌ База данных не найдена."); return
    with db() as con:
        docs   = con.execute("SELECT COUNT(*) FROM doctors WHERE is_active=1").fetchone()[0]
        total  = con.execute("SELECT COUNT(*) FROM referrals").fetchone()[0]
        bought = con.execute("SELECT COUNT(*) FROM referrals WHERE status='bought'").fetchone()[0]
        bonus  = con.execute("SELECT COALESCE(SUM(bonus),0) FROM referrals WHERE status='bought'").fetchone()[0]
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    caption = (f"💾 <b>Бэкап OrthoShop</b>\n\n📅 {now}\n"
               f"👨‍⚕️ Врачей: <b>{docs}</b>\n📤 Направлений: <b>{total}</b>\n"
               f"✅ Куплено: <b>{bought}</b>\n💰 Бонусов: <b>{fmt(int(bonus))}</b>")
    name = f"orthotrack_{datetime.now().strftime('%Y%m%d_%H%M')}.db"
    await bot.send_document(chat_id, FSInputFile(DB_PATH, filename=name), caption=caption)

@dp.message(Command("backup"))
@dp.message(F.text == "💾 Бэкап")
async def cmd_backup(msg: types.Message):
    if not is_senior(msg.from_user.id):
        await msg.answer("❌ Только для старшего администратора."); return
    await msg.answer("⏳ Готовлю бэкап...")
    await send_backup(msg.from_user.id)

async def daily_backup():
    while True:
        now    = datetime.now()
        target = now.replace(hour=23, minute=0, second=0, microsecond=0)
        if now >= target:
            from datetime import timedelta
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        for aid in SENIOR_ADMINS:
            try: await send_backup(aid)
            except: pass

# ─────────────────────────────────────────────
async def main():
    init_db()
    print("✅ OrthoTrack v4 запущен!")
    asyncio.create_task(daily_backup())
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
