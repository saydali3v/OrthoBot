"""
OrthoTrack Bot v5 — полная версия
"""
import asyncio, sqlite3, random, string, os, json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
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
    FSInputFile
)

load_dotenv()

BOT_TOKEN     = os.getenv("BOT_TOKEN", "")
SENIOR_ADMINS = [int(x) for x in os.getenv("SENIOR_ADMINS", "127036820").split(",") if x.strip()]
STAFF_IDS     = [int(x) for x in os.getenv("STAFF_IDS", "").split(",") if x.strip()]
BONUS_PCT     = float(os.getenv("BONUS_PCT", "18"))
DB_PATH       = "orthotrack.db"
TZ            = ZoneInfo("Asia/Tashkent")

def now_tashkent():
    return datetime.now(TZ).strftime("%d.%m.%Y %H:%M:%S")

def is_senior(uid): return uid in SENIOR_ADMINS
def is_staff(uid):  return uid in STAFF_IDS
def is_admin(uid):  return is_senior(uid) or is_staff(uid)

# ─────────────────────────────────────────────
# КАТАЛОГ
# ─────────────────────────────────────────────
CATEGORIES = {
    "🦴 Позвоночник и спина": [
        ("AR540","Корсет грудопоясничный AR 540",480_000),
        ("AR542","Корсет поясничный мягкий AR 542",225_000),
        ("AR544","Корсет грудной AR 544",330_000),
        ("AR573","Корсет поясничный AR 573",300_000),
        ("AR541","Послеоперационный бандаж AR 541",250_000),
        ("AR532","Ортопедическая подушка AR 532",110_000),
        ("ORT_PODUSHKA","Ортопедическая подушка",350_000),
    ],
    "🧣 Шея": [
        ("AR546","Воротник шейный AR 546",195_000),
        ("AR545","Воротник детский AR 545",120_000),
        ("FILADELFIA","Воротник Филадельфия",300_000),
        ("NADUV","Надувной воротник",185_000),
    ],
    "🦵 Колено и нога": [
        ("AR556","Ортез на колено AR 556",280_000),
        ("AR575SH","Ортез колено с шарнирами AR 575",385_000),
        ("AR575ST","Ортез колено со стержнями AR 575",385_000),
        ("REG_KOLENO","Регулируемый ортез на колено",850_000),
        ("AR562","Голеностопный бандаж AR 562",290_000),
        ("ROMWALKER","Голеностопный ортез ROM Walker",1_500_000),
        ("DEROT","Деротационный ортез",655_000),
        ("DEROT_DET","Деротационный ортез (детский)",655_000),
    ],
    "🖐 Рука и запястье": [
        ("AR551","Ортез на запястье AR 551",300_000),
        ("AR552","Ортез на запястье AR 552",360_000),
        ("AR560","Ортез на руку AR 560",110_000),
        ("AR579","Ортез на руку AR 579",200_000),
        ("AR534","Ортез на руку AR 534",235_000),
    ],
    "🦶 Стопа": [
        ("STELNKI_ORT","Ортопедические стельки",370_000),
        ("STELNKI_PLSK","Стельки от плоскостопия",50_000),
        ("AR604","Стельки AR 604",200_000),
        ("NOSOCHKI","Носочки от плоскостопия",70_000),
        ("VALGUS_MAN","Вальгусная манжетка",70_000),
        ("VALGUS_RASP","Вальгусная распорка",90_000),
        ("FIKSATOR","Фиксатор большого пальца",100_000),
        ("OBUV_GIPS","Обувь для гипса",400_000),
        ("OBUV580","Обувь 580",650_000),
    ],
    "🤰 Для беременных": [
        ("BAND_BERE","Бандаж для беременных",250_000),
        ("BAND_GRUD","Бандаж для грудины",325_000),
        ("BAND_TAZ","Тазобедренный бандаж",650_000),
    ],
    "🧦 Компрессия": [
        ("COMP_CHULKI","Компрессионные чулки",430_000),
        ("COMP_KOLT","Компрессионные колготки",440_000),
    ],
    "🚶 Опора и движение": [
        ("TROST","Трость",200_000),
        ("HODUNKI","Ходунки",550_000),
        ("KOSTYLI","Костыли",280_000),
        ("SHINA_FREIKA","Шина Фрейка",285_000),
    ],
    "💆 Массаж и восстановление": [
        ("ORT_KRUG","Ортопедический круг",40_000),
        ("ORT_KOVRIK","Ортопедический коврик",250_000),
        ("KUZNECOV","Аппликатор Кузнецова",380_000),
        ("MASSAJ_VAL","Массажные валики",200_000),
    ],
}

PRODUCTS: dict[str, tuple[str, int]] = {}
for _items in CATEGORIES.values():
    for _code, _name, _price in _items:
        PRODUCTS[_code] = (_name, _price)

HOURS_OPTIONS = ["1 час","2 часа","3 часа","4 часа","5 часов","6 часов","7 часов","8 часов","Завтра","На этой неделе"]

def fmt(amount: int) -> str:
    return f"{int(amount):,}".replace(",", " ") + " сум"

def cart_to_text(items_json: str, show_prices: bool = True) -> str:
    items = json.loads(items_json)
    lines = []
    total = 0
    for code, qty in items:
        name, base_price = PRODUCTS.get(code, (code, 0))
        price = get_price(code)
        sub   = price * qty
        total += sub
        if show_prices:
            lines.append(f"  • {name} x{qty} = {fmt(sub)}")
        else:
            lines.append(f"  • {name} x{qty}")
    if show_prices:
        lines.append(f"\n💵 Итого: {fmt(total)}")
    return "\n".join(lines)

