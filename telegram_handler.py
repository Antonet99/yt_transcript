import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

class TelegramError(Exception):
    """Classe base per le eccezioni di Telegram"""
    pass

def check_bot_status():
    """Verifica lo stato del bot e le sue autorizzazioni"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe"
        response = requests.get(url)
        if not response.ok:
            raise TelegramError(f"Errore nella verifica del bot: {response.text}")
        print("✅ Bot Telegram verificato correttamente")
        
        # Verifica il canale
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChat"
        response = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID})
        if not response.ok:
            raise TelegramError(
                f"Errore nella verifica del canale: {response.text}\n"
                f"Chat ID utilizzato: {TELEGRAM_CHAT_ID}\n"
                "Assicurati che:\n"
                "1. Il bot sia stato aggiunto al canale\n"
                "2. Il bot sia amministratore del canale\n"
                "3. L'ID del canale sia corretto"
            )
        print("✅ Canale Telegram verificato correttamente")
        
        return True
    except Exception as e:
        print(f"❌ Errore nella verifica delle credenziali Telegram: {str(e)}")
        return False

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def send_message_to_channel(text):
    """Invia un messaggio al canale Telegram con retry"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        response = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text})
        
        if not response.ok:
            error_msg = f"Errore nell'invio del messaggio: {response.text}"
            if "chat not found" in response.text.lower():
                error_msg += f"\nChat ID utilizzato: {TELEGRAM_CHAT_ID}"
                error_msg += "\nAssicurati che:\n1. Il bot sia stato aggiunto al canale\n2. Il bot sia amministratore del canale"
            raise TelegramError(error_msg)
        
        return response.json()
    except requests.RequestException as e:
        print(f"❌ Errore di rete nell'invio del messaggio Telegram: {str(e)}")
        raise TelegramError(f"Errore di rete: {str(e)}")
    except Exception as e:
        print(f"❌ Errore generico nell'invio del messaggio Telegram: {str(e)}")
        raise TelegramError(f"Errore generico: {str(e)}")

def process_new_video(video_info, transcript=None, summary=None):
    """Processa un nuovo video e invia le notifiche appropriate"""
    try:
        # Notifica nuovo video
        video_message = (
            f"📢 Nuovo video pubblicato da {video_info['channel_name']}!\n"
            f"🎥 {video_info['title']}\n"
            f"🔗 {video_info['link']}"
        )
        send_message_to_channel(video_message)

        # Se abbiamo un riassunto, invialo
        if summary:
            send_message_to_channel(summary)
        elif transcript is None:
            error_msg = f"❌ Riassunto non disponibile per il video: {video_info['title']}"
            send_message_to_channel(error_msg)
            print(f"⏩ Saltato il riassunto per {video_info['title']} (trascrizione non disponibile)")
    
    except TelegramError as e:
        print(f"❌ Errore nell'invio delle notifiche Telegram: {str(e)}")
        # Non rilanciamo l'errore per permettere al programma di continuare
    except Exception as e:
        print(f"❌ Errore generico nel processing del video: {str(e)}")
        # Non rilanciamo l'errore per permettere al programma di continuare 