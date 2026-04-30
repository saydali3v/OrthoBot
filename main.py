"""
OrthoTrack Bot v3 — корзина, цены в сумах, доказательство временем
"""
import asyncio, sqlite3, random, string, os
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
    ReplyKeyboardRemove
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(",")]
BONUS_PCT = float(os.getenv("BONUS_PCT", "20"))
DB_PATH   = "orthotrack.db"

# ─────────────────────────────────────────────
# КАТАЛОГ ТОВАРОВ С ЦЕНАМИ (в сумах)
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
        ("AR556",    "Ортез на колено AR 556",           280_000),
        ("AR575SH",  "Ортез колено с шарнирами AR 575",  385_000),
        ("AR575ST",  "Ортез колено со стержнями AR 575", 385_000),
        ("REG_KOLENO","Регулируемый ортез на колено",    850_000),
        ("AR562",    "Голеностопный бандаж AR 562",      290_000),
        ("ROMWALKER","Голеностопный ортез ROM Walker",  1_500_000),
        ("DEROT",    "Деротационный ортез",              655_000),
        ("DEROT_DET","Деротационный ортез (детский)",    655_000),
    ],
    "🖐 Рука и запястье": [
        ("AR551", "Ортез на запястье AR 551",            300_000),
        ("AR552", "Ортез на запястье AR 552",            360_000),
        ("AR560", "Ортез на руку AR 560",                110_000),
        ("AR579", "Ортез на руку AR 579",                200_000),
        ("AR534", "Ортез на руку AR 534",                235_000),
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
        ("BAND_BERE", "Бандаж для беременных",           250_000),
        ("BAND_GRUD", "Бандаж для грудины",              325_000),
        ("BAND_TAZ",  "Тазобедренный бандаж",            650_000),
    ],
    "🧦 Компрессия": [
        ("COMP_CHULKI", "Компрессионные чулки",          430_000),
        ("COMP_KOLT",   "Компрессионные колготки",       440_000),
    ],
    "🚶 Опора и движение": [
        ("TROST",       "Трость",                        200_000),
        ("HODUNKI",     "Ходунки",                       550_000),
        ("KOSTYLI",     "Костыли",                       280_000),
        ("SHINA_FREIKA","Шина Фрейка",                   285_000),
    ],
    "💆 Массаж и восстановление": [
        ("ORT_KRUG",   "Ортопедический круг",             40_000),
        ("ORT_KOVRIK", "Ортопедический коврик",          250_000),
        ("KUZNECOV",   "Аппликатор Кузнецова",           380_000),
        ("MASSAJ_VAL", "Массажные валики",               200_000),
    ],
}

# Плоский словарь: код → (название, цена)
PRODUCTS: dict[str, tuple[str, int]] = {}
for _items in CATEGORIES.values():
    for _code, _name, _price in _items:
        PRODUCTS[_code] = (_name, _price)

HOURS_OPTIONS = ["1 час","2 часа","3 часа","4 часа","5 часов","6 часов","7 часов","8 часов"]