# ─────────────────────────────────────────────
# БД
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
            arrived_at   TEXT,
            bought_at    TEXT,
            bonus        REAL DEFAULT 0,
            ref_number   TEXT UNIQUE NOT NULL,
            confirmed_by INTEGER,
            notified     INTEGER DEFAULT 0,
            FOREIGN KEY (doctor_id) REFERENCES doctors(id)
        );
        CREATE TABLE IF NOT EXISTS payments (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER NOT NULL,
            amount    REAL NOT NULL,
            paid_at   TEXT DEFAULT (datetime('now','localtime')),
            paid_by   INTEGER,
            note      TEXT,
            FOREIGN KEY (doctor_id) REFERENCES doctors(id)
        );
        CREATE TABLE IF NOT EXISTS visits (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            visited_at TEXT DEFAULT (datetime('now','localtime')),
            added_by   INTEGER
        );
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS custom_products (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            code       TEXT UNIQUE NOT NULL,
            name       TEXT NOT NULL,
            category   TEXT NOT NULL,
            price      INTEGER NOT NULL,
            bonus_pct  REAL DEFAULT 0,
            is_active  INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        """)
    # Миграции
    with db() as con:
        try:
            con.execute("ALTER TABLE referrals ADD COLUMN arrived_at TEXT")
        except: pass
        try:
            con.execute("ALTER TABLE referrals ADD COLUMN notified INTEGER DEFAULT 0")
        except: pass        # Начальные настройки
        con.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('bonus_pct','18')")
        # Начальные цены из каталога
        for code, name, price in [item for items in CATEGORIES.values() for item in items]:
            con.execute(
                "INSERT OR IGNORE INTO settings (key,value) VALUES (?,?)",
                (f"price_{code}", str(price))
            )

def get_custom_products():
    """Возвращает все активные кастомные товары"""
    with db() as con:
        return con.execute(
            "SELECT code, name, category, price, bonus_pct FROM custom_products WHERE is_active=1"
        ).fetchall()

def get_all_categories():
    """Возвращает CATEGORIES + кастомные товары"""
    result = {k: list(v) for k, v in CATEGORIES.items()}
    for code, name, category, price, bonus_pct in get_custom_products():
        if category not in result:
            result[category] = []
        if not any(c == code for c, n, p in result[category]):
            result[category].append((code, name, price))
    return result

def get_all_products():
    """Возвращает PRODUCTS + кастомные товары"""
    result = dict(PRODUCTS)
    for code, name, category, price, bonus_pct in get_custom_products():
        result[code] = (name, price)
    return result

def get_product_bonus_pct(code):
    """Возвращает индивидуальный % бонуса для товара или общий"""
    with db() as con:
        row = con.execute(
            "SELECT bonus_pct FROM custom_products WHERE code=? AND bonus_pct > 0",
            (code,)
        ).fetchone()
    return row[0] if row else get_bonus_pct()

def get_setting(key, default=None):
    with db() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else default

def set_setting(key, value):
    with db() as con:
        con.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, str(value)))

def get_bonus_pct():
    return float(get_setting("bonus_pct", "18"))

def get_price(code):
    val = get_setting(f"price_{code}")
    if val: return int(val)
    for items in CATEGORIES.values():
        for c, n, p in items:
            if c == code: return p
    return 0

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
        paid = con.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE doctor_id=?",
                           (doctor_id,)).fetchone()[0]
    return r[0] or 0, r[1] or 0, r[2] or 0, paid or 0

def all_doctors():
    with db() as con:
        rows = con.execute("""
            SELECT d.id, d.full_name, d.clinic, d.phone,
                   COUNT(r.id),
                   SUM(CASE WHEN r.status='bought' THEN 1 ELSE 0 END),
                   COALESCE(SUM(CASE WHEN r.status='bought' THEN r.bonus ELSE 0 END),0)
            FROM doctors d
            LEFT JOIN referrals r ON r.doctor_id=d.id
            WHERE d.is_active=1
            GROUP BY d.id
        """).fetchall()
        result = []
        for row in rows:
            paid = con.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE doctor_id=?",
                               (row[0],)).fetchone()[0]
            result.append((*row, paid or 0))
    result.sort(key=lambda x: x[6]-x[7], reverse=True)
    return result

def pending_refs():
    with db() as con:
        return con.execute("""
            SELECT r.id, d.full_name, d.clinic, d.phone,
                   r.items_json, r.total_price, r.expected_in, r.sent_at, r.ref_number, d.id
            FROM referrals r JOIN doctors d ON d.id=r.doctor_id
            WHERE r.status='pending' ORDER BY r.sent_at ASC
        """).fetchall()

def today_pending_refs():
    today = datetime.now().strftime("%Y-%m-%d")
    with db() as con:
        return con.execute("""
            SELECT r.id, d.full_name, d.clinic, d.phone,
                   r.items_json, r.total_price, r.expected_in, r.sent_at, r.ref_number, d.id
            FROM referrals r JOIN doctors d ON d.id=r.doctor_id
            WHERE r.status='pending' AND r.sent_at LIKE ?
            ORDER BY r.sent_at ASC
        """, (f"{today}%",)).fetchall()

def search_by_clinic(query):
    with db() as con:
        return con.execute("""
            SELECT r.id, d.full_name, d.clinic, d.phone,
                   r.items_json, r.total_price, r.expected_in, r.sent_at, r.ref_number, d.id
            FROM referrals r JOIN doctors d ON d.id=r.doctor_id
            WHERE r.status='pending' AND LOWER(d.clinic) LIKE LOWER(?)
            ORDER BY r.sent_at ASC
        """, (f"%{query}%",)).fetchall()

def global_stats():
    with db() as con:
        docs  = con.execute("SELECT COUNT(*) FROM doctors WHERE is_active=1").fetchone()[0]
        refs  = con.execute("""
            SELECT COUNT(*),
                   SUM(CASE WHEN status='bought' THEN 1 ELSE 0 END),
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

def weekly_top():
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    with db() as con:
        return con.execute("""
            SELECT d.full_name, d.clinic,
                   COUNT(r.id) AS total,
                   SUM(CASE WHEN r.status='bought' THEN 1 ELSE 0 END) AS bought,
                   COALESCE(SUM(CASE WHEN r.status='bought' THEN r.bonus ELSE 0 END),0) AS bonus
            FROM referrals r JOIN doctors d ON d.id=r.doctor_id
            WHERE r.sent_at >= ?
            GROUP BY d.id ORDER BY bought DESC LIMIT 10
        """, (week_ago,)).fetchall()

def doctor_month_stats(doctor_id):
    month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    with db() as con:
        return con.execute("""
            SELECT COUNT(*),
                   SUM(CASE WHEN status='bought' THEN 1 ELSE 0 END),
                   COALESCE(SUM(CASE WHEN status='bought' THEN bonus ELSE 0 END),0)
            FROM referrals WHERE doctor_id=? AND sent_at >= ?
        """, (doctor_id, month_start)).fetchone()

def doctor_today_stats(doctor_id):
    today = datetime.now().strftime("%Y-%m-%d")
    with db() as con:
        return con.execute("""
            SELECT COUNT(*),
                   SUM(CASE WHEN status='bought' THEN 1 ELSE 0 END),
                   COALESCE(SUM(CASE WHEN status='bought' THEN bonus ELSE 0 END),0)
            FROM referrals WHERE doctor_id=? AND sent_at LIKE ?
        """, (doctor_id, f"{today}%")).fetchone()

def doctor_payments_history(doctor_id):
    with db() as con:
        return con.execute("""
            SELECT amount, paid_at, note FROM payments
            WHERE doctor_id=? ORDER BY paid_at DESC LIMIT 10
        """, (doctor_id,)).fetchall()

def doctor_ranking(doctor_id):
    with db() as con:
        all_ids = con.execute("""
            SELECT doctor_id, SUM(CASE WHEN status='bought' THEN 1 ELSE 0 END) AS cnt
            FROM referrals GROUP BY doctor_id ORDER BY cnt DESC
        """).fetchall()
    for i, (did, _) in enumerate(all_ids, 1):
        if did == doctor_id:
            return i, len(all_ids)
    return None, None

# ─────────────────────────────────────────────
# КЛАВИАТУРЫ
# ─────────────────────────────────────────────
def kb_senior():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="⏳ Все ожидаемые"),    KeyboardButton(text="📅 Сегодня")],
        [KeyboardButton(text="🚶 Клиент пришёл"),    KeyboardButton(text="🔍 Поиск по клинике")],
        [KeyboardButton(text="👨‍⚕️ Все врачи"),        KeyboardButton(text="💰 Выплатить бонус")],
        [KeyboardButton(text="📊 Статистика"),        KeyboardButton(text="📈 Отчёт за неделю")],
        [KeyboardButton(text="🗒 Дневной лист"),      KeyboardButton(text="📋 История")],
        [KeyboardButton(text="⚙️ Настройки"),         KeyboardButton(text="💾 Бэкап")],
    ])

def kb_staff():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="🚶 Клиент пришёл"),    KeyboardButton(text="⏳ Все ожидаемые")],
        [KeyboardButton(text="📅 Сегодня"),           KeyboardButton(text="🔍 Поиск по клинике")],
        [KeyboardButton(text="📊 Статистика")],
    ])

def kb_doctor():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="📤 Отправить клиента")],
        [KeyboardButton(text="📊 Мои показатели"),  KeyboardButton(text="📅 За месяц")],
        [KeyboardButton(text="🕐 Мои направления"), KeyboardButton(text="💰 Мои бонусы")],
    ])

def main_kb(uid):
    if is_senior(uid): return kb_senior()
    if is_staff(uid):  return kb_staff()
    return kb_doctor()

def kb_categories():
    cats = get_all_categories()
    buttons = [[KeyboardButton(text=cat)] for cat in cats.keys()]
    buttons.append([KeyboardButton(text="🛒 Корзина"), KeyboardButton(text="✅ Отправить направление")])
    buttons.append([KeyboardButton(text="◀️ Отмена")])
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=buttons)

def kb_products_doctor(category):
    cats = get_all_categories()
    items = cats.get(category, [])
    buttons = [[KeyboardButton(text=name)] for _, name, price in items]
    buttons.append([KeyboardButton(text="🛒 Корзина"), KeyboardButton(text="✅ Отправить направление")])
    buttons.append([KeyboardButton(text="◀️ К категориям")])
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=buttons)

def kb_products(category):
    cats = get_all_categories()
    items = cats.get(category, [])
    buttons = [[KeyboardButton(text=f"{name} — {fmt(get_price(code))}")] for code, name, price in items]
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
                text=f"{name} — {fmt(int(balance))}",
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

class ConfirmBought(StatesGroup):
    waiting = State()  # ждём фото чека или ручной ввод времени

class SearchClinic(StatesGroup):
    query = State()

class Settings(StatesGroup):
    menu        = State()
    bonus_pct   = State()
    price_cat   = State()
    price_item  = State()
    price_value = State()
    new_prod_cat   = State()
    new_prod_name  = State()
    new_prod_price = State()
    new_prod_bonus = State()

