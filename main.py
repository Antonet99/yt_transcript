from db_operations import (init_db, get_cached_transcript, cache_transcript, 
                        get_videos_to_reprocess, get_unprocessed_videos)
from youtube_handler import poll_channels, get_transcript
from telegram_handler import process_new_video, check_bot_status
from ai_handler import get_summary

def process_video_with_cache(video_info):
    """Processa un video utilizzando la cache quando possibile"""
    video_id = video_info["video_id"]
    
    # Prova a recuperare dalla cache
    cached_transcript, cached_summary = get_cached_transcript(video_id)
    
    if cached_transcript and cached_summary:
        # Se il riassunto non contiene un errore
        if not cached_summary.startswith("⚠️ Riassunto non disponibile"):
            print(f"✅ Usando dati dalla cache per {video_info.get('title', video_id)}")
            process_new_video(video_info, cached_transcript, cached_summary)
            return True
        print(f"⚠️ Riassunto in cache non valido per {video_info.get('title', video_id)}, riprovo...")
    
    # Se non in cache o riassunto non valido, scarica e processa
    transcript = video_info.get("transcript") or (get_transcript(video_id)[0] if not cached_transcript else cached_transcript)
    
    if transcript:
        try:
            # Prova a generare il riassunto
            summary = get_summary(transcript, video_info.get("title", "Video senza titolo"), video_id)
            # Salva trascrizione e riassunto in cache
            cache_transcript(video_id, transcript, summary)
            # Processa il video con entrambi
            process_new_video(video_info, transcript, summary)
            return True
        except Exception as e:
            print(f"❌ Errore nel generare il riassunto per {video_info.get('title', video_id)}: {str(e)}")
            # Salva solo la trascrizione con un messaggio di errore come riassunto
            error_summary = f"⚠️ Riassunto non disponibile a causa di un errore: {str(e)}"
            cache_transcript(video_id, transcript, error_summary)
            # Invia la notifica del video con la trascrizione ma senza riassunto
            process_new_video(video_info, transcript, None)
            return False
    else:
        # Se non c'è trascrizione, invia solo la notifica del video
        process_new_video(video_info)
        return True

def process_pending_videos():
    """Processa i video che necessitano di essere riprocessati"""
    pending_videos = get_videos_to_reprocess()
    if pending_videos:
        print(f"🔄 Trovati {len(pending_videos)} video da riprocessare...")
        for video in pending_videos:
            try:
                print(f"🔄 Riprocesso video {video['video_id']}...")
                if process_video_with_cache(video):
                    print(f"✅ Video {video['video_id']} riprocessato con successo")
            except Exception as e:
                print(f"❌ Errore nel riprocessare il video {video['video_id']}: {str(e)}")
    return bool(pending_videos)

def process_unprocessed_videos():
    """Processa i video che non hanno una trascrizione in cache"""
    unprocessed = get_unprocessed_videos()
    if unprocessed:
        print(f"🔄 Trovati {len(unprocessed)} video senza trascrizione...")
        for video in unprocessed:
            try:
                print(f"🔄 Processo video {video['video_id']}...")
                process_video_with_cache(video)
            except Exception as e:
                print(f"❌ Errore nel processare il video {video['video_id']}: {str(e)}")
        return True
    return False

def main_single_run():
    """Avvia il monitoraggio e processa i nuovi video"""
    try:
        # Verifica le credenziali Telegram
        if not check_bot_status():
            print("❌ Impossibile procedere: errore nella verifica delle credenziali Telegram")
            return
            
        # Inizializza il database se necessario
        init_db()
        
        # Prima controlla se ci sono video senza trascrizione
        if not process_unprocessed_videos():
            # Poi controlla se ci sono video da riprocessare
            if not process_pending_videos():
                # Se non ci sono video da riprocessare, controlla nuovi video
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