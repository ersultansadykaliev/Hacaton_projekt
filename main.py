import asyncio
import logging
import sys
from datetime import datetime, time

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from config import BOT_TOKEN
from handlers import router, sync_user_limit
import database


# --- МЕНЮ КОМАНД ---
async def set_main_menu(bot: Bot):
    commands = [
        BotCommand(command="/start", description="Настроить FinGuard ⚙️"),
        BotCommand(command="/status", description="Финансовое здоровье 📊"),
        BotCommand(command="/report", description="Отчет по категориям 📈"),
        BotCommand(command="/bill", description="Мои подписки 📺"),
        BotCommand(command="/undo", description="Отменить последнюю трату ♻️"),
        BotCommand(command="/limit", description="Установить свой лимит 📈"),
        BotCommand(command="/reset", description="Сброс данных 🗑"),
        BotCommand(command="/topup", description="Пополнить баланс 💸"),
        BotCommand(command="/help", description="Помощь ❓")
    ]
    await bot.set_my_commands(commands)


# --- ПЛАНИРОВЩИК (Scheduler) ---
async def scheduler_loop(bot: Bot):
    """
    Фоновый цикл для отправки утренних отчетов.
    Проверяет время раз в минуту.
    """
    while True:
        now = datetime.now()
        
        # Настраиваем время уведомления (например, 09:00 утра)
        if now.hour == 9 and now.minute == 0:
            logging.info("Запуск утренней рассылки...")
            
            user_ids = await database.get_all_users()
            for user_id in user_ids:
                try:
                    # Синхронизируем лимит (начисляем новый день)
                    data = await sync_user_limit(user_id)
                    if data:
                        text = (
                            f"☕ <b>Доброе утро!</b>\n\n"
                            f"💵 Твой лимит на сегодня: <b>{data['daily_pool']:.0f} сом</b>\n"
                            f"📈 Дневной шаг: {data['fixed_limit']:.0f}\n\n"
                            f"Удачного дня! Не трать лишнего 😈"
                        )
                        await bot.send_message(user_id, text)
                except Exception as e:
                    logging.error(f"Ошибка при отправке уведомления {user_id}: {e}")
            
            # Ждем минуту, чтобы не отправить дважды в одну и ту же минуту
            await asyncio.sleep(61)
        
        # Спим 30 секунд перед следующей проверкой
        await asyncio.sleep(30)


async def main():
    # 🔹 логирование
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        stream=sys.stdout,
    )

    # 🔹 база
    await database.init_db()

    # 🔹 бот
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()
    dp.include_router(router)

    # 🔥 ВАЖНО: очистка старых сообщений (правильное место)
    await bot.delete_webhook(drop_pending_updates=True)

    # 🔹 меню
    await set_main_menu(bot)

    # 🔹 Запуск планировщика в фоне
    asyncio.create_task(scheduler_loop(bot))

    try:
        print("FinGuard запущен с планировщиком 🚀")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