class ConfirmBonus(StatesGroup):
    edit = State()

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
        conv = round(bought/total*100) if total else 0
        rank, total_docs = doctor_ranking(doc[0])
        await msg.answer(
            f"👋 С возвращением, <b>Dr. {doc[2]}</b>!\n"
            f"🏥 {doc[3]}  |  📱 {doc[4]}\n\n"
            f"📤 Направлений: <b>{total}</b>  ✅ Купили: <b>{bought}</b> ({conv}%)\n"
            f"🏆 Рейтинг: <b>{rank} из {total_docs}</b>\n\n"
            f"💰 Бонусы приходят каждый день в <b>22:00</b> 🌙",
            reply_markup=kb_doctor()
        )
    else:
        await msg.answer("👋 <b>Добро пожаловать!</b>\n\nВведите вашу <b>Фамилию</b>:")
        await state.set_state(RegDoctor.last_name)

# ── Регистрация ───────────────────────────────
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
        await msg.answer("❌ Введите только <b>Отчество</b> одним словом"); return
    await state.update_data(patronymic=val)
    await msg.answer("✅ Принято.\n\n🏥 Название клиники или больницы:")
    await state.set_state(RegDoctor.clinic)

@dp.message(RegDoctor.clinic)
async def reg_clinic(msg: types.Message, state: FSMContext):
    await state.update_data(clinic=msg.text.strip())
    await msg.answer("📱 Ваш номер телефона:")
    await state.set_state(RegDoctor.phone)

@dp.message(RegDoctor.phone)
async def reg_phone(msg: types.Message, state: FSMContext):
    phone  = msg.text.strip()
    digits = ''.join(c for c in phone if c.isdigit())
    if len(digits) < 4:
        await msg.answer("❌ Введите хотя бы <b>4 цифры</b> номера"); return
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
        f"Вы подключены к системе OrthoShop 💰\n"
        f"Бонусы приходят каждый день в <b>22:00</b> 🌙",
        reply_markup=kb_doctor()
    )
    for aid in SENIOR_ADMINS:
        try:
            await bot.send_message(aid, f"🆕 <b>Новый врач!</b>\n👤 {full_name}\n🏥 {data['clinic']}\n📱 {phone}")
        except: pass

# ── Корзина ───────────────────────────────────
@dp.message(F.text == "📤 Отправить клиента")
async def send_start(msg: types.Message, state: FSMContext):
    doc = doctor_by_tg(msg.from_user.id)
    if not doc:
        await msg.answer("❌ Сначала зарегистрируйтесь — /start"); return
    await state.update_data(doctor_id=doc[0], doctor_name=doc[2], doctor_tg=msg.from_user.id, cart=[], current_cat=None)
    await msg.answer("🛒 <b>Выберите категорию товара:</b>", reply_markup=kb_categories())
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
        is_doc = not is_admin(msg.from_user.id)
        lines = ["🛒 <b>Корзина:</b>\n"]
        total = 0
        for code, qty in cart:
            name, _ = PRODUCTS.get(code,(code,0))
            price = get_price(code)
            sub = price * qty
            total += sub
            lines.append(f"• {name} x{qty}" if is_doc else f"• {name} x{qty} = {fmt(sub)}")
        if not is_doc:
            lines.append(f"\n💵 <b>Итого: {fmt(total)}</b>")
        await msg.answer("\n".join(lines)); return

    if text == "✅ Отправить направление":
        if not cart:
            await msg.answer("🛒 Добавьте товар!"); return
        is_doc = not is_admin(msg.from_user.id)
        total = sum(get_price(c)*q for c,q in cart)
        lines = ["✅ <b>Товары:</b>\n"]
        for code, qty in cart:
            name, _ = PRODUCTS.get(code,(code,0))
            lines.append(f"• {name} x{qty}" if is_doc else f"• {name} x{qty} = {fmt(get_price(code)*qty)}")
        if not is_doc:
            lines.append(f"\n💵 <b>Итого: {fmt(total)}</b>")
        lines.append(f"\n⏰ <b>Через сколько придёт клиент?</b>")
        await msg.answer("\n".join(lines), reply_markup=kb_hours())
        await state.set_state(SendClient.hours); return

    all_cats = get_all_categories()
    if text in all_cats:
        await state.update_data(current_cat=text)
        cnt = sum(q for _,q in cart)
        hint = f"🛒 {cnt} товаров\n\n" if cnt else ""
        is_doc = not is_admin(msg.from_user.id)
        kb = kb_products_doctor(text) if is_doc else kb_products(text)
        await msg.answer(f"{hint}📋 <b>{text}</b>\nВыберите товар:", reply_markup=kb); return

    current_cat = data.get("current_cat")
    if current_cat and current_cat in all_cats:
        is_doc = not is_admin(msg.from_user.id)
        for code, name, price in all_cats[current_cat]:
            btn_text = name if is_doc else f"{name} — {fmt(get_price(code))}"
            if text == btn_text:
                found = False
                for i,(c,q) in enumerate(cart):
                    if c == code:
                        cart[i] = (c, q+1); found = True; break
                if not found: cart.append((code, 1))
                await state.update_data(cart=cart)
                total = sum(get_price(c)*q for c,q in cart)
                cnt_msg = f"🛒 {sum(q for _,q in cart)} товаров"
                if is_doc:
                    await msg.answer(
                        f"✅ <b>{name}</b> добавлен!\n{cnt_msg}\n\n"
                        f"Добавьте ещё или нажмите <b>✅ Отправить направление</b>"
                    )
                else:
                    await msg.answer(
                        f"✅ <b>{name}</b> добавлен!\n{cnt_msg} | 💵 {fmt(total)}\n\n"
                        f"Добавьте ещё или нажмите <b>✅ Отправить направление</b>"
                    )
                return
    await msg.answer("Выберите из списка:")

@dp.message(SendClient.hours)
async def send_hours(msg: types.Message, state: FSMContext):
    if msg.text == "◀️ Назад":
        await msg.answer("Выберите категорию:", reply_markup=kb_categories())
        await state.set_state(SendClient.shopping); return
    if msg.text not in HOURS_OPTIONS:
        await msg.answer("Выберите время из списка:"); return
    await state.update_data(hours=msg.text)
    data   = await state.get_data()
    cart   = data["cart"]
    is_doc = not is_admin(msg.from_user.id)
    total  = sum(get_price(c)*q for c,q in cart)
    lines  = ["📋 <b>Подтвердите направление:</b>\n"]
    for code, qty in cart:
        name, _ = PRODUCTS.get(code,(code,0))
        lines.append(f"• {name} x{qty}" if is_doc else f"• {name} x{qty} = {fmt(get_price(code)*qty)}")
    if not is_doc:
        lines.append(f"\n💵 <b>{fmt(total)}</b>")
    lines.append(f"\n⏰ Клиент придёт: <b>{msg.text}</b>")
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
    total      = sum(get_price(c)*q for c,q in cart)
    ref_num    = unique_ref()
    sent_time  = datetime.now(TZ).strftime("%d.%m.%Y %H:%M")
    with db() as con:
        cur = con.execute(
            "INSERT INTO referrals (doctor_id,items_json,total_price,expected_in,ref_number) VALUES (?,?,?,?,?)",
            (data["doctor_id"], items_json, total, hours, ref_num)
        )
        ref_id = cur.lastrowid
    await state.clear()
    sent_time = datetime.now(TZ).strftime("%d.%m.%Y %H:%M")
    lines = [f"✅ <b>Направление отправлено!</b>\n🔖 <b>{ref_num}</b>  |  📅 {sent_time}\n"]
    for code, qty in cart:
        name, _ = PRODUCTS.get(code,(code,0))
        lines.append(f"• {name} x{qty}")
    lines.append(f"\n💵 {fmt(total)}\n⏰ Клиент придёт: {hours}")
    lines.append(f"\n\n📋 <b>Не забудьте:</b> напишите ваш номер телефона в листок флаера перед отправкой клиента")
    await msg.answer("\n".join(lines), reply_markup=kb_doctor())
    all_admins = list(set(SENIOR_ADMINS + STAFF_IDS))
    adm_lines = [f"🔔 <b>Новый клиент от врача!</b>\n",
                 f"👨‍⚕️ <b>{data['doctor_name']}</b>",
                 f"⏰ <b>{hours}</b>  |  🔖 {ref_num}  |  📅 {sent_time}\n"]
    for code, qty in cart:
        name, price = PRODUCTS.get(code,(code,0))
        adm_lines.append(f"• {name} x{qty} = {fmt(price*qty)}")
    adm_lines.append(f"\n💵 <b>Итого: {fmt(total)}</b>")
    for aid in all_admins:
        try:
            await bot.send_message(aid, "\n".join(adm_lines), reply_markup=inline_sale(ref_id))
        except: pass

