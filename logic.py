# =========================
# 🧠 УМНЫЕ ТЕГИ (SMART TAGS)
# =========================

SMART_TAGS = {
    "еда": ["бургер", "обед", "kfc", "продукты", "шаурма", "кофе", "вода", "хлеб", "кафе", "ресторан", "столовая", "чай", "супермаркет", "пицца", "суши", "мясо", "овощи", "фрукты", "сладкое", "мороженое", "завтрак", "ужин", "бургер", "мак", "доставка", "салат", "молоко", "яйца", "сыр", "творог", "кефир", "йогурт", "сметана", "масло", "колбаса", "сосиски", "котлеты", "пельмени", "макароны", "рис", "гречка", "мука", "сахар", "соль", "перец", "приправа", "соус", "кетчуп", "майонез"],
    "транспорт": ["такси", "автобус", "метро", "яндекс", "бензин", "проезд", "маршрутка", "троллейбус", "парковка", "авто", "машина", "дорога", "билет", "перелет", "самолет", "поезд", "электричка", "жд", "авиабилет", "ждбилет", "топливо", "дизель", "газ", "мойка", "автосервис", "шина", "колесо", "запчасть"],
    "жилье": ["коммуналка", "свет", "интернет", "аренда", "квартира", "ремонт", "вода", "газ", "отопление", "мебель", "техника", "дом", "тсж", "домофон", "лифт", "мусор", "уборка", "стирка", "порошок", "кондиционер", "обои", "краска", "инструмент"],
    "развлечения": ["кино", "клуб", "игры", "подписка", "пиво", "бар", "кальян", "кинотеатр", "парк", "аттракционы", "концерт", "театр", "музей", "выставка", "steam", "ps", "playstation", "xbox", "nintendo", "донат", "премиум", "бильярд", "боулинг", "караоке", "кафетерий"],
    "здоровье": ["аптека", "врач", "таблетки", "анализы", "стоматолог", "больница", "клиника", "лекарства", "витамины", "зуб", "массаж", "окулист", "терапевт", "хирург", "узи", "мрт", "кровь", "рецепт", "мазь", "капли", "спрей", "бинты", "пластырь"],
    "шопинг": ["одежда", "обувь", "куртка", "штаны", "джинсы", "футболка", "кроссовки", "косметика", "парфюм", "подарок", "цветы", "wb", "wildberries", "ozon", "али", "aliexpress", "платье", "юбка", "костюм", "рубашка", "шапка", "перчатки", "сумка", "рюкзак", "ремень", "очки", "украшения", "кольцо", "часы"],
    "связь": ["баланс", "телефон", "мобильный", "тариф", "мтс", "мегафон", "билайн", "ош", "мега", "beeline", "o!", "теле2", "ростелеком", "домру", "связной", "евросеть"],
}

def guess_category(text: str) -> str:
    """
    Пытается угадать категорию по тексту описания.
    Возвращает название категории (с большой буквы) или None.
    """
    text_lower = text.lower()
    # Убираем знаки препинания и разбиваем на слова
    words = ''.join(c if c.isalnum() else ' ' for c in text_lower).split()
    
    for category, keywords in SMART_TAGS.items():
        for word in words:
            if word in keywords:
                return category.capitalize()
    return None


# =========================
# 💰 БАЗОВАЯ МАТЕМАТИКА
# =========================

def calculate_daily_limit(balance: int, reserve: int, goal: int, living_minimum: int, days: int) -> float:
    if days <= 0:
        return 0.0

    # 1. Сначала считаем только свободные деньги
    available = balance - reserve - goal - living_minimum

    # 2. Если свободных нет, залезаем в копилку (goal)
    if available <= 0:
        available = balance - reserve - living_minimum

    # 3. Если и копилки нет, залезаем в резерв (reserve)
    if available <= 0:
        available = balance - living_minimum

    return max(0.0, available / days)


def get_purchase_verdict(amount: int, daily_limit: float):
    if amount <= daily_limit:
        return "approved", "✅ Одобрено. Вписываешься в план."

    elif amount > daily_limit * 1.5:
        return "blocked", f"⛔ Слишком дорого. Лимит: {daily_limit:.0f}"

    else:
        return "warning", "⚠️ Выше лимита. Завтра будет сложнее."