def fmt(amount: int) -> str:
    """Форматирует сумму: 280000 → 280 000 сум"""
    return f"{amount:,}".replace(",", " ") + " сум"

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
            is_active  INTEGER DEFAULT 1
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
            FOREIGN KEY (doctor_id) REFERENCES doctors(id)
        );
        """)

def unique_code():
    with db() as con:
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not con.execute("SELECT 1 FROM doctors WHERE code=?", (code,)).fetchone():
                return code

def unique_ref_number():
    with db() as con:
        while True:
            num = "ORD-" + ''.join(random.choices(string.digits, k=6))
            if not con.execute("SELECT 1 FROM referrals WHERE ref_number=?", (num,)).fetchone():
                return num

def doctor_by_tg(tg_id):
    with db() as con:
        return con.execute("SELECT * FROM doctors WHERE tg_id=?", (tg_id,)).fetchone()
# cols: 0=id 1=tg_id 2=full_name 3=clinic 4=phone 5=code 6=created_at 7=is_active

def doctor_stats(doctor_id):
    with db() as con:
        return con.execute("""
            SELECT COUNT(*),
                   SUM(CASE WHEN status='bought' THEN 1 ELSE 0 END),
                   COALESCE(SUM(bonus),0)
            FROM referrals WHERE doctor_id=?
        """, (doctor_id,)).fetchone()

def all_doctors_ranked():
    with db() as con:
        return con.execute("""
            SELECT d.id, d.full_name, d.clinic, d.phone, d.code,
                   COUNT(r.id) AS total,
                   SUM(CASE WHEN r.status='bought' THEN 1 ELSE 0 END) AS bought,
                   COALESCE(SUM(r.bonus),0) AS bonus
            FROM doctors d
            LEFT JOIN referrals r ON r.doctor_id=d.id
            WHERE d.is_active=1
            GROUP BY d.id ORDER BY bonus DESC
        """).fetchall()

def pending_referrals():
    with db() as con:
        return con.execute("""
            SELECT r.id, d.full_name, d.clinic, d.phone,
                   r.items_json, r.total_price, r.expected_in, r.sent_at, r.ref_number
            FROM referrals r JOIN doctors d ON d.id=r.doctor_id
            WHERE r.status='pending' ORDER BY r.sent_at DESC
        """).fetchall()

def global_stats():
    with db() as con:
        docs = con.execute("SELECT COUNT(*) FROM doctors WHERE is_active=1").fetchone()[0]
        refs = con.execute("""
            SELECT COUNT(*),
                   SUM(CASE WHEN status='bought'  THEN 1 ELSE 0 END),
                   SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END),
                   COALESCE(SUM(bonus),0)
            FROM referrals
        """).fetchone()
        today = datetime.now().strftime("%Y-%m-%d")
        today_r = con.execute("""
            SELECT COUNT(*), SUM(CASE WHEN status='bought' THEN 1 ELSE 0 END)
            FROM referrals WHERE sent_at LIKE ?
        """, (f"{today}%",)).fetchone()
    return docs, refs, today_r

# ─────────────────────────────────────────────
# ПАРСИНГ КОРЗИНЫ
# ─────────────────────────────────────────────
import json

def cart_to_text(items_json: str) -> str:
    items = json.loads(items_json)
    lines = []
    total = 0
    for code, qty in items:
        name, price = PRODUCTS.get(code, (code, 0))
        subtotal = price * qty
        total += subtotal
        lines.append(f"  • {name} x{qty} = {fmt(subtotal)}")
    lines.append(f"\n💵 Итого: {fmt(total)}")
    return "\n".join(lines)

def cart_total(items_json: str) -> int:
    items = json.loads(items_json)
    return sum(PRODUCTS.get(code, ("", 0))[1] * qty for code, qty in items)

# ─────────────────────────────────────────────
# КЛАВИАТУРЫ
# ─────────────────────────────────────────────
def kb_admin():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="⏳ Ожидаемые клиенты"), KeyboardButton(text="👨‍⚕️ Все врачи")],
        [KeyboardButton(text="📊 Статистика"),         KeyboardButton(text="📋 История")],
    ])

def kb_doctor():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="📤 Отправить клиента")],
        [KeyboardButton(text="📊 Мои показатели"), KeyboardButton(text="🕐 Мои направления")],
    ])

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
        [KeyboardButton(text=h) for h in HOURS_OPTIONS[4:]],
        [KeyboardButton(text="◀️ Назад")],
    ])

def inline_sale(ref_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Купил",    callback_data=f"bought:{ref_id}"),
        InlineKeyboardButton(text="❌ Не купил", callback_data=f"nobuy:{ref_id}"),
    ]])

def inline_confirm(ref_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить продажу", callback_data=f"confirm:{ref_id}"),
    ]])

# ─────────────────────────────────────────────
# FSM
# ─────────────────────────────────────────────
class RegDoctor(StatesGroup):
    last_name   = State()
    first_name  = State()
    patronymic  = State()
    clinic      = State()
    phone       = State()

class SendClient(StatesGroup):
    shopping  = State()   # выбор товаров (корзина)
    hours     = State()
    confirm   = State()

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
    if uid in ADMIN_IDS:
        await msg.answer("👋 <b>Добро пожаловать, администратор OrthoShop!</b>", reply_markup=kb_admin())
        return
    doc = doctor_by_tg(uid)
    if doc:
        total, bought, bonus = doctor_stats(doc[0])
        conv = round(bought/total*100) if total else 0
        await msg.answer(
            f"👋 С возвращением, <b>Dr. {doc[2]}</b>!\n"
            f"🏥 {doc[3]}  |  📱 {doc[4]}\n\n"
            f"📤 Направлений: <b>{total}</b>  ✅ Купили: <b>{bought}</b> ({conv}%)\n"
            f"💰 Бонусов накоплено: <b>{fmt(int(bonus))}</b>",
            reply_markup=kb_doctor()
        )
    else:
        await msg.answer(
            "👋 <b>Добро пожаловать в OrthoShop!</b>\n\n"
            "Введите вашу <b>Фамилию</b>:"
        )
        await state.set_state(RegDoctor.last_name)

# ── Регистрация ───────────────────────────────
@dp.message(RegDoctor.last_name)
async def reg_last_name(msg: types.Message, state: FSMContext):
    val = msg.text.strip()
    if len(val) < 2 or ' ' in val:
        await msg.answer("❌ <b>Введите только Фамилию</b> (одно слово)\n\nНапример: <b>Иванов</b>")
        return
    await state.update_data(last_name=val)
    await msg.answer("✅ Фамилия принята.\n\nТеперь введите ваше <b>Имя</b>:")
    await state.set_state(RegDoctor.first_name)

@dp.message(RegDoctor.first_name)
async def reg_first_name(msg: types.Message, state: FSMContext):
    val = msg.text.strip()
    if len(val) < 2 or ' ' in val:
        await msg.answer("❌ <b>Введите только Имя</b> (одно слово)\n\nНапример: <b>Иван</b>")
        return
    await state.update_data(first_name=val)
    await msg.answer("✅ Имя принято.\n\nТеперь введите ваше <b>Отчество</b>:")
    await state.set_state(RegDoctor.patronymic)

@dp.message(RegDoctor.patronymic)
async def reg_patronymic(msg: types.Message, state: FSMContext):
    val = msg.text.strip()
    if len(val) < 2 or ' ' in val:
        await msg.answer("❌ <b>Введите только Отчество</b> (одно слово)\n\nНапример: <b>Иванович</b>\n\nБез отчества регистрация невозможна.")
        return
    await state.update_data(patronymic=val)
    await msg.answer("✅ Отчество принято.\n\n🏥 Название клиники или больницы:")
    await state.set_state(RegDoctor.clinic)

@dp.message(RegDoctor.clinic)
async def reg_clinic(msg: types.Message, state: FSMContext):
    await state.update_data(clinic=msg.text.strip())
    await msg.answer(
        "📱 Ваш номер телефона:\n\n"
        "<i>Можно написать полный номер или последние 4 цифры</i>"
    )
    await state.set_state(RegDoctor.phone)

@dp.message(RegDoctor.phone)
async def reg_phone(msg: types.Message, state: FSMContext):
    phone  = msg.text.strip()
    digits = ''.join(c for c in phone if c.isdigit())
    if len(digits) < 4:
        await msg.answer(
            "❌ <b>Введите хотя бы последние 4 цифры номера</b>\n\n"
            "Например: <b>+998 97 135 68 68</b> или просто <b>6868</b>\n\n"
            "Без телефона регистрация невозможна."
        )
        return
    data      = await state.get_data()
    full_name = f"{data['last_name']} {data['first_name']} {data['patronymic']}"
    code      = unique_code()
    with db() as con:
        con.execute(
            "INSERT INTO doctors (tg_id,full_name,clinic,phone,code) VALUES (?,?,?,?,?)",
            (msg.from_user.id, full_name, data["clinic"], phone, code)
        )
    await state.clear()
    await msg.answer(
        f"✅ <b>Регистрация завершена!</b>\n\n"
        f"👤 {full_name}\n"
        f"🏥 {data['clinic']}\n"
        f"📱 {phone}\n\n"
        f"За каждую покупку клиента — <b>{BONUS_PCT:.0f}% бонус</b> вам 💰",
        reply_markup=kb_doctor()
    )
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(aid,
                f"🆕 <b>Новый врач зарегистрировался!</b>\n"
                f"👤 {full_name}\n🏥 {data['clinic']}\n📱 {phone}"
            )
        except: pass

# ── Отправить клиента — корзина ───────────────
@dp.message(F.text == "📤 Отправить клиента")
async def send_start(msg: types.Message, state: FSMContext):
    doc = doctor_by_tg(msg.from_user.id)
    if not doc:
        await msg.answer("❌ Сначала зарегистрируйтесь — /start"); return
    await state.update_data(
        doctor_id=doc[0], doctor_name=doc[2], doctor_tg=msg.from_user.id,
        cart=[], current_cat=None
    )
    await msg.answer(
        "🛒 <b>Добавьте товары в корзину</b>\n\n"
        "Выберите категорию → выберите товар → добавится в корзину\n"
        "Можно добавить несколько товаров!\n\n"
        "Когда готово — нажмите <b>✅ Отправить направление</b>",
        reply_markup=kb_categories()
    )
    await state.set_state(SendClient.shopping)

@dp.message(SendClient.shopping)
async def shopping_handler(msg: types.Message, state: FSMContext):
    text = msg.text
    data = await state.get_data()
    cart: list = data.get("cart", [])

    # ── Отмена ──
    if text == "◀️ Отмена":
        await state.clear()
        await msg.answer("Отменено.", reply_markup=kb_doctor()); return

    # ── Назад к категориям ──
    if text == "◀️ К категориям":
        await state.update_data(current_cat=None)
        await msg.answer("📦 Выберите категорию:", reply_markup=kb_categories()); return

    # ── Показать корзину ──
    if text == "🛒 Корзина":
        if not cart:
            await msg.answer("🛒 Корзина пуста. Добавьте товары."); return
        lines = ["🛒 <b>Ваша корзина:</b>\n"]
        total = 0
        for code, qty in cart:
            name, price = PRODUCTS.get(code, (code, 0))
            sub = price * qty
            total += sub
            lines.append(f"• {name} x{qty} = {fmt(sub)}")
        lines.append(f"\n💵 <b>Итого: {fmt(total)}</b>")
        await msg.answer("\n".join(lines)); return

    # ── Отправить направление ──
    if text == "✅ Отправить направление":
        if not cart:
            await msg.answer("🛒 Корзина пуста! Добавьте хотя бы один товар."); return
        lines = ["✅ <b>Товары в направлении:</b>\n"]
        total = 0
        for code, qty in cart:
            name, price = PRODUCTS.get(code, (code, 0))
            sub = price * qty
            total += sub
            lines.append(f"• {name} x{qty} = {fmt(sub)}")
        lines.append(f"\n💵 <b>Итого: {fmt(total)}</b>")
        lines.append("\n⏰ <b>Через сколько придёт клиент?</b>")
        await msg.answer("\n".join(lines), reply_markup=kb_hours())
        await state.set_state(SendClient.hours); return

    # ── Выбор категории ──
    if text in CATEGORIES:
        await state.update_data(current_cat=text)
        count = sum(q for _, q in cart)
        cart_hint = f"🛒 {count} товаров в корзине\n\n" if count else ""
        await msg.answer(
            f"{cart_hint}📋 <b>{text}</b>\n\nВыберите товар:",
            reply_markup=kb_products(text)
        ); return

    # ── Выбор товара (формат "Название — цена") ──
    current_cat = data.get("current_cat")
    if current_cat and current_cat in CATEGORIES:
        for code, name, price in CATEGORIES[current_cat]:
            btn_text = f"{name} — {fmt(price)}"
            if text == btn_text:
                # Добавить в корзину
                found = False
                for i, (c, q) in enumerate(cart):
                    if c == code:
                        cart[i] = (c, q+1)
                        found = True; break
                if not found:
                    cart.append((code, 1))
                await state.update_data(cart=cart)
                total = sum(PRODUCTS.get(c,("",0))[1]*q for c,q in cart)
                await msg.answer(
                    f"✅ <b>{name}</b> добавлен в корзину!\n"
                    f"🛒 Товаров в корзине: <b>{sum(q for _,q in cart)}</b>  |  💵 {fmt(total)}\n\n"
                    f"Добавьте ещё или нажмите <b>✅ Отправить направление</b>"
                ); return

    await msg.answer("Выберите из списка:")

# ── Время прихода ─────────────────────────────
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
        name, price = PRODUCTS.get(code, (code, 0))
        lines.append(f"• {name} x{qty} = {fmt(price*qty)}")
    lines.append(f"\n💵 <b>Итого: {fmt(total)}</b>")
    lines.append(f"⏰ Клиент придёт через: <b>{msg.text}</b>")

    await msg.answer(
        "\n".join(lines),
        reply_markup=ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton(text="✅ Подтвердить")],
            [KeyboardButton(text="◀️ Назад")],
        ])
    )
    await state.set_state(SendClient.confirm)

@dp.message(SendClient.confirm)
async def send_confirm(msg: types.Message, state: FSMContext):
    if msg.text == "◀️ Назад":
        await msg.answer("Выберите время:", reply_markup=kb_hours())
        await state.set_state(SendClient.hours); return
    if msg.text != "✅ Подтвердить": return

    data      = await state.get_data()
    cart      = data["cart"]
    hours     = data["hours"]
    items_json = json.dumps(cart)
    total     = sum(PRODUCTS.get(c,("",0))[1]*q for c,q in cart)
    ref_num   = unique_ref_number()
    sent_time = datetime.now().strftime("%d.%m.%Y %H:%M")

    with db() as con:
        cur = con.execute(
            "INSERT INTO referrals (doctor_id,items_json,total_price,expected_in,ref_number) VALUES (?,?,?,?,?)",
            (data["doctor_id"], items_json, total, hours, ref_num)
        )
        ref_id = cur.lastrowid

    await state.clear()

    # Текст для врача
    lines = [f"✅ <b>Направление отправлено!</b>\n",
             f"🔖 Номер: <b>{ref_num}</b>",
             f"📅 Время отправки: <b>{sent_time}</b>\n"]
    for code, qty in cart:
        name, price = PRODUCTS.get(code,(code,0))
        lines.append(f"• {name} x{qty}")
    lines.append(f"\n💵 {fmt(total)}")
    lines.append(f"⏰ Клиент придёт через {hours}")
    lines.append(f"\nКогда клиент купит — придёт уведомление с датой и временем 💰")
    await msg.answer("\n".join(lines), reply_markup=kb_doctor())

    # Текст для администратора
    adm_lines = [f"🔔 <b>Новый клиент от врача!</b>\n",
                 f"👨‍⚕️ <b>{data['doctor_name']}</b>",
                 f"⏰ Ожидается через: <b>{hours}</b>",
                 f"🔖 Номер: <b>{ref_num}</b>",
                 f"📅 Отправлено: <b>{sent_time}</b>\n",
                 f"<b>Товары:</b>"]
    for code, qty in cart:
        name, price = PRODUCTS.get(code,(code,0))
        adm_lines.append(f"• {name} x{qty} = {fmt(price*qty)}")
    adm_lines.append(f"\n💵 <b>Итого: {fmt(total)}</b>")
    adm_lines.append(f"\nОтметьте результат когда клиент придёт:")

    for aid in ADMIN_IDS:
        try:
            await bot.send_message(aid, "\n".join(adm_lines), reply_markup=inline_sale(ref_id))
        except: pass

# ── Купил ─────────────────────────────────────
@dp.callback_query(F.data.startswith("bought:"))
async def cb_bought(call: types.CallbackQuery):
    ref_id = int(call.data.split(":")[1])
    with db() as con:
        ref = con.execute(
            "SELECT r.*,d.full_name,d.tg_id,d.phone FROM referrals r JOIN doctors d ON d.id=r.doctor_id WHERE r.id=?",
            (ref_id,)
        ).fetchone()
    if not ref or ref[5] != "pending":
        await call.answer("Уже обработано"); return

    bought_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    bonus       = round(ref[3] * BONUS_PCT / 100)

    with db() as con:
        con.execute(
            "UPDATE referrals SET status='bought', bought_at=?, bonus=? WHERE id=?",
            (bought_time, bonus, ref_id)
        )

    cart_text = cart_to_text(ref[2])

    # Сообщение админу
    await call.message.edit_text(
        f"✅ <b>Продажа подтверждена!</b>\n\n"
        f"👨‍⚕️ {ref[10]}  |  📱 {ref[12]}\n"
        f"🔖 {ref[9]}\n\n"
        f"{cart_text}\n\n"
        f"📅 <b>Дата и время покупки: {bought_time}</b>\n"
        f"💰 Бонус врача: <b>{fmt(bonus)}</b>"
    )
    await call.answer("✅ Записано!")

    # Уведомление врачу с доказательством
    _, bought_cnt, total_bonus = doctor_stats(ref[1])
    if ref[11]:
        try:
            await bot.send_message(
                ref[11],
                f"🎉 <b>Ваш клиент совершил покупку!</b>\n\n"
                f"🔖 Номер направления: <b>{ref[9]}</b>\n"
                f"📅 <b>Дата и время покупки: {bought_time}</b>\n\n"
                f"{cart_to_text(ref[2])}\n\n"
                f"💰 Ваш бонус: <b>{fmt(bonus)}</b>\n"
                f"💰 Всего накоплено: <b>{fmt(int(total_bonus))}</b>"
            )
        except: pass

# ── Не купил ──────────────────────────────────
@dp.callback_query(F.data.startswith("nobuy:"))
async def cb_nobuy(call: types.CallbackQuery):
    ref_id = int(call.data.split(":")[1])
    with db() as con:
        ref = con.execute(
            "SELECT r.*,d.full_name,d.tg_id,d.phone FROM referrals r JOIN doctors d ON d.id=r.doctor_id WHERE r.id=?",
            (ref_id,)
        ).fetchone()
        if ref and ref[5] == "pending":
            con.execute(
                "UPDATE referrals SET status='notbought', bought_at=datetime('now','localtime') WHERE id=?",
                (ref_id,)
            )
    if ref:
        nobuy_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        await call.message.edit_text(
            f"❌ <b>Клиент не купил</b>\n\n"
            f"👨‍⚕️ {ref[10]}  |  📱 {ref[12]}\n"
            f"🔖 {ref[9]}\n"
            f"📅 {nobuy_time}\n\n"
            f"{cart_to_text(ref[2])}"
        )
        if ref[11]:
            try:
                await bot.send_message(ref[11],
                    f"📊 <b>Отчёт по направлению</b>\n\n"
                    f"🔖 {ref[9]}\n"
                    f"📅 {nobuy_time}\n\n"
                    f"{cart_to_text(ref[2])}\n\n"
                    f"❌ Клиент не приобрёл товар\n"
                    f"Бонус не начислен."
                )
            except: pass
    await call.answer()

# ── Кнопки врача ──────────────────────────────
@dp.message(F.text == "📊 Мои показатели")
async def doc_stats(msg: types.Message):
    doc = doctor_by_tg(msg.from_user.id)
    if not doc: return
    total, bought, bonus = doctor_stats(doc[0])
    notbought = (total or 0) - (bought or 0)
    conv = round((bought or 0)/total*100) if total else 0
    await msg.answer(
        f"📊 <b>Ваша статистика</b>\n\n"
        f"👤 {doc[2]}\n🏥 {doc[3]}\n📱 {doc[4]}\n\n"
        f"📤 Направлений: <b>{total}</b>\n"
        f"✅ Купили: <b>{bought or 0}</b>  ❌ Не купили: <b>{notbought}</b>\n"
        f"📈 Конверсия: <b>{conv}%</b>\n\n"
        f"💰 Бонусов накоплено: <b>{fmt(int(bonus or 0))}</b>"
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
    sm = {"pending":"⏳ Ожидается","bought":"✅ Купил","notbought":"❌ Не купил"}
    lines = ["🕐 <b>Последние направления:</b>\n"]
    for items_json, hours, status, bonus, sent_at, bought_at, ref_num in refs:
        st = sm.get(status,"?")
        b  = f"\n   💰 Бонус: {fmt(int(bonus))}" if status=="bought" else ""
        dt = f"\n   📅 Куплено: {bought_at}" if status=="bought" and bought_at else ""
        items = json.loads(items_json)
        names = ", ".join(PRODUCTS.get(c,(c,0))[0] for c,_ in items)
        lines.append(f"{st} <b>{ref_num}</b>\n   📦 {names}{b}{dt}\n   🕐 {sent_at[:16]}\n")
    await msg.answer("\n".join(lines))

# ── Кнопки администратора ─────────────────────
@dp.message(F.text == "⏳ Ожидаемые клиенты")
async def admin_pending(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    refs = pending_referrals()
    if not refs:
        await msg.answer("📭 Нет ожидаемых клиентов."); return
    await msg.answer(f"⏳ <b>Ожидаемых клиентов: {len(refs)}</b>")
    for ref_id, name, clinic, phone, items_json, total, hours, sent_at, ref_num in refs:
        await msg.answer(
            f"👨‍⚕️ <b>{name}</b>\n🏥 {clinic}  |  📱 {phone}\n"
            f"🔖 {ref_num}\n"
            f"⏰ Через {hours}  |  🕐 {sent_at[11:16]}\n\n"
            f"{cart_to_text(items_json)}",
            reply_markup=inline_sale(ref_id)
        )

@dp.message(F.text == "👨‍⚕️ Все врачи")
async def admin_doctors(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    doctors = all_doctors_ranked()
    if not doctors:
        await msg.answer("📭 Врачей пока нет."); return
    lines = ["👨‍⚕️ <b>Рейтинг врачей:</b>\n"]
    for i, (did, name, clinic, phone, code, total, bought, bonus) in enumerate(doctors, 1):
        conv = round((bought or 0)/total*100) if total else 0
        lines.append(
            f"{i}. <b>{name}</b>\n"
            f"   🏥 {clinic}  |  📱 {phone}\n"
            f"   📤 {total} | ✅ {bought or 0} ({conv}%) | 💰 <b>{fmt(int(bonus or 0))}</b>\n"
        )
    text = "\n".join(lines)
    for chunk in [text[i:i+4000] for i in range(0,len(text),4000)]:
        await msg.answer(chunk)

@dp.message(F.text == "📊 Статистика")
async def admin_stats(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
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
    if msg.from_user.id not in ADMIN_IDS: return
    with db() as con:
        refs = con.execute("""
            SELECT d.full_name, d.phone, r.items_json, r.status,
                   r.bonus, r.sent_at, r.bought_at, r.ref_number
            FROM referrals r JOIN doctors d ON d.id=r.doctor_id
            ORDER BY r.sent_at DESC LIMIT 15
        """).fetchall()
    if not refs:
        await msg.answer("📭 Истории нет."); return
    sm = {"pending":"⏳","bought":"✅","notbought":"❌"}
    lines = ["📋 <b>Последние 15 направлений:</b>\n"]
    for name, phone, items_json, status, bonus, sent_at, bought_at, ref_num in refs:
        items = json.loads(items_json)
        names = ", ".join(PRODUCTS.get(c,(c,0))[0] for c,_ in items)
        b  = f" | 💰{fmt(int(bonus))}" if status=="bought" else ""
        dt = f"\n   📅 {bought_at}" if status=="bought" and bought_at else ""
        lines.append(
            f"{sm.get(status,'?')} <b>{name}</b> ({phone})\n"
            f"   🔖 {ref_num}{b}\n"
            f"   📦 {names}{dt}\n"
            f"   🕐 {sent_at[:16]}\n"
        )
    await msg.answer("\n".join(lines))

# ─────────────────────────────────────────────
async def main():
    init_db()
    print("✅ OrthoTrack v3 запущен!")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