# ── Купил — просим фото чека или ввод времени ──
@dp.callback_query(F.data.startswith("bought:"))
async def cb_bought(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа"); return
    ref_id = int(call.data.split(":")[1])
    with db() as con:
        ref = con.execute(
            "SELECT r.*,d.full_name,d.tg_id,d.clinic FROM referrals r JOIN doctors d ON d.id=r.doctor_id WHERE r.id=?",
            (ref_id,)
        ).fetchone()
    if not ref or ref[5] != "pending":
        await call.answer("Уже обработано"); return

    bought_time = datetime.now(TZ).strftime("%d.%m.%Y %H:%M:%S")
    bonus_pct = get_bonus_pct()
    bonus = round(ref[3] * bonus_pct / 100)

    # Показываем подтверждение с возможностью изменить бонус
    await state.update_data(confirm_ref_id=ref_id, default_bonus=bonus)
    items = json.loads(ref[2])
    names = ", ".join(PRODUCTS.get(c,(c,0))[0] for c,_ in items)
    await call.message.answer(
        f"✅ <b>Подтверждение покупки</b>\n\n"
        f"👨‍⚕️ {ref[10]}\n"
        f"📦 {names}\n"
        f"🔖 {ref[9]}\n\n"
        f"💰 Бонус врача: <b>{fmt(bonus)}</b> ({bonus_pct:.0f}%)\n\n"
        f"📸 Отправьте <b>фото чека</b>\n"
        f"— или —\n"
        f"⌨️ Введите дату и время вручную: <i>02.05.2026 14:35</i>",
        reply_markup=ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton(text="🕐 Сейчас")],
            [KeyboardButton(text=f"✏️ Изменить бонус (сейчас {fmt(bonus)})")],
            [KeyboardButton(text="◀️ Отмена")]
        ])
    )
    await state.set_state(ConfirmBought.waiting)
    await call.answer()

@dp.message(ConfirmBought.waiting)
async def confirm_bought_input(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id): return
    data          = await state.get_data()
    ref_id        = data.get("confirm_ref_id")
    default_bonus = data.get("default_bonus", 0)

    if msg.text == "◀️ Отмена":
        await state.clear()
        await msg.answer("Отменено.", reply_markup=main_kb(msg.from_user.id)); return

    # Изменить бонус — только старший админ
    if msg.text and msg.text.startswith("✏️ Изменить бонус") and is_senior(msg.from_user.id):
        await msg.answer(
            f"✏️ Введите новую сумму бонуса в сумах:\n<i>Текущий: {fmt(int(default_bonus))}</i>",
            reply_markup=ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
                [KeyboardButton(text="◀️ Отмена")]
            ])
        )
        await state.set_state(ConfirmBonus.edit)
        return

    with db() as con:
        ref = con.execute(
            "SELECT r.*,d.full_name,d.tg_id FROM referrals r JOIN doctors d ON d.id=r.doctor_id WHERE r.id=?",
            (ref_id,)
        ).fetchone()
    if not ref:
        await state.clear()
        await msg.answer("❌ Ошибка.", reply_markup=main_kb(msg.from_user.id)); return

    photo_id = None
    bought_time = None

    if msg.photo:
        photo_id    = msg.photo[-1].file_id
        bought_time = now_tashkent()
    elif msg.text == "🕐 Сейчас":
        bought_time = now_tashkent()
    elif msg.text:
        try:
            dt = datetime.strptime(msg.text.strip(), "%d.%m.%Y %H:%M")
            bought_time = dt.strftime("%d.%m.%Y %H:%M:%S")
        except ValueError:
            await msg.answer(
                "❌ Неверный формат.\nВведите: <b>02.05.2026 14:35</b>\n"
                "Или нажмите <b>🕐 Сейчас</b>"
            ); return

    bonus = data.get("custom_bonus", default_bonus)
    await state.clear()

    with db() as con:
        con.execute("UPDATE referrals SET status='bought',bought_at=?,bonus=?,confirmed_by=? WHERE id=?",
                    (bought_time, bonus, msg.from_user.id, ref_id))

    confirm_text = (
        f"✅ <b>Продажа подтверждена!</b>\n\n"
        f"👨‍⚕️ {ref[10]}\n🔖 {ref[9]}\n"
        f"📅 <b>{bought_time}</b>\n\n"
        f"{cart_to_text(ref[2], show_prices=True)}\n\n"
        f"💰 Бонус врача: <b>{fmt(int(bonus))}</b>"
    )

    if photo_id:
        await msg.answer_photo(photo_id, caption=confirm_text, reply_markup=main_kb(msg.from_user.id))
    else:
        await msg.answer(confirm_text, reply_markup=main_kb(msg.from_user.id))

    for aid in SENIOR_ADMINS:
        if aid != msg.from_user.id:
            try:
                if photo_id:
                    await bot.send_photo(aid, photo_id, caption=confirm_text)
                else:
                    await bot.send_message(aid, confirm_text)
            except: pass

    # Врач НЕ получает уведомление сразу — только в 22:00

@dp.message(ConfirmBonus.edit)
async def confirm_bonus_edit(msg: types.Message, state: FSMContext):
    if not is_senior(msg.from_user.id): return
    if msg.text == "◀️ Отмена":
        await state.clear()
        await msg.answer("Отменено.", reply_markup=main_kb(msg.from_user.id)); return
    try:
        new_bonus = float(msg.text.replace(" ","").replace(",",".").replace("сум","").strip())
        if new_bonus < 0: raise ValueError
    except ValueError:
        await msg.answer("❌ Введите сумму числом, например: 50000"); return

    await state.update_data(custom_bonus=new_bonus)
    await msg.answer(
        f"✅ Бонус изменён на <b>{fmt(int(new_bonus))}</b>\n\n"
        f"Теперь отправьте фото чека или введите время:",
        reply_markup=ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton(text="🕐 Сейчас")],
            [KeyboardButton(text="◀️ Отмена")]
        ])
    )
    await state.set_state(ConfirmBought.waiting)
# ── Не купил ──────────────────────────────────
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
        nobuy_text = f"❌ <b>Не купил</b>\n\n👨‍⚕️ {ref[10]}\n🔖 {ref[9]}\n📅 {nobuy_time}\n\n{cart_to_text(ref[2])}"
        await call.message.edit_text(nobuy_text)
        # Уведомление всем старшим админам
        for aid in SENIOR_ADMINS:
            if aid != call.from_user.id:
                try: await bot.send_message(aid, nobuy_text)
                except: pass
        if ref[11]:
            try:
                await bot.send_message(ref[11],
                    f"📊 <b>Отчёт</b>\n🔖 {ref[9]}\n📅 {nobuy_time}\n\n{cart_to_text(ref[2])}\n\n❌ Клиент не купил.")
            except: pass
    await call.answer()

# ── Настройки ─────────────────────────────────
@dp.message(F.text == "⚙️ Настройки")
async def settings_menu(msg: types.Message, state: FSMContext):
    if not is_senior(msg.from_user.id): return
    bonus_pct = get_bonus_pct()
    await msg.answer(
        f"⚙️ <b>Настройки магазина</b>\n\n"
        f"💰 Бонус врачам: <b>{bonus_pct:.0f}%</b>\n\n"
        f"Что изменить?",
        reply_markup=ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton(text="💰 Изменить % бонуса")],
            [KeyboardButton(text="🏷 Изменить цену товара")],
            [KeyboardButton(text="➕ Добавить новый товар")],
            [KeyboardButton(text="🔄 Перезапустить бот")],
            [KeyboardButton(text="◀️ Назад")],
        ])
    )
    await state.set_state(Settings.menu)