def get_health_bar(current: float, total: float) -> str:
    """
    Генерирует визуальную полоску здоровья на основе дневного лимита.
    """
    # Если лимита нет (0) или мы в минусе — здоровье 0
    if total <= 0:
        return "💔 [░░░░░░░░░░] 0%\n<i>☠️ Лимит не определен или исчерпан.</i>"

    percent = (current / total) * 100
    
    # Ограничиваем для визуала
    display_percent = max(0, min(100, percent))
    
    # Визуальная полоска (10 блоков) - используем округление для точности
    blocks = round(display_percent / 10)
    bar = "█" * blocks + "░" * (10 - blocks)
    
    # Настроение и иконка
    if percent >= 100:
        mood = "😇 Идеально. Ты экономишь!"
        heart = "💎"
    elif percent >= 70:
        mood = "😎 Всё под контролем."
        heart = "💚"
    elif percent >= 40:
        mood = "🤨 Жить можно. Пока что."
        heart = "💛"
    elif percent > 0:
        mood = "😰 Эй, полегче! Денег мало!"
        heart = "🧡"
    else:
        mood = "💀 Дневной лимит убит."
        heart = "💔"

    return f"{heart} <b>Здоровье дня:</b>\n[{bar}] {display_percent:.0f}%\n<i>{mood}</i>"


# =========================
# 📉 ПРОГНОЗ
# =========================

def get_survival_forecast(amount: int, daily_limit: float) -> str:
    if daily_limit <= 0:
        return "Баланс на нуле — любая трата ведет к долгам."

    impact_days = int(amount / daily_limit)

    if impact_days > 1:
        return f"Покупка съедает {impact_days} дней бюджета."
    return "Все стабильно."


def get_survival_days(balance, reserve, goal, living_minimum, amount, daily_limit):
    if daily_limit <= 0:
        return 0

    new_balance = balance - amount

    # Используем fallback-логику (свободно -> копилка -> резерв)
    available = new_balance - reserve - goal - living_minimum
    if available <= 0:
        available = new_balance - reserve - living_minimum
    if available <= 0:
        available = new_balance - living_minimum

    if available <= 0:
        return 0

    return int(available / daily_limit)


def get_burn_days(balance, reserve, goal, living_minimum, daily_limit):
    # Используем fallback-логику
    available = balance - reserve - goal - living_minimum
    if available <= 0:
        available = balance - reserve - living_minimum
    if available <= 0:
        available = balance - living_minimum

    if daily_limit <= 0 or available <= 0:
        return 0

    return int(available / daily_limit)


# =========================
# 🔥 АНАЛИТИКА
# =========================

def get_mistake_cost(balance, reserve, goal, living_minimum, days, amount):
    if days <= 1:
        return {"new_limit": 0, "drop_percent": 100}

    current = calculate_daily_limit(balance, reserve, goal, living_minimum, days)

    new_balance = balance - amount
    new_limit = calculate_daily_limit(new_balance, reserve, goal, living_minimum, days - 1)

    if current > 0:
        drop = ((current - new_limit) / current) * 100
    else:
        drop = 100

    return {
        "new_limit": round(new_limit, 2),
        "drop_percent": round(drop, 1)
    }


def get_risk_level(drop_percent):
    if drop_percent < 20:
        return "🟢 Низкий"
    elif drop_percent < 50:
        return "🟡 Средний"
    else:
        return "🔴 Высокий"


def get_safe_spending(daily_limit):
    return round(daily_limit * 0.8, 2)


# =========================
# 🤖 ГЛАВНЫЙ ОТВЕТ
# =========================

