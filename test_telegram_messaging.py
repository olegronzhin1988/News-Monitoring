import asyncio
from app.services.telegram_notifier import send_telegram_message

async def test():
    result = await send_telegram_message("Тестовое сообщение от News Monitoring")
    print(f"Sent: {result}")

asyncio.run(test())