@dp.message(Settings.menu)
async def settings_choice(msg: types.Message, state: FSMContext):
    if not is_senior(msg.from_user.id): return
    if msg.text == "◀️ Назад":
        await state.clear()
        await msg.answer("Главное меню", reply_markup=kb_senior()); return

    if msg.text == "💰 Изменить % бонуса":
        bonus_pct = get_bonus_pct()
        await msg.answer(
            f"💰 Текущий бонус: <b>{bonus_pct:.0f}%</b>\n\n"
            f"Введите новый процент (например: 15):",
            reply_markup=ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
                [KeyboardButton(text="◀️ Назад")]
            ])
        )
        await state.set_state(Settings.bonus_pct)

    elif msg.text == "🏷 Изменить цену товара":
        cats = get_all_categories()
        buttons = [[KeyboardButton(text=cat)] for cat in cats.keys()]
        buttons.append([KeyboardButton(text="◀️ Назад")])
        await msg.answer(
            "🏷 Выберите категорию товара:",
            reply_markup=ReplyKeyboardMarkup(resize_keyboard=True, keyboard=buttons)
        )
        await state.set_state(Settings.price_cat)

    elif msg.text == "➕ Добавить новый товар":
        cats = get_all_categories()
        all_cat_names = list(cats.keys()) + ["➕ Новая категория"]
        buttons = [[KeyboardButton(text=c)] for c in all_cat_names]
        buttons.append([KeyboardButton(text="◀️ Назад")])
        await msg.answer(
            "➕ <b>Добавить новый товар</b>\n\n"
            "Выберите категорию или создайте новую:",
            reply_markup=ReplyKeyboardMarkup(resize_keyboard=True, keyboard=buttons)
        )
        await state.set_state(Settings.new_prod_cat)

    elif msg.text == "🔄 Перезапустить бот":
        await msg.answer(
            "🔄 <b>Перезапуск бота...</b>\n\n"
            "Бот перезапустится через 3 секунды.\n"
            "Все врачи и администраторы смогут пользоваться ботом заново.",
            reply_markup=kb_senior()
        )
        await state.clear()
        await asyncio.sleep(3)
        import sys, os as _os
        _os.execv(sys.executable, [sys.executable] + sys.argv)

@dp.message(Settings.bonus_pct)
async def settings_set_bonus(msg: types.Message, state: FSMContext):
    if not is_senior(msg.from_user.id): return
    if msg.text == "◀️ Назад":
        await state.set_state(Settings.menu)
        await settings_menu(msg, state); return
    try:
        pct = float(msg.text.replace("%","").strip())
        if not 0 < pct <= 100: raise ValueError
    except ValueError:
        await msg.answer("❌ Введите число от 1 до 100, например: 18"); return
    set_setting("bonus_pct", pct)
    await state.clear()
    await msg.answer(
        f"✅ Бонус врачам изменён на <b>{pct:.0f}%</b>",
        reply_markup=kb_senior()
    )

@dp.message(Settings.price_cat)
async def settings_price_cat(msg: types.Message, state: FSMContext):
    if not is_senior(msg.from_user.id): return
    if msg.text == "◀️ Назад":
        await state.set_state(Settings.menu)
        await settings_menu(msg, state); return
    cats = get_all_categories()
    if msg.text not in cats:
        await msg.answer("Выберите из списка."); return
    await state.update_data(price_cat=msg.text)
    items = cats[msg.text]
    buttons = [[KeyboardButton(text=f"{name} (сейчас: {fmt(get_price(code))})")] for code, name, _ in items]
    buttons.append([KeyboardButton(text="◀️ Назад")])
    await msg.answer(
        f"🏷 <b>{msg.text}</b>\nВыберите товар:",
        reply_markup=ReplyKeyboardMarkup(resize_keyboard=True, keyboard=buttons)
    )
    await state.set_state(Settings.price_item)

@dp.message(Settings.price_item)
async def settings_price_item(msg: types.Message, state: FSMContext):
    if not is_senior(msg.from_user.id): return
    if msg.text == "◀️ Назад":
        await state.set_state(Settings.price_cat)
        return
    data = await state.get_data()
    cat  = data.get("price_cat")
    cats = get_all_categories()
    found_code = None
    found_name = None
    for code, name, _ in cats.get(cat, []):
        if msg.text.startswith(name):
            found_code = code
            found_name = name
            break
    if not found_code:
        await msg.answer("Выберите из списка."); return
    await state.update_data(price_code=found_code, price_name=found_name)
    await msg.answer(
        f"🏷 <b>{found_name}</b>\n"
        f"Текущая цена: <b>{fmt(get_price(found_code))}</b>\n\n"
        f"Введите новую цену в сумах (например: 250000):",
        reply_markup=ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton(text="◀️ Назад")]
        ])
    )
    await state.set_state(Settings.price_value)

@dp.message(Settings.price_value)
async def settings_set_price(msg: types.Message, state: FSMContext):
    if not is_senior(msg.from_user.id): return
    if msg.text == "◀️ Назад":
        await state.set_state(Settings.price_item)
        return
    try:
        price = int(msg.text.replace(" ","").replace("сум","").replace(",","").strip())
        if price <= 0: raise ValueError
    except ValueError:
        await msg.answer("❌ Введите сумму числом, например: 250000"); return
    data = await state.get_data()
    code = data.get("price_code")
    name = data.get("price_name")
    set_setting(f"price_{code}", price)
    await state.clear()
    await msg.answer(
        f"✅ Цена <b>{name}</b> изменена на <b>{fmt(price)}</b>",
        reply_markup=kb_senior()
    )

# ── Добавить новый товар ───────────────────────
@dp.message(Settings.new_prod_cat)
async def new_prod_cat(msg: types.Message, state: FSMContext):
    if not is_senior(msg.from_user.id): return
    if msg.text == "◀️ Назад":
        await state.set_state(Settings.menu)
        await settings_menu(msg, state); return
    if msg.text == "➕ Новая категория":
        await msg.answer(
            "Введите название новой категории (например: 🦷 Стоматология):",
            reply_markup=ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
                [KeyboardButton(text="◀️ Назад")]
            ])
        )
    await state.update_data(new_cat=msg.text)
    await msg.answer(
        f"📦 Категория: <b>{msg.text}</b>\n\n"
        f"Введите <b>название товара</b>:",
        reply_markup=ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton(text="◀️ Назад")]
        ])
    )
    await state.set_state(Settings.new_prod_name)

@dp.message(Settings.new_prod_name)
async def new_prod_name_handler(msg: types.Message, state: FSMContext):
    if not is_senior(msg.from_user.id): return
    if msg.text == "◀️ Назад":
        await state.set_state(Settings.new_prod_cat)
        return
    await state.update_data(new_name=msg.text.strip())
    await msg.answer(
        f"📦 Товар: <b>{msg.text.strip()}</b>\n\n"
        f"Введите <b>цену</b> в сумах (например: 300000):",
        reply_markup=ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton(text="◀️ Назад")]
        ])
    )
    await state.set_state(Settings.new_prod_price)

@dp.message(Settings.new_prod_price)
async def new_prod_price_handler(msg: types.Message, state: FSMContext):
    if not is_senior(msg.from_user.id): return
    if msg.text == "◀️ Назад":
        await state.set_state(Settings.new_prod_name)
        return
    try:
        price = int(msg.text.replace(" ","").replace("сум","").replace(",","").strip())
        if price <= 0: raise ValueError
    except ValueError:
        await msg.answer("❌ Введите сумму числом, например: 300000"); return
    await state.update_data(new_price=price)
    bonus_pct = get_bonus_pct()
    await msg.answer(
        f"💰 Введите <b>% бонуса</b> для этого товара\n\n"
        f"Или нажмите <b>Общий ({bonus_pct:.0f}%)</b> чтобы использовать стандартный:",
        reply_markup=ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton(text=f"Общий ({bonus_pct:.0f}%)")],
            [KeyboardButton(text="◀️ Назад")]
        ])
    )
    await state.set_state(Settings.new_prod_bonus)

@dp.message(Settings.new_prod_bonus)
async def new_prod_bonus_handler(msg: types.Message, state: FSMContext):
    if not is_senior(msg.from_user.id): return
    if msg.text == "◀️ Назад":
        await state.set_state(Settings.new_prod_price)
        return
    data = await state.get_data()
    bonus_pct_custom = 0  # 0 = использовать общий
    if not msg.text.startswith("Общий"):
        try:
            bonus_pct_custom = float(msg.text.replace("%","").strip())
            if not 0 <= bonus_pct_custom <= 100: raise ValueError
        except ValueError:
            await msg.answer("❌ Введите число от 0 до 100, например: 15"); return

    # Генерируем код
    import re
    code = "CUSTOM_" + re.sub(r'[^A-Za-z0-9]', '', data["new_name"].upper())[:10] + "_" + str(random.randint(100,999))

    with db() as con:
        con.execute(
            "INSERT INTO custom_products (code, name, category, price, bonus_pct) VALUES (?,?,?,?,?)",
            (code, data["new_name"], data["new_cat"], data["new_price"], bonus_pct_custom)
        )

    await state.clear()
    bonus_display = f"{bonus_pct_custom:.0f}%" if bonus_pct_custom > 0 else f"общий ({get_bonus_pct():.0f}%)"
    await msg.answer(
        f"✅ <b>Товар добавлен!</b>\n\n"
        f"📦 {data['new_name']}\n"
        f"📂 {data['new_cat']}\n"
        f"💵 {fmt(data['new_price'])}\n"
        f"💰 Бонус: {bonus_display}\n\n"
        f"Товар сразу доступен врачам в каталоге.",
        reply_markup=kb_senior()
    )
