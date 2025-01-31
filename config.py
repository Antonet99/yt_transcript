import os
from dotenv import load_dotenv

# Carica le variabili d'ambiente dal file .env
load_dotenv()

# Configurazione canali YouTube
CHANNELS = {
    "Alfredo Pedullà": "UC2v9Tfka3PPWDgy_2TXL6Mg",
    "Romeo Agresti": "UCmlXlTE2oTArVL8DafyRsXA",
    "JTalks": "UCg3fYr4L3C5buwo_5EeopuQ"
}

# Configurazione Telegram
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
# Rimuovi eventuali virgolette dall'ID del canale
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID').strip('"').strip("'")

# Configurazione Gemini AI
GENAI_API_KEY = os.getenv('GENAI_API_KEY')
AI_MODEL = os.getenv('AI_MODEL')
ALT_AI_MODEL = os.getenv('ALT_AI_MODEL', 'gemini-exp-1206')  # Modello alternativo con fallback

# Configurazione Database
POSTGRES_CONFIG = {
    "host": os.getenv('DB_HOST'),
    "port": int(os.getenv('DB_PORT', 5432)),
    "dbname": os.getenv('DB_NAME'),
    "user": os.getenv('DB_USER'),
    "password": os.getenv('DB_PASSWORD')
}

# Carica il prompt di sistema
try:
    with open("system_prompt.txt", "r", encoding="utf-8") as file:
        SYSTEM_INSTRUCTION = file.read().strip()
except FileNotFoundError:
    SYSTEM_INSTRUCTION = ""
    print("⚠️ File system_prompt.txt non trovato. Verrà utilizzato un prompt vuoto.") 