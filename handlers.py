from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
import re

import logic
import database
import visuals

from datetime import datetime

router = Router()

# 🔥 базовый минимум
daily_minimum = 500


# =========================
# 🧠 СИНХРОНИЗАЦИЯ ЛИМИТА
# =========================
async def sync_user_limit(user_id: int):
    """
    Начисляет лимит за прошедшие дни
    """
    data = await database.get_user(user_id)
    if not data: return None

    last_sync = datetime.strptime(data["last_sync"], "%Y-%m-%d").date()
    today = datetime.now().date()
    
    delta = (today - last_sync).days

    if delta > 0:
        # Начисляем лимит за каждый прошедший день
        new_pool = data["daily_pool"] + (data["fixed_limit"] * delta)
        # Уменьшаем количество дней до дохода
        new_days = max(0, data["days"] - delta)
        
        await database.save_user(
            user_id, data["balance"], new_days, data["reserve"], 
            data["goal"], data["fixed_limit"], new_pool
        )
        return await database.get_user(user_id)
    
    return data


# =========================
# 🧠 АДАПТИВНЫЙ МИНИМУМ
# =========================
def get_adaptive_minimum(balance: int, days: int, daily_minimum: int = 500):
    base = daily_minimum * days

    if balance < 3000:
        return int(balance * 0.3)
    elif balance < 20000:
        return int(balance * 0.5)

    return base


# =========================
# СОСТОЯНИЯ
# =========================
class SetupState(StatesGroup):
    weighting_for_balance = State()
    weighting_for_date = State()
    weighting_for_reserve = State()
    weighting_for_goal = State()
    topup_amount = State()
    waiting_for_new_date = State()
    waiting_for_new_goal = State()


# =========================
# 📺 ПОДПИСКИ / СЧЕТА
# =========================

@router.message(Command("bill"))
async def cmd_bill(message: types.Message):
    # Если просто /bill - показываем список
    args = message.text.split()
    if len(args) == 1:
        subs = await database.get_subscriptions(message.from_user.id)
        if not subs:
            return await message.answer(
                "📺 У тебя пока нет подписок.\n"
                "Чтобы добавить, пиши:\n"
                "<code>/bill 500 Netflix</code>"
            )
        
        text = "📺 <b>Твои регулярные счета:</b>\n\n"
        for s_id, amount, desc in subs:
            text += f"• {amount} — {desc} (ID: {s_id})\n"
        
        text += f"\n🗑 Чтобы удалить: <code>/delbill [ID]</code>"
        return await message.answer(text)

    # Если /bill 500 описание - добавляем
    if len(args) < 3:
        return await message.answer("❌ Пиши: <code>/bill [сумма] [описание]</code>")

    if not args[1].isdigit():
        return await message.answer("❌ Сумма должна быть числом")

    amount = int(args[1])
    desc = " ".join(args[2:])
    
    await database.add_subscription(message.from_user.id, amount, desc)
    await message.answer(f"✅ Добавлена подписка: {desc} ({amount} сом/мес)")
    
    # После добавления подписки пересчитаем лимит
    data = await database.get_user(message.from_user.id)
    if data:
        total_bills = await database.get_total_subscriptions(message.from_user.id)
        living_minimum = get_adaptive_minimum(data["balance"], data["days"], daily_minimum)
        
        # Вычитаем счета из расчета лимита
        new_fixed_limit = logic.calculate_fixed_limit(
            data["balance"] - total_bills, data["reserve"], data["goal"], living_minimum
        )
        await database.save_user(
            message.from_user.id, data["balance"], data["days"], data["reserve"], data["goal"], new_fixed_limit
        )
        await message.answer(f"🔄 Лимит пересчитан с учетом счетов: {new_fixed_limit}")


