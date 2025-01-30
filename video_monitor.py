import os
import sqlite3
import feedparser
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import google.generativeai as genai

# -----------------------------------------------------------------------------
# CONFIGURAZIONE
# -----------------------------------------------------------------------------

CHANNELS = {
    "Alfredo Pedullà": "UC2v9Tfka3PPWDgy_2TXL6Mg",
    "Romeo Agresti": "UCmlXlTE2oTArVL8DafyRsXA"
}

# Percorso del database SQLite
DB_FILE = "channel_state.db"

# Credenziali lette da GitHub Actions (Secrets)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GENAI_API_KEY = os.getenv("GENAI_API_KEY")

# Configura il modello Gemini
MODEL = "gemini-2.0-flash-thinking-exp-01-21"
with open("system_prompt.txt", "r", encoding="utf-8") as file:
    SYSTEM_INSTRUCTION = file.read().strip()


# -----------------------------------------------------------------------------
# FUNZIONI: GESTIONE DATABASE SQLITE
# -----------------------------------------------------------------------------

def init_db():
    """Crea il database e la tabella se non esistono"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS video_state (
                    channel_id TEXT PRIMARY KEY,
                    last_video_id TEXT
                )''')
    conn.commit()
    conn.close()

def get_last_video_id(channel_id):
    """Recupera l'ultimo video noto per un dato canale"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT last_video_id FROM video_state WHERE channel_id = ?", (channel_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def update_last_video_id(channel_id, video_id):
    """Aggiorna il database con il nuovo video elaborato"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO video_state (channel_id, last_video_id) VALUES (?, ?) "
              "ON CONFLICT(channel_id) DO UPDATE SET last_video_id = ?",
              (channel_id, video_id, video_id))
    conn.commit()
    conn.close()

# -----------------------------------------------------------------------------
# FUNZIONI: MONITORAGGIO RSS
# -----------------------------------------------------------------------------

def get_latest_videos(channel_id):
    """Recupera gli ultimi video pubblicati tramite RSS"""
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    feed = feedparser.parse(url)

    videos = []
    for entry in feed.entries:
        video_id = getattr(entry, 'yt_videoid', None)
        if video_id:
            videos.append({
                "title": entry.title,
                "link": entry.link,
                "published": entry.published,
                "video_id": video_id
            })
    return videos

def poll_channels(channels):
    """Controlla per nuovi video sui canali"""
    new_videos = []
    for channel_name, channel_id in channels.items():
        last_known_video = get_last_video_id(channel_id)
        videos = get_latest_videos(channel_id)
        if videos:
            latest_video = videos[0]
            latest_video_id = latest_video["video_id"]
            if last_known_video != latest_video_id:
                update_last_video_id(channel_id, latest_video_id)
                new_videos.append({
                    "channel_name": channel_name,
                    "channel_id": channel_id,
                    **latest_video
                })
    return new_videos

# -----------------------------------------------------------------------------
# FUNZIONI: TRASCRIZIONE + AI
# -----------------------------------------------------------------------------

genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel(model_name=MODEL, 
                              system_instruction=SYSTEM_INSTRUCTION)

def get_transcript(video_id, lang='it'):
    """Scarica la trascrizione del video"""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
    except:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
    formatter = TextFormatter()
    return formatter.format_transcript(transcript)

def get_summary(text):
    """Genera il riassunto tramite Gemini AI"""
    response = model.generate_content(f"Riassumi in italiano: {text}")
    return response.text

# -----------------------------------------------------------------------------
# FUNZIONI: INVIO MESSAGGI TELEGRAM
# -----------------------------------------------------------------------------

def send_message_to_channel(text):
    """Invia un messaggio al canale Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text})

def process_new_video(video_info):
    """Pipeline di elaborazione del video"""
    send_message_to_channel(f"📢 Nuovo video pubblicato da {video_info['channel_name']}!\n🎥 {video_info['title']}\n🔗 {video_info['link']}")
    transcript = get_transcript(video_info["video_id"])
    summary = get_summary(transcript)
    send_message_to_channel(summary)

# -----------------------------------------------------------------------------
# AVVIO DEL PROCESSO
# -----------------------------------------------------------------------------

def main_single_run():
    """Avvia il monitoraggio e processa i nuovi video"""
    init_db()
    new_videos = poll_channels(CHANNELS)
    for video_info in new_videos:
        process_new_video(video_info)

if __name__ == "__main__":
    main_single_run()
