# telegram_notifier.py. includes service functions for telegram notices
import httpx
from app.core.config import settings as stngs

# Service function to send notification
async def send_telegram_message(text:str) -> bool:
    # creating telegram request
    url = f"https://api.telegram.org/bot{stngs.TELEGRAM_BOT_TOKEN}/sendMessage"
    headers = {"Content-Type": "application/json"}
    body= {
        "chat_id": stngs.TELEGRAM_CHAT_ID,
        "text": text
        }
    
    # Sending request
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url,
                                     headers=headers,
                                    json=body)
        if response.status_code == 200:
            return True
        else:
            return False