def build_smart_response(balance, reserve, goal, days, amount, living_minimum=15000,fixed_limit=None):
    if fixed_limit is not None:
        daily_limit = fixed_limit
    else:
        daily_limit = calculate_daily_limit(
            balance, reserve, goal, living_minimum, days
        )

    verdict_type, verdict_text = get_purchase_verdict(amount, daily_limit)

    forecast = get_survival_forecast(amount, daily_limit)

    mistake = get_mistake_cost(balance, reserve, goal, living_minimum, days, amount)

    days_left = get_survival_days(
        balance, reserve, goal, living_minimum, amount, daily_limit
    )

    burn_days = get_burn_days(
        balance, reserve, goal, living_minimum, daily_limit
    )

    risk = get_risk_level(mistake["drop_percent"])

    safe_spend = get_safe_spending(daily_limit)

    available = balance - reserve - goal - living_minimum

    response = f"{verdict_text}\n\n"

    # 💰 реальность
    if available < 0:
        # Пытаемся залезть в копилку/резерв
        if balance - living_minimum > 0:
            response += (
                f"💰 <b>Свободно:</b> 0 сом\n"
                f"⚠️ Ты используешь <b>резервы/копилку</b>.\n\n"
            )
        else:
            response += (
                f"💰 <b>Свободно:</b> 0 сом\n"
                f"⚠️ Ты уже в дефиците: {abs(available)} сом\n\n"
            )
    else:
        response += (
            f"💰 <b>Свободно:</b> {available} сом\n\n"
        )

    # 📉 прогноз
    response += f"📉 <b>Что будет дальше:</b>\n{forecast}\n\n"

    # 📊 анализ
    response += "📊 <b>Анализ:</b>\n"
    response += f"• Лимит: {daily_limit:.0f}\n"
    response += f"• После покупки: {mistake['new_limit']}\n"
    response += f"• Просадка: {mistake['drop_percent']}%\n"
    response += f"• Риск: {risk}\n"

    # 😏 характер
    if verdict_type == "approved":
        response += "\n😌 Всё под контролем."
    elif verdict_type == "warning":
        response += "\n🤨 Уже на грани."
    else:
        response += "\n🚫 Я бы не стал."

    # 🚨 минимум
    if balance < living_minimum:
        response += "\n\n⚠️ У тебя даже нет денег на базовую жизнь."

    if balance - amount < living_minimum:
        response += "\n🚨 Ты залезаешь в деньги на жизнь."

    # 🚨 копилка
    if balance - amount < reserve + goal:
        response += "\n🚨 Ты трогаешь копилку."

    # ⏳ прогноз
    if days_left <= 0:
        response += "\n\n☠️ Деньги закончатся."
    else:
        response += f"\n\n⏳ Хватит на: {days_left} дн."

    # 💡 советы
    response += "\n\n💡 <b>Совет:</b>\n"
    response += f"— Безопасно тратить: {safe_spend}\n"

    if burn_days > 0:
        response += f"— При таком темпе деньги закончатся через: {burn_days} дн.\n"

    # Добавляем инфо о свободном остатке после покупки
    remaining_available = max(0, available - amount)
    response += f"\n💰 <b>Остаток свободных денег: {remaining_available} сом</b>"

    return verdict_type, response


def parse_time_duration(text: str) -> int:
    """
    Парсит строку и возвращает количество дней.
    Поддерживает: 
    - числа (10, 20)
    - дни (5 дней, 1 день)
    - месяцы (1 месяц, 2 месяца)
    - годы (1 год)
    """
    import re
    text = text.lower().strip()
    
    # Если просто число
    if text.isdigit():
        return int(text)
    
    # Ищем число и слово
    match = re.search(r"(\d+)\s*([а-яё]+)", text)
    if not match:
        return None
    
    value = int(match.group(1))
    unit = match.group(2)
    
    if any(x in unit for x in ["мес", "мес"]):
        return value * 30
    elif any(x in unit for x in ["год", "лет"]):
        return value * 365
    elif any(x in unit for x in ["ден", "дня", "дне"]):
        return value
    
    return value


def calculate_fixed_limit(balance, reserve, goal, living_minimum):
    """
    Рассчитывает фиксированный дневной лимит
    """

    # 1. Сначала считаем только свободные деньги
    available = balance - reserve - goal - living_minimum

    # 2. Если свободных нет, залезаем в копилку (goal)
    if available <= 0:
        available = balance - reserve - living_minimum

    # 3. Если и копилки нет, залезаем в резерв (reserve)
    if available <= 0:
        available = balance - living_minimum

    if available <= 0:
        return 0.0

    # адаптивный процент
    if balance < 3000:
        percent = 0.10
    elif balance < 20000:
        percent = 0.07
    else:
        percent = 0.05

    return round(available * percent, 2)