@dp.message(F.text == "🚶 Клиент пришёл")
async def client_arrived(msg: types.Message):
    if not is_admin(msg.from_user.id): return
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    with db() as con:
        con.execute("INSERT INTO visits (added_by) VALUES (?)", (msg.from_user.id,))
        count = con.execute(
            "SELECT COUNT(*) FROM visits WHERE visited_at LIKE ?",
            (f"{today}%",)
        ).fetchone()[0]
    await msg.answer(
        f"🚶 <b>Клиент зафиксирован!</b>\n\n"
        f"📅 Сегодня зашло клиентов: <b>{count}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="➕ Ещё один", callback_data="visit_add"),
            InlineKeyboardButton(text="➖ Убрать",   callback_data="visit_remove"),
        ]])
    )

@dp.callback_query(F.data == "visit_add")
async def visit_add(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа"); return
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    with db() as con:
        con.execute("INSERT INTO visits (added_by) VALUES (?)", (call.from_user.id,))
        count = con.execute(
            "SELECT COUNT(*) FROM visits WHERE visited_at LIKE ?",
            (f"{today}%",)
        ).fetchone()[0]
    await call.message.edit_text(
        f"🚶 <b>Клиент добавлен!</b>\n\n"
        f"📅 Сегодня зашло клиентов: <b>{count}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="➕ Ещё один", callback_data="visit_add"),
            InlineKeyboardButton(text="➖ Убрать",   callback_data="visit_remove"),
        ]])
    )
    await call.answer()

@dp.callback_query(F.data == "visit_remove")
async def visit_remove(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа"); return
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    with db() as con:
        # Удаляем последнюю запись за сегодня
        last = con.execute(
            "SELECT id FROM visits WHERE visited_at LIKE ? ORDER BY id DESC LIMIT 1",
            (f"{today}%",)
        ).fetchone()
        if last:
            con.execute("DELETE FROM visits WHERE id=?", (last[0],))
        count = con.execute(
            "SELECT COUNT(*) FROM visits WHERE visited_at LIKE ?",
            (f"{today}%",)
        ).fetchone()[0]
    if not last:
        await call.answer("Нельзя убрать — счётчик уже 0"); return
    await call.message.edit_text(
        f"➖ <b>Убрано!</b>\n\n"
        f"📅 Сегодня зашло клиентов: <b>{count}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="➕ Ещё один", callback_data="visit_add"),
            InlineKeyboardButton(text="➖ Убрать",   callback_data="visit_remove"),
        ]])
    )
    await call.answer()

# ── Поиск по клинике ──────────────────────────
@dp.message(F.text == "🔍 Поиск по клинике")
async def search_clinic_start(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id): return
    await state.clear()
    await msg.answer(
        "🔍 Введите название клиники (можно часть слова):\n\n"
        "<i>Например: стомат, поликлиника, №5</i>",
        reply_markup=ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton(text="◀️ Отмена поиска")]
        ])
    )
    await state.set_state(SearchClinic.query)

@dp.message(SearchClinic.query)
async def search_clinic_result(msg: types.Message, state: FSMContext):
    await state.clear()
    if msg.text == "◀️ Отмена поиска":
        await msg.answer("Отменено.", reply_markup=main_kb(msg.from_user.id)); return
    query = msg.text.strip()
    refs  = search_by_clinic(query)
    await msg.answer(reply_markup=main_kb(msg.from_user.id), text="🔍")
    if not refs:
        await msg.answer(f"📭 Нет ожидаемых клиентов от клиник с «{query}»"); return
    await msg.answer(f"🔍 <b>Найдено: {len(refs)}</b> по запросу «{query}»")
    for ref_id, name, clinic, phone, items_json, total, hours, sent_at, ref_num, doc_id in refs:
        await msg.answer(
            f"👨‍⚕️ <b>{name}</b>  ({clinic})\n📱 {phone}\n"
            f"🔖 {ref_num}  |  ⏰ {hours}  |  🕐 {sent_at[11:16]}\n\n"
            f"{cart_to_text(items_json)}",
            reply_markup=inline_sale(ref_id)
        )

# ── Выплата бонусов ───────────────────────────
@dp.message(F.text == "💰 Выплатить бонус")
async def pay_start(msg: types.Message, state: FSMContext):
    if not is_senior(msg.from_user.id): return
    kb = inline_doctors_pay()
    if not kb:
        await msg.answer("💰 Нет врачей с невыплаченными бонусами."); return
    await msg.answer("👨‍⚕️ <b>Выберите врача:</b>", reply_markup=kb)

