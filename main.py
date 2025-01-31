from db_operations import init_db, get_cached_transcript, cache_transcript
from youtube_handler import poll_channels, get_transcript
from telegram_handler import process_new_video, check_bot_status
from ai_handler import get_summary

def process_video_with_cache(video_info):
    """Processa un video utilizzando la cache quando possibile"""
    video_id = video_info["video_id"]
    
    # Prova a recuperare dalla cache
    cached_transcript, cached_summary = get_cached_transcript(video_id)
    
    if cached_transcript and cached_summary:
        print(f"✅ Usando dati dalla cache per {video_info['title']}")
        process_new_video(video_info, cached_transcript, cached_summary)
        return
    
    # Se non in cache, scarica e processa
    transcript, from_cache = get_transcript(video_id)
    if transcript:
        try:
            # Prova a generare il riassunto
            summary = get_summary(transcript, video_info["title"], video_id)
            # Salva trascrizione e riassunto in cache
            cache_transcript(video_id, transcript, summary)
            # Processa il video con entrambi
            process_new_video(video_info, transcript, summary)
        except Exception as e:
            print(f"❌ Errore nel generare il riassunto per {video_info['title']}: {str(e)}")
            # Salva solo la trascrizione con un messaggio di errore come riassunto
            error_summary = f"⚠️ Riassunto non disponibile a causa di un errore: {str(e)}"
            cache_transcript(video_id, transcript, error_summary)
            # Invia la notifica del nuovo video con la trascrizione ma senza riassunto
            process_new_video(video_info, transcript, None)
    else:
        # Se non c'è trascrizione, invia solo la notifica del nuovo video
        process_new_video(video_info)

def main_single_run():
    """Avvia il monitoraggio e processa i nuovi video"""
    try:
        # Verifica le credenziali Telegram
        if not check_bot_status():
            print("❌ Impossibile procedere: errore nella verifica delle credenziali Telegram")
            return
            
        # Inizializza il database se necessario
        init_db()
        
        # Controlla nuovi video
        new_videos = poll_channels()
        
        # Processa ogni nuovo video
        for video_info in new_videos:
            try:
                process_video_with_cache(video_info)
            except Exception as e:
                print(f"❌ Errore nel processing del video {video_info['title']}: {str(e)}")
                continue
        
        if not new_videos:
            print("✅ Nessun nuovo video trovato")
            
    except Exception as e:
        print(f"❌ Errore critico nell'esecuzione del programma: {str(e)}")

if __name__ == "__main__":
    main_single_run() 