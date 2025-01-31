import feedparser
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api.formatters import TextFormatter
from tenacity import retry, stop_after_attempt, wait_exponential
from config import CHANNELS
from db_operations import get_last_video_id, update_last_video_id

class YouTubeError(Exception):
    """Classe base per le eccezioni di YouTube"""
    pass

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def get_latest_videos(channel_id):
    """Recupera gli ultimi video pubblicati tramite RSS con retry"""
    try:
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        feed = feedparser.parse(url)
        
        if feed.bozo:  # Controlla se ci sono errori nel feed
            raise YouTubeError(f"Errore nel parsing del feed RSS: {feed.bozo_exception}")
        
        # Recupera il nome del canale dal feed
        channel_name = feed.feed.title if hasattr(feed.feed, 'title') else None
        
        videos = []
        for entry in feed.entries:
            video_id = getattr(entry, 'yt_videoid', None)
            if video_id:
                videos.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published,
                    "video_id": video_id,
                    "channel_name": channel_name
                })
        return videos
    except Exception as e:
        print(f"❌ Errore nel recupero dei video dal canale {channel_id}: {str(e)}")
        raise YouTubeError(f"Errore nel recupero dei video: {str(e)}")

def poll_channels(channels=CHANNELS):
    """Controlla per nuovi video sui canali"""
    new_videos = []
    for config_channel_name, channel_id in channels.items():
        try:
            last_known_video = get_last_video_id(channel_id)
            videos = get_latest_videos(channel_id)
            
            if videos:
                latest_video = videos[0]
                latest_video_id = latest_video["video_id"]
                # Usa il nome del canale dal feed se disponibile, altrimenti usa quello dalla configurazione
                actual_channel_name = latest_video.get("channel_name") or config_channel_name
                
                if last_known_video != latest_video_id:
                    update_last_video_id(channel_id, latest_video_id, actual_channel_name)
                    new_videos.append({
                        "channel_name": actual_channel_name,
                        "channel_id": channel_id,
                        **latest_video
                    })
        except Exception as e:
            print(f"❌ Errore nel polling del canale {config_channel_name}: {str(e)}")
            continue  # Continua con il prossimo canale in caso di errore
    
    return new_videos

def try_get_transcript_with_lang(video_id, lang):
    """Prova a ottenere la trascrizione in una specifica lingua"""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
        print(f"✅ Trascrizione trovata in {lang}")
        return transcript
    except (TranscriptsDisabled, NoTranscriptFound):
        return None

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def get_transcript(video_id, lang='it'):
    """Scarica la trascrizione del video con retry e fallback su inglese"""
    try:
        # Prima prova in italiano
        transcript = try_get_transcript_with_lang(video_id, 'it')
        
        # Se non trova in italiano, prova in inglese
        if transcript is None:
            print("⚠️ Trascrizione in italiano non trovata, provo in inglese...")
            transcript = try_get_transcript_with_lang(video_id, 'en')
        
        # Se non trova in nessuna lingua
        if transcript is None:
            print(f"❌ Trascrizione non disponibile per il video: https://www.youtube.com/watch?v={video_id}")
            return None, False
        
        # Formatta la trascrizione
        formatter = TextFormatter()
        return formatter.format_transcript(transcript), False
        
    except Exception as e:
        print(f"⚠️ Errore nel recuperare la trascrizione per {video_id}: {str(e)}")
        raise YouTubeError(f"Errore nel recupero della trascrizione: {str(e)}") 