@dp.callback_query(F.data.startswith("paydoc:"))
async def pay_select(call: types.CallbackQuery, state: FSMContext):
    if not is_senior(call.from_user.id):
        await call.answer("Нет доступа"); return
    doc_id = int(call.data.split(":")[1])
    with db() as con:
        doc = con.execute("SELECT * FROM doctors WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        await call.answer("Врач не найден"); return
    total, bought, earned, paid = doctor_stats(doc_id)
    balance = earned - paid
    await state.update_data(
        pay_doctor_id=doc_id, pay_doctor_name=doc[2],
        pay_doctor_tg=doc[1], pay_balance=balance
    )
    await call.message.edit_text(
        f"👨‍⚕️ <b>{doc[2]}</b>\n🏥 {doc[3]}  |  📱 {doc[4]}\n\n"
        f"💰 Заработано: <b>{fmt(int(earned))}</b>\n"
        f"✅ Выплачено: <b>{fmt(int(paid))}</b>\n"
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
        await msg.answer("❌ Введите сумму числом, например: 150000"); return
    data = await state.get_data()
    if amount > data["pay_balance"]:
        await msg.answer(f"❌ Превышает баланс ({fmt(int(data['pay_balance']))}). Введите меньше:"); return
    await state.update_data(pay_amount=amount)
    await msg.answer(
        f"📸 Отправьте <b>фото чека</b> или скриншот перевода\n\n"
        f"Сумма: <b>{fmt(int(amount))}</b>\nВрач: <b>{data['pay_doctor_name']}</b>"
    )
    await state.set_state(PayBonus.photo)

@dp.message(PayBonus.photo, F.photo)
async def pay_photo(msg: types.Message, state: FSMContext):
    if not is_senior(msg.from_user.id): return
    data      = await state.get_data()
    amount    = data["pay_amount"]
    doc_id    = data["pay_doctor_id"]
    paid_time = datetime.now().strftime("%d.%m.%Y %H:%M")
    with db() as con:
        con.execute("INSERT INTO payments (doctor_id,amount,paid_by) VALUES (?,?,?)",
                    (doc_id, amount, msg.from_user.id))
    _, _, earned, paid_total = doctor_stats(doc_id)
    balance   = earned - paid_total
    photo_id  = msg.photo[-1].file_id
    await state.clear()
    caption = (
        f"✅ <b>Выплата записана!</b>\n\n"
        f"👨‍⚕️ {data['pay_doctor_name']}\n"
        f"💰 Выплачено: <b>{fmt(int(amount))}</b>\n"
        f"💵 Остаток: <b>{fmt(int(balance))}</b>\n"
        f"📅 {paid_time}"
    )
    await msg.answer_photo(photo_id, caption=caption, reply_markup=kb_senior())
    for aid in SENIOR_ADMINS:
        if aid != msg.from_user.id:
            try: await bot.send_photo(aid, photo_id, caption=caption)
            except: pass
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
async def pay_no_photo(msg: types.Message):
    await msg.answer("📸 Отправьте <b>фото чека</b>")

# ── Кнопки врача ──────────────────────────────
@dp.message(F.text == "📊 Мои показатели")
async def doc_stats(msg: types.Message):
    doc = doctor_by_tg(msg.from_user.id)
    if not doc: return
    total, bought, earned, paid = doctor_stats(doc[0])
    notbought = total - bought
    conv      = round(bought/total*100) if total else 0
    await msg.answer(
        f"📊 <b>Ваша статистика</b>\n\n"
        f"👤 {doc[2]}\n🏥 {doc[3]}\n📱 {doc[4]}\n\n"
        f"📤 Всего направлений: <b>{total}</b>\n"
        f"✅ Купили: <b>{bought}</b>  ❌ Не купили: <b>{notbought}</b>\n"
        f"📈 Конверсия: <b>{conv}%</b>\n\n"
        f"💰 Бонусы приходят каждый день в <b>22:00</b> 🌙"
    )

@dp.message(F.text == "📅 За месяц")
async def doc_month(msg: types.Message):
    doc = doctor_by_tg(msg.from_user.id)
    if not doc: return
    total, bought, bonus = doctor_month_stats(doc[0])
    notbought = (total or 0) - (bought or 0)
    conv = round((bought or 0)/(total or 1)*100)
    await msg.answer(
        f"📅 <b>Статистика за этот месяц</b>\n\n"
        f"📤 Направлений: <b>{total or 0}</b>\n"
        f"✅ Купили: <b>{bought or 0}</b>  ❌ Не купили: <b>{notbought}</b>\n"
        f"📈 Конверсия: <b>{conv}%</b>\n\n"
        f"💰 Бонусы приходят каждый день в <b>22:00</b> 🌙"
    )

@dp.message(F.text == "🏆 Мой рейтинг")
async def doc_ranking(msg: types.Message):
    doc = doctor_by_tg(msg.from_user.id)
    if not doc: return
    rank, total_docs = doctor_ranking(doc[0])
    top = weekly_top()
    lines = [f"🏆 <b>Рейтинг за неделю</b>\n\n"
             f"Ваше место: <b>{rank} из {total_docs}</b>\n\n"
             f"<b>Топ врачей:</b>"]
    medals = ["🥇","🥈","🥉"]
    for i, (name, clinic, total, bought, bonus) in enumerate(top, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        lines.append(f"{medal} {name} — {bought} покупок | {fmt(int(bonus))}")
    await msg.answer("\n".join(lines))

@dp.message(F.text == "💰 Мои бонусы")
async def doc_bonuses(msg: types.Message):
    doc = doctor_by_tg(msg.from_user.id)
    if not doc: return

    with db() as con:
        # Только бонусы которые уже были отправлены врачу в 22:00
        notified_row = con.execute("""
            SELECT COUNT(*), COALESCE(SUM(bonus), 0)
            FROM referrals
            WHERE doctor_id=? AND status='bought' AND notified=1
        """, (doc[0],)).fetchone()

        # Выплаты
        paid_row = con.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE doctor_id=?",
            (doc[0],)
        ).fetchone()

        # История выплат
        payments = con.execute("""
            SELECT amount, paid_at FROM payments
            WHERE doctor_id=? ORDER BY paid_at DESC LIMIT 10
        """, (doc[0],)).fetchall()

    cnt     = notified_row[0] or 0
    earned  = notified_row[1] or 0
    paid    = paid_row[0] or 0
    balance = earned - paid

    lines = [
        f"💰 <b>Мои бонусы</b>\n",
        f"📦 Покупок: <b>{cnt}</b>",
        f"💰 Накоплено: <b>{fmt(int(earned))}</b>",
        f"✅ Выплачено: <b>{fmt(int(paid))}</b>",
        f"💵 <b>К выплате: {fmt(int(max(0, balance)))}</b>",
        f"\n<i>Обновляется каждый день в 22:00 🌙</i>",
    ]

    if payments:
        lines.append(f"\n💳 <b>История выплат:</b>")
        for amount, paid_at in payments:
            lines.append(f"  • {fmt(int(amount))} — {paid_at[:16]}")

    await msg.answer("\n".join(lines))

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
    all_prods = get_all_products()
    for items_json, hours, status, bonus, sent_at, bought_at, ref_num in refs:
        dt = f"\n   📅 {bought_at[:16]}" if status=="bought" and bought_at else ""
        items = json.loads(items_json)
        names = ", ".join(all_prods.get(c,(c,0))[0] for c,_ in items)
        lines.append(f"{sm.get(status,'?')} <b>{ref_num}</b>\n   📦 {names}{dt}\n   🕐 {sent_at[:16]}\n")
    await msg.answer("\n".join(lines))

# ── Кнопки администратора ─────────────────────
@dp.message(F.text == "⏳ Все ожидаемые")
async def admin_all_pending(msg: types.Message):
    if not is_admin(msg.from_user.id): return
    refs = pending_refs()
    if not refs:
        await msg.answer("📭 Нет ожидаемых клиентов."); return
    await msg.answer(f"⏳ <b>Всего ожидается: {len(refs)}</b>")
    for ref_id, name, clinic, phone, items_json, total, hours, sent_at, ref_num, doc_id in refs:
        await msg.answer(
            f"👨‍⚕️ <b>{name}</b>  ({clinic})\n📱 {phone}\n"
            f"🔖 {ref_num}  |  ⏰ {hours}  |  🕐 {sent_at[11:16]}\n\n"
            f"{cart_to_text(items_json)}",
            reply_markup=inline_sale(ref_id)
        )

@dp.message(F.text == "📅 Сегодня")
async def admin_today(msg: types.Message):
    if not is_admin(msg.from_user.id): return
    refs = today_pending_refs()
    if not refs:
        await msg.answer("📭 Сегодня нет ожидаемых клиентов."); return
    await msg.answer(f"📅 <b>Сегодня ожидается: {len(refs)}</b>")
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
        await msg.answer("📭 Врачей нет."); return
    lines = ["👨‍⚕️ <b>Все врачи:</b>\n"]
    for i, (did, name, clinic, phone, total, bought, earned, paid) in enumerate(doctors, 1):
        balance = earned - paid
        conv    = round(bought/total*100) if total else 0
        lines.append(
            f"{i}. <b>{name}</b>\n"
            f"   🏥 {clinic}  |  📱 {phone}\n"
            f"   📤 {total} | ✅ {bought} ({conv}%)\n"
            f"   💰 {fmt(int(earned))}  |  💵 К выплате: <b>{fmt(int(balance))}</b>\n"
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

@dp.message(F.text == "📈 Отчёт за неделю")
async def admin_weekly(msg: types.Message):
    if not is_senior(msg.from_user.id): return
    top = weekly_top()
    if not top:
        await msg.answer("📭 За неделю нет данных."); return
    lines = ["📈 <b>Отчёт за неделю — топ врачей:</b>\n"]
    medals = ["🥇","🥈","🥉"]
    for i, (name, clinic, total, bought, bonus) in enumerate(top, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        conv  = round(bought/total*100) if total else 0
        lines.append(
            f"{medal} <b>{name}</b>  ({clinic})\n"
            f"   📤 {total} | ✅ {bought} ({conv}%) | 💰 {fmt(int(bonus))}\n"
        )
    await msg.answer("\n".join(lines))

@dp.message(F.text == "📋 История")
async def admin_history(msg: types.Message):
    if not is_admin(msg.from_user.id): return
    with db() as con:
        refs = con.execute("""
            SELECT d.full_name, r.items_json, r.status, r.bonus,
                   r.sent_at, r.bought_at, r.ref_number
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
        lines.append(f"{sm.get(status,'?')} <b>{name}</b> — {ref_num}{b}\n   {names}{dt}\n   🕐 {sent_at[:16]}\n")
    await msg.answer("\n".join(lines))

@dp.message(F.text == "🗒 Дневной лист")
async def admin_daily_sheet(msg: types.Message):
    if not is_senior(msg.from_user.id): return
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    with db() as con:
        refs = con.execute("""
            SELECT r.id, d.full_name, d.clinic, r.items_json, r.status,
                   r.bonus, r.sent_at, r.bought_at, r.ref_number
            FROM referrals r JOIN doctors d ON d.id=r.doctor_id
            WHERE r.sent_at LIKE ?
            ORDER BY r.sent_at ASC
        """, (f"{today}%",)).fetchall()

    if not refs:
        await msg.answer(f"📭 Сегодня ({today}) направлений нет."); return

    bought_list    = [r for r in refs if r[4] == "bought"]
    notbought_list = [r for r in refs if r[4] == "notbought"]
    pending_list   = [r for r in refs if r[4] == "pending"]

    # Считаем посетителей за сегодня
    with db() as con:
        visitors = con.execute(
            "SELECT COUNT(*) FROM visits WHERE visited_at LIKE ?",
            (f"{today}%",)
        ).fetchone()[0]

    await msg.answer(
        f"🗒 <b>Дневной лист — {datetime.now(TZ).strftime('%d.%m.%Y')}</b>\n\n"
        f"🚶 Всего зашло в магазин: <b>{visitors}</b>\n\n"
        f"✅ Купили (от врачей): <b>{len(bought_list)}</b>\n"
        f"❌ Не купили: <b>{len(notbought_list)}</b>\n"
        f"⏳ Под вопросом: <b>{len(pending_list)}</b>\n"
        f"📤 Всего направлений: <b>{len(refs)}</b>"
    )

    # Купили
    if bought_list:
        await msg.answer("✅ <b>КУПИЛИ:</b>")
        for ref_id, name, clinic, items_json, status, bonus, sent_at, bought_at, ref_num in bought_list:
            items = json.loads(items_json)
            names = ", ".join(PRODUCTS.get(c,(c,0))[0] for c,_ in items)
            await msg.answer(
                f"✅ <b>{name}</b>  ({clinic})\n"
                f"📦 {names}\n"
                f"🔖 {ref_num}\n"
                f"📅 Куплено: <b>{bought_at}</b>\n"
                f"💰 Бонус: <b>{fmt(int(bonus))}</b>"
            )

    # Не купили
    if notbought_list:
        await msg.answer("❌ <b>НЕ КУПИЛИ:</b>")
        for ref_id, name, clinic, items_json, status, bonus, sent_at, bought_at, ref_num in notbought_list:
            items = json.loads(items_json)
            names = ", ".join(PRODUCTS.get(c,(c,0))[0] for c,_ in items)
            await msg.answer(
                f"❌ <b>{name}</b>  ({clinic})\n"
                f"📦 {names}\n"
                f"🔖 {ref_num}\n"
                f"📅 Отмечено: {bought_at[:16] if bought_at else '—'}"
            )

    # Под вопросом — с кнопками
    if pending_list:
        await msg.answer(
            f"⏳ <b>ПОД ВОПРОСОМ — нужно отметить:</b>\n\n"
            f"<i>Сверьте с кассой и нажмите купил/не купил</i>"
        )
        for ref_id, name, clinic, items_json, status, bonus, sent_at, bought_at, ref_num in pending_list:
            await msg.answer(
                f"⏳ <b>{name}</b>  ({clinic})\n"
                f"{cart_to_text(items_json)}\n"
                f"🔖 {ref_num}  |  🕐 {sent_at[11:16]}",
                reply_markup=inline_sale(ref_id)
            )

# ── Бэкап ─────────────────────────────────────
async def send_backup(chat_id: int):
    if not os.path.exists(DB_PATH):
        await bot.send_message(chat_id, "❌ База данных не найдена."); return
    with db() as con:
        docs   = con.execute("SELECT COUNT(*) FROM doctors WHERE is_active=1").fetchone()[0]
        total  = con.execute("SELECT COUNT(*) FROM referrals").fetchone()[0]
        bought = con.execute("SELECT COUNT(*) FROM referrals WHERE status='bought'").fetchone()[0]
        bonus  = con.execute("SELECT COALESCE(SUM(bonus),0) FROM referrals WHERE status='bought'").fetchone()[0]
    now     = datetime.now().strftime("%d.%m.%Y %H:%M")
    caption = (f"💾 <b>Бэкап OrthoShop</b>\n📅 {now}\n"
               f"👨‍⚕️ {docs} врачей  |  📤 {total} направлений\n"
               f"✅ {bought} куплено  |  💰 {fmt(int(bonus))}")
    name = f"orthotrack_{datetime.now().strftime('%Y%m%d_%H%M')}.db"
    await bot.send_document(chat_id, FSInputFile(DB_PATH, filename=name), caption=caption)

@dp.message(Command("backup"))
@dp.message(F.text == "💾 Бэкап")
async def cmd_backup(msg: types.Message):
    if not is_senior(msg.from_user.id):
        await msg.answer("❌ Только для старшего администратора."); return
    await msg.answer("⏳ Готовлю бэкап...")
    await send_backup(msg.from_user.id)

# ── Ежедневные задачи ─────────────────────────
async def daily_tasks():
    while True:
        now_tz = datetime.now(TZ)
        target = now_tz.replace(hour=22, minute=0, second=0, microsecond=0)
        if now_tz >= target:
            target += timedelta(days=1)
        await asyncio.sleep((target - now_tz).total_seconds())

        today = datetime.now(TZ).strftime("%Y-%m-%d")

        # Итог дня для каждого врача в 22:00
        with db() as con:
            docs = con.execute(
                "SELECT id, tg_id, full_name FROM doctors WHERE is_active=1 AND tg_id IS NOT NULL"
            ).fetchall()

        # Все неотправленные подтверждённые покупки — группируем по врачам
        with db() as con:
            unnotified = con.execute("""
                SELECT r.doctor_id, d.tg_id, d.full_name,
                       COUNT(*) as cnt,
                       COALESCE(SUM(r.bonus),0) as bonus
                FROM referrals r JOIN doctors d ON d.id=r.doctor_id
                WHERE r.status='bought' AND r.notified=0
                GROUP BY r.doctor_id
            """).fetchall()

        for doc_id, doc_tg, doc_name, cnt, bonus in unnotified:
            if not doc_tg: continue
            try:
                _, _, total_earned, total_paid = doctor_stats(doc_id)
                balance = total_earned - total_paid
                await bot.send_message(doc_tg,
                    f"🌙 <b>Итог дня — {datetime.now(TZ).strftime('%d.%m.%Y')}</b>\n\n"
                    f"✅ Подтверждено покупок: <b>{cnt}</b>\n"
                    f"💰 <b>Ваш бонус: {fmt(int(bonus))}</b>\n\n"
                    f"💵 Всего к выплате: <b>{fmt(int(balance))}</b>"
                )
                # Помечаем как отправленные
                with db() as con:
                    con.execute("""
                        UPDATE referrals SET notified=1
                        WHERE doctor_id=? AND status='bought' AND notified=0
                    """, (doc_id,))
            except: pass

        # Врачам у которых не было покупок но были направления — тоже отправляем итог
        with db() as con:
            docs_with_refs = con.execute("""
                SELECT DISTINCT d.id, d.tg_id
                FROM referrals r JOIN doctors d ON d.id=r.doctor_id
                WHERE r.sent_at LIKE ? AND d.tg_id IS NOT NULL
            """, (f"{today}%",)).fetchall()

        notified_ids = {row[0] for row in unnotified}
        for doc_id, doc_tg in docs_with_refs:
            if doc_id in notified_ids or not doc_tg: continue
            try:
                with db() as con:
                    row = con.execute("""
                        SELECT COUNT(*),
                               SUM(CASE WHEN status='bought' THEN 1 ELSE 0 END)
                        FROM referrals WHERE doctor_id=? AND sent_at LIKE ?
                    """, (doc_id, f"{today}%")).fetchone()
                td_total  = row[0] or 0
                td_bought = row[1] or 0
                if td_total > 0:
                    await bot.send_message(doc_tg,
                        f"🌙 <b>Итог дня — {datetime.now(TZ).strftime('%d.%m.%Y')}</b>\n\n"
                        f"📤 Направлений: <b>{td_total}</b>\n"
                        f"✅ Купили: <b>{td_bought}</b>\n"
                        f"💰 Бонусов за сегодня: <b>0 сум</b>\n\n"
                        f"<i>Ожидаем подтверждения от администратора</i>"
                    )
            except: pass
        # Напоминание врачам о pending > 24 часа
        cutoff = (datetime.now(TZ) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        with db() as con:
            old_refs = con.execute("""
                SELECT r.id, d.tg_id, r.items_json, r.ref_number, r.sent_at
                FROM referrals r JOIN doctors d ON d.id=r.doctor_id
                WHERE r.status='pending' AND r.sent_at <= ?
            """, (cutoff,)).fetchall()
        for ref_id, doc_tg, items_json, ref_num, sent_at in old_refs:
            if doc_tg:
                try:
                    items = json.loads(items_json)
                    names = ", ".join(PRODUCTS.get(c,(c,0))[0] for c,_ in items)
                    await bot.send_message(doc_tg,
                        f"⚠️ <b>Клиент ещё под вопросом</b>\n\n"
                        f"🔖 {ref_num}\n📦 {names}\n"
                        f"🕐 Отправлено: {sent_at[:16]}\n\n"
                        f"Результат придёт в 22:00 когда администратор подтвердит."
                    )
                except: pass

        # Бэкап для старших админов
        for aid in SENIOR_ADMINS:
            try: await send_backup(aid)
            except: pass

# ─────────────────────────────────────────────
async def main():
    init_db()
    print("✅ OrthoTrack v5 запущен!")
    asyncio.create_task(daily_tasks())
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