@router.message(Command("delbill"))
async def cmd_delbill(message: types.Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return await message.answer("❌ Пиши: <code>/delbill [ID]</code>")

    await database.delete_subscription(int(args[1]))
    await message.answer("🗑 Подписка удалена")


@router.message(Command("wishlist"))
async def cmd_wishlist(message: types.Message):
    wishes = await database.get_wishlist(message.from_user.id)
    if not wishes:
        return await message.answer("🎁 Твой список желаний пуст. Самое время что-то захотеть! Используй /want")

    text = "🎁 <b>Твой список желаний:</b>\n\n"
    for w_id, amount, item_name, ts in wishes:
        text += f"• {item_name} — {amount} сом (ID: {w_id})\n"
    
    text += f"\n🗑 Чтобы удалить: <code>/delwish [ID]</code>"
    await message.answer(text)


@router.message(Command("delwish"))
async def cmd_delwish(message: types.Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return await message.answer("❌ Пиши: <code>/delwish [ID]</code>")

    await database.delete_wish(int(args[1]))
    await message.answer("🗑 Желание удалено из списка.")


@router.message(Command("want"))
async def cmd_want(message: types.Message):
    args = message.text.split()
    if len(args) < 3:
        return await message.answer(
            "🛡 <b>Защита от трат:</b>\n\n"
            "Пиши: <code>/want [сумма] [название]</code>\n"
            "Пример: <code>/want 8000 Кроссовки</code>"
        )

    if not args[1].isdigit():
        return await message.answer("❌ Сумма должна быть числом")

    amount = int(args[1])
    item_name = " ".join(args[2:])
    user_id = message.from_user.id

    data = await database.get_user(user_id)
    if not data:
        return await message.answer("Сначала сделай /start")

    # Математика: сколько дней нужно откладывать (допустим 20% от лимита)
    daily_saving = data["fixed_limit"] * 0.2
    
    if daily_saving <= 0:
        days = "бесконечно (лимит 0)"
    else:
        days = round(amount / daily_saving)

    await database.add_wish(user_id, amount, item_name)

    await message.answer(
        f"🛡 <b>Хотелка добавлена в лист ожидания!</b>\n\n"
        f"🎁 Предмет: {item_name}\n"
        f"💰 Цена: {amount}\n"
        f"⏳ Срок выдержки: <b>{days} дн.</b>\n\n"
        f"Я буду напоминать тебе о ней каждое утро. Если через {days} дней ты всё еще будешь её хотеть — купишь! 😉"
    )


@router.message(Command("undo"))
async def cmd_undo(message: types.Message):
    user_id = message.from_user.id
    
    # 1. Получаем и удаляем последнюю запись
    last_tx = await database.pop_last_transaction(user_id)
    if not last_tx:
        return await message.answer("⚠️ Твоя история пуста, отменять нечего.")

    # 2. Получаем текущие данные пользователя
    data = await database.get_user(user_id)
    if not data:
        return await message.answer("Ошибка пользователя.")

    amount = last_tx["amount"]
    desc = last_tx["description"]

    # 3. Возвращаем деньги на баланс и в пул
    new_balance = data["balance"] + amount
    new_pool = data["daily_pool"] + amount
    
    await database.update_balance(user_id, new_balance)
    await database.update_daily_pool(user_id, new_pool)

    await message.answer(
        f"♻️ <b>Отмена выполнена!</b>\n\n"
        f"Удалено: <code>{amount} - {desc}</code>\n"
        f"💰 Деньги возвращены на баланс и в сегодняшний лимит."
    )


@router.message(Command("limit"))
async def cmd_limit(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.answer(
            "📈 <b>Настройка лимита:</b>\n\n"
            "Пиши: <code>/limit [сумма]</code>\n"
            "Пример: <code>/limit 1000</code>\n\n"
            "Это установит фиксированную сумму, которую ты можешь тратить каждый день."
        )

    if not args[1].isdigit():
        return await message.answer("❌ Сумма должна быть числом")

    new_limit = float(args[1])
    user_id = message.from_user.id
    
    data = await database.get_user(user_id)
    if not data:
        return await message.answer("Сначала сделай /start")

    # Обновляем и фиксированный шаг, и текущий доступный пул
    old_limit = data["fixed_limit"]
    await database.save_user(
        user_id, 
        data["balance"], 
        data["days"], 
        data["reserve"], 
        data["goal"], 
        new_limit, 
        new_limit # Сразу обновляем и сегодняшний лимит
    )

    await message.answer(
        f"📈 <b>Лимит обновлен!</b>\n\n"
        f"📉 Было: {old_limit:.0f} сом\n"
        f"🚀 Стало: <b>{new_limit:.0f} сом</b>\n\n"
        f"Теперь это твой ежедневный бюджет. 😈"
    )


# =========================
# 📊 ОТЧЕТЫ
# =========================

@router.message(Command("report"))
async def cmd_report(message: types.Message):
    user_id = message.from_user.id
    data = await database.get_user(user_id)
    if not data:
        return await message.answer("Сначала сделай /start")

    # 1. Получаем траты из транзакций
    stats = await database.get_category_stats(user_id)
    # Превращаем в список для модификации
    stats = [list(item) for item in stats]

    # 2. Добавляем подписки (счета)
    total_bills = await database.get_total_subscriptions(user_id)
    if total_bills > 0:
        stats.append(["подписки", total_bills, "Счета"])

    # 3. Считаем итого и свободный остаток
    total_spent = sum(item[1] for item in stats)
    
    living_minimum = get_adaptive_minimum(data["balance"], data["days"], daily_minimum)
    available = data["balance"] - data["reserve"] - data["goal"] - living_minimum
    
    # Добавим "Свободно" как отдельный сектор для диаграммы
    if available > 0:
        stats.append(["свободно", available, "Остаток"])

    if not stats:
        return await message.answer("📉 Пока нет данных для отчета.")

    # Эмодзи для категорий
    category_icons = {
        "еда": "🍔",
        "транспорт": "🚕",
        "жилье": "🏠",
        "развлечения": "🎉",
        "здоровье": "💊",
        "шопинг": "🛍️",
        "связь": "📱",
        "подписки": "📺",
        "свободно": "💰",
        "прочее": "📦"
    }

    report_text = "📊 <b>Полный обзор бюджета:</b>\n\n"
    
    grand_total = total_spent + max(0, available)
    
    for category, amount, count_info in stats:
        icon = category_icons.get(category.lower(), "💰")
        percent = (amount / grand_total) * 100 if grand_total > 0 else 0
        
        # Для "Подписок" и "Свободно" count_info это строка
        if isinstance(count_info, int):
            info_str = f"└ <i>{count_info} операций</i>"
        else:
            info_str = f"└ <i>{count_info}</i>"
            
        report_text += f"{icon} <b>{category.capitalize()}</b>: {amount:.0f} сом ({percent:.1f}%)\n{info_str}\n\n"

    report_text += f"💵 <b>Всего расходов: {total_spent:.0f} сом</b>"
    
    # Генерация графика
    chart_buffer = visuals.create_category_pie_chart(stats)
    
    if chart_buffer:
        photo = BufferedInputFile(chart_buffer.read(), filename="report.png")
        await message.answer_photo(photo=photo, caption=report_text)
    else:
        await message.answer(report_text)


# =========================
# КОМАНДЫ
# =========================

@router.message(Command("reset"))
async def cmd_reset(message: types.Message, state: FSMContext):
    await database.delete_user_data(message.from_user.id)
    await state.clear()
    await message.answer("🗑 Все данные удалены. Начни заново: /start")


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "👋 Привет! Я FinGuard 😈\n\n"
        "Я защищаю твои деньги от тебя самого.\n\n"
        "💰 Сколько у тебя сейчас денег?"
    )
    await state.set_state(SetupState.weighting_for_balance)


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "💡 Как пользоваться:\n\n"
        "Пиши покупку:\n"
        "<code>500 еда</code>\n"
        "<code>1000 такси #транспорт</code>\n\n"
        "/status — состояние\n"
        "/report — аналитика трат\n"
        "/limit [сумма] — ручная настройка лимита\n"
        "/goal [сумма] — изменить копилку\n"
        "/date [срок] — изменить дату дохода\n"
        "/want [сумма] [цель] — добавить хотелку\n"
        "/wishlist — список желаний\n"
        "/undo — отмена последней траты\n"
        "/reset — сброс"
    )


@router.message(Command("status"))
async def cmd_status(message: types.Message):
    data = await sync_user_limit(message.from_user.id)
    if not data:
        return await message.answer("Сначала сделай /start")

    # Получаем историю
    history = await database.get_history(message.from_user.id, limit=5)
    history_text = ""
    for h in history:
        # Пытаемся красиво вывести историю
        history_text += f"• {h[0]} - {h[1]}\n"
    
    if not history_text: history_text = "Пока пусто"

    balance = data["balance"]
    days = data["days"]
    reserve = data["reserve"]
    goal = data["goal"]
    daily_pool = data["daily_pool"]

    living_minimum = get_adaptive_minimum(balance, days, daily_minimum)
    
    # 1. Сначала считаем свободные деньги
    available = balance - reserve - goal - living_minimum

    # Для отображения в интерфейсе, если available < 0, показываем 0, 
    # так как пользователь перешел на резервы
    display_available = max(0, available)

    # Визуальное тамагочи на основе дневного лимита
    health_bar = logic.get_health_bar(daily_pool, data["fixed_limit"])

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💸 Пополнить", callback_data="topup"),
            InlineKeyboardButton(text="📅 Срок дохода", callback_data="change_date")
        ],
        [
            InlineKeyboardButton(text="🎯 Изменить копилку", callback_data="change_goal")
        ]
    ])

    await message.answer(
        f"📊 <b>Статус:</b>\n\n"
        f"💰 Баланс: {balance}\n"
        f"🛟 Резерв: {reserve}\n"
        f"🎯 Копилка: {goal}\n"
        f"🍜 Минимум: {living_minimum}\n\n"
        f"💸 <b>Свободно для трат: {display_available}</b>\n"
        f"📅 Дней до дохода: {days}\n"
        f"💵 <b>Доступно сегодня: {daily_pool:.0f}</b>\n"
        f"📈 Дневной шаг: {data['fixed_limit']:.0f}\n\n"
        f"{health_bar}\n\n"
        f"📜 <b>Последние траты:</b>\n{history_text}",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "change_goal")
async def change_goal_button(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🎯 Сколько ты хочешь оставить на следующий месяц?")
    await state.set_state(SetupState.waiting_for_new_goal)
    await callback.answer()


@router.message(Command("goal"))
async def cmd_goal(message: types.Message, state: FSMContext):
    await message.answer("🎯 Сколько ты хочешь оставить на следующий месяц?")
    await state.set_state(SetupState.waiting_for_new_goal)


@router.message(SetupState.waiting_for_new_goal)
async def process_new_goal(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ Введи число")

    new_goal = int(message.text)
    user_id = message.from_user.id
    data = await database.get_user(user_id)
    if not data: return await state.clear()

    old_goal = data["goal"]
    
    # Пересчитываем лимит
    total_bills = await database.get_total_subscriptions(user_id)
    living_minimum = get_adaptive_minimum(data["balance"], data["days"], daily_minimum)
    
    new_fixed_limit = logic.calculate_fixed_limit(
        data["balance"] - total_bills, data["reserve"], new_goal, living_minimum
    )

    # Сохраняем (пул тоже обнуляем, так как план поменялся)
    await database.save_user(
        user_id, data["balance"], data["days"], data["reserve"], new_goal, new_fixed_limit,
        daily_pool=new_fixed_limit 
    )

    await message.answer(
        f"🎯 <b>Копилка обновлена!</b>\n\n"
        f"📉 Было: {old_goal} сом\n"
        f"🚀 Стало: <b>{new_goal} сом</b>\n\n"
        f"🔄 Новый лимит на день: <b>{new_fixed_limit:.0f}</b>\n"
        f"Бюджет перестроен под твои цели. 😈📉"
    )
    await state.clear()


@router.callback_query(F.data == "change_date")
async def change_date_button(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📅 Через сколько дней теперь ожидается доход?\n(Напиши, например: 10, или '1 месяц')")
    await state.set_state(SetupState.waiting_for_new_date)
    await callback.answer()


@router.message(Command("date"))
async def cmd_date(message: types.Message, state: FSMContext):
    await message.answer("📅 Через сколько дней теперь ожидается доход?")
    await state.set_state(SetupState.waiting_for_new_date)


@router.message(SetupState.waiting_for_new_date)
async def process_new_date(message: types.Message, state: FSMContext):
    days = logic.parse_time_duration(message.text)
    
    if days is None:
        return await message.answer("❌ Не понимаю. Напиши число или, например, '1 месяц'")

    user_id = message.from_user.id
    data = await database.get_user(user_id)
    if not data: return await state.clear()

    # Пересчитываем лимит с новыми днями
    old_days = data["days"]
    total_bills = await database.get_total_subscriptions(user_id)
    living_minimum = get_adaptive_minimum(data["balance"], days, daily_minimum)
    
    new_fixed_limit = logic.calculate_fixed_limit(
        data["balance"] - total_bills, data["reserve"], data["goal"], living_minimum
    )

    # Сохраняем (пул тоже обнуляем до дневного, так как план поменялся)
    await database.save_user(
        user_id, data["balance"], days, data["reserve"], data["goal"], new_fixed_limit,
        daily_pool=new_fixed_limit 
    )

    await message.answer(
        f"📅 <b>Срок изменен!</b>\n\n"
        f"⏳ Было: {old_days} дн.\n"
        f"🚀 Стало: <b>{days} дн.</b>\n\n"
        f"🔄 Новый дневной лимит: <b>{new_fixed_limit:.0f}</b>\n\n"
        f"План перестроен под новую дату. 😈📈"
    )
    await state.clear()


@router.callback_query(F.data == "topup")
async def topup_button(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("💸 Введи сумму пополнения:")
    await state.set_state(SetupState.topup_amount)
    await callback.answer()


@router.message(Command("topup"))
async def cmd_topup(message: types.Message, state: FSMContext):
    await message.answer("💸 Сколько хочешь добавить к балансу?")
    await state.set_state(SetupState.topup_amount)


@router.message(SetupState.topup_amount)
async def process_topup(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ Введи число")

    amount = int(message.text)
    user_id = message.from_user.id
    data = await database.get_user(user_id)

    if not data:
        await state.clear()
        return await message.answer("Сначала сделай /start")

    new_balance = data["balance"] + amount
    old_balance = data["balance"]
    
    # Автоматический пересчет лимита при пополнении
    total_bills = await database.get_total_subscriptions(user_id)
    living_minimum = get_adaptive_minimum(new_balance, data["days"], daily_minimum)
    
    # Счета вычитаются из баланса ПЕРЕД расчетом лимита
    new_fixed_limit = logic.calculate_fixed_limit(
        new_balance - total_bills, data["reserve"], data["goal"], living_minimum
    )

    await database.save_user(
        user_id, new_balance, data["days"], data["reserve"], data["goal"], new_fixed_limit
    )

    available = new_balance - data["reserve"] - data["goal"] - living_minimum
    display_available = max(0, available)

    await message.answer(
        f"💰 <b>Баланс пополнен!</b>\n\n"
        f"➖ Было: {old_balance} сом\n"
        f"🚀 Стало: <b>{new_balance} сом</b>\n"
        f"➕ Сумма: +{amount}\n\n"
        f"💸 Свободно для трат: {display_available}\n"
        f"🔄 Новый лимит: {new_fixed_limit:.0f}"
    )
    await state.clear()


@router.message(SetupState.weighting_for_balance)
async def get_balance(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Введи число")
    await state.update_data(balance=int(message.text))
    await message.answer("📅 Через сколько дней доход?")
    await state.set_state(SetupState.weighting_for_date)


@router.message(SetupState.weighting_for_date)
async def get_days(message: types.Message, state: FSMContext):
    days = logic.parse_time_duration(message.text)
    
    if days is None:
        return await message.answer("❌ Не понимаю. Напиши, например: '10 дней', '1 месяц' или '2 года'")
        
    await state.update_data(days=days)
    await message.answer(f"✅ Понял: {days} дн. до дохода.\n\n🛟 Резерв (подушка безопасности)?")
    await state.set_state(SetupState.weighting_for_reserve)


@router.message(SetupState.weighting_for_reserve)
async def get_reserve(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Введи число")
    reserve = int(message.text)
    data = await state.get_data()
    if reserve >= data["balance"]:
        return await message.answer("Резерв не может быть больше баланса")
    await state.update_data(reserve=reserve)
    await message.answer("🎯 Сколько хочешь оставить на следующий месяц? (это уйдет в копилку)")
    await state.set_state(SetupState.weighting_for_goal)


@router.message(SetupState.weighting_for_goal)
async def get_goal(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Введи число")
    goal = int(message.text)
    data = await state.get_data()

    living_minimum = get_adaptive_minimum(data["balance"], data["days"], daily_minimum)
    fixed_limit = logic.calculate_fixed_limit(
        data["balance"], data["reserve"], goal, living_minimum
    )

    available = data["balance"] - data["reserve"] - goal - living_minimum
    display_available = max(0, available)

    await database.save_user(
        message.from_user.id, data["balance"], data["days"], data["reserve"], goal, fixed_limit,
        daily_pool=fixed_limit # Изначально пул равен дневному лимиту
    )

    await message.answer(
        f"🔥 Готово!\n\n"
        f"💰 Баланс: {data['balance']}\n"
        f"🛟 Резерв: {data['reserve']}\n"
        f"🎯 Копилка: {goal}\n"
        f"🍜 Минимум: {living_minimum}\n\n"
        f"💸 <b>Свободно для трат: {display_available} сом</b>\n"
        f"💵 Лимит (фикс): {fixed_limit}\n\n"
        f"Теперь я контролирую твои финансы 😈"
    )
    await state.clear()


@router.message(F.text)
async def process_purchase(message: types.Message):
    data = await sync_user_limit(message.from_user.id)
    if not data:
        return

    match = re.search(r"(\d+)", message.text)
    if not match:
        return

    amount = int(match.group(1))
    text_part = message.text.replace(str(amount), "").strip()

    # Извлекаем категорию
    category = "Прочее"
    description = text_part or "Трата"

    hash_match = re.search(r"#(\w+)", text_part)
    if hash_match:
        # 1. Приоритет — явный хэштег
        category = hash_match.group(1).lower().capitalize()
        description = text_part.replace(f"#{category.lower()}", "").strip() or "Трата"
    elif text_part:
        # 2. Умный поиск по тегам
        guessed = logic.guess_category(text_part)
        if guessed:
            category = guessed
            description = text_part
        else:
            # 3. По старинке: первое слово
            parts = text_part.split()
            if parts:
                category = parts[0].lower().capitalize()
                description = " ".join(parts[1:]) if len(parts) > 1 else parts[0]

    balance = data["balance"]
    living_minimum = get_adaptive_minimum(balance, data["days"], daily_minimum)

    # Используем daily_pool как текущий лимит
    verdict_type, response = logic.build_smart_response(
        balance, data["reserve"], data["goal"], data["days"], amount, 
        living_minimum=living_minimum, fixed_limit=data["daily_pool"]
    )

    if verdict_type == "approved":
        await database.update_balance(message.from_user.id, balance - amount)
        await database.log_transaction(message.from_user.id, amount, description, category)
        # Списываем из дневного пула
        await database.update_daily_pool(message.from_user.id, data["daily_pool"] - amount)

    if verdict_type != "approved":
        # Telegram callback_data limit is 64 bytes. 
        # Truncate strings to ensure they fit.
        safe_desc = description[:20] 
        safe_cat = category[:15]
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💸 Всё равно купить", callback_data=f"buy:{amount}:{safe_desc}:{safe_cat}")]
        ])
        await message.answer(response, reply_markup=keyboard)
    else:
        await message.answer(response)


@router.callback_query(F.data.startswith("buy:"))
async def force_buy(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    amount = int(parts[1])
    description = parts[2]
    category = parts[3] if len(parts) > 3 else "Прочее"

    data = await database.get_user(callback.from_user.id)
    if not data: return

    await database.update_balance(callback.from_user.id, data["balance"] - amount)
    await database.log_transaction(callback.from_user.id, amount, description, category)
    # Списываем из дневного пула (может уйти в минус!)
    await database.update_daily_pool(callback.from_user.id, data["daily_pool"] - amount)

    await callback.message.answer(f"💸 Ладно... ты купил это в категорию {category}.\nЯ тебя предупреждал 😐")
    await callback.answer()
