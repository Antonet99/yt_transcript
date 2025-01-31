import psycopg
from tenacity import retry, stop_after_attempt, wait_exponential
from config import POSTGRES_CONFIG

class DatabaseError(Exception):
    """Classe base per le eccezioni del database"""
    pass

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def get_connection():
    """Crea una connessione al database PostgreSQL con retry in caso di errore"""
    try:
        return psycopg.connect(**POSTGRES_CONFIG)
    except psycopg.Error as e:
        raise DatabaseError(f"Errore di connessione al database: {str(e)}")

def init_db():
    """Crea le tabelle se non esistono"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Tabella per lo stato dei canali
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS video_state (
                        channel_id TEXT PRIMARY KEY,
                        channel_name TEXT NOT NULL,
                        last_video_id TEXT NOT NULL
                    )
                ''')

                # Verifica se la colonna channel_name esiste già
                cur.execute('''
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'video_state' AND column_name = 'channel_name'
                ''')
                
                if not cur.fetchone():
                    # Aggiungi la colonna se non esiste
                    print("Aggiunta colonna channel_name alla tabella video_state...")
                    cur.execute('ALTER TABLE video_state ADD COLUMN channel_name TEXT')
                    cur.execute('UPDATE video_state SET channel_name = \'Unknown\'')
                    cur.execute('ALTER TABLE video_state ALTER COLUMN channel_name SET NOT NULL')

                # Tabella per la cache delle trascrizioni
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS transcript_cache (
                        video_id TEXT PRIMARY KEY,
                        transcript TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW(),
                        access_count INTEGER DEFAULT 0
                    )
                ''')

                # Indici per migliorare le performance
                cur.execute('CREATE INDEX IF NOT EXISTS idx_cache_created ON transcript_cache (created_at)')
                cur.execute('CREATE INDEX IF NOT EXISTS idx_cache_access ON transcript_cache (access_count)')

            conn.commit()
    except (psycopg.Error, DatabaseError) as e:
        print(f"❌ Errore durante l'inizializzazione del database: {str(e)}")
        raise

def get_unprocessed_videos():
    """Recupera i video che sono in video_state ma non hanno una trascrizione in cache"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT vs.last_video_id, vs.channel_name, vs.channel_id
                    FROM video_state vs
                    LEFT JOIN transcript_cache tc ON vs.last_video_id = tc.video_id
                    WHERE tc.video_id IS NULL
                ''')
                results = cur.fetchall()
                
                if results:
                    return [{
                        "video_id": row[0],
                        "channel_name": row[1],
                        "channel_id": row[2],
                        "title": f"Video da {row[1]}",  # Titolo generico per retrocompatibilità
                        "link": f"https://www.youtube.com/watch?v={row[0]}"  # Generiamo il link dal video_id
                    } for row in results]
                return []
                
    except (psycopg.Error, DatabaseError) as e:
        print(f"❌ Errore nel recupero dei video non processati: {str(e)}")
        return []

def get_last_video_id(channel_id):
    """Recupera l'ultimo video noto per un dato canale"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT last_video_id FROM video_state WHERE channel_id = %s", (channel_id,))
                result = cur.fetchone()
                return result[0] if result else None
    except (psycopg.Error, DatabaseError) as e:
        print(f"❌ Errore nel recupero dell'ultimo video ID: {str(e)}")
        return None

def update_last_video_id(channel_id, video_id, channel_name):
    """Aggiorna il database con il nuovo video elaborato"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO video_state (channel_id, channel_name, last_video_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (channel_id) 
                    DO UPDATE SET 
                        last_video_id = EXCLUDED.last_video_id,
                        channel_name = EXCLUDED.channel_name
                ''', (channel_id, channel_name, video_id))
            conn.commit()
    except (psycopg.Error, DatabaseError) as e:
        print(f"❌ Errore nell'aggiornamento dell'ultimo video ID: {str(e)}")
        raise

def get_cached_transcript(video_id):
    """Recupera la trascrizione e il riassunto dalla cache"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    UPDATE transcript_cache 
                    SET 
                        access_count = access_count + 1,
                        updated_at = NOW() 
                    WHERE video_id = %s
                    RETURNING transcript, summary
                ''', (video_id,))
                result = cur.fetchone()
                return (result[0], result[1]) if result else (None, None)
    except (psycopg.Error, DatabaseError) as e:
        print(f"❌ Errore nel recupero della trascrizione dalla cache: {str(e)}")
        return None, None

def cache_transcript(video_id, transcript, summary):
    """Salva la trascrizione e il riassunto nella cache"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO transcript_cache (video_id, transcript, summary)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (video_id) 
                    DO UPDATE SET
                        transcript = EXCLUDED.transcript,
                        summary = EXCLUDED.summary,
                        updated_at = NOW()
                ''', (video_id, transcript, summary))
            conn.commit()
    except (psycopg.Error, DatabaseError) as e:
        print(f"❌ Errore nel salvataggio della trascrizione nella cache: {str(e)}")
        raise

def get_videos_to_reprocess():
    """Recupera i video che necessitano di essere riprocessati"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Recupera i video che hanno una trascrizione ma un riassunto con errore
                cur.execute('''
                    SELECT tc.video_id, tc.transcript, vs.channel_name, vs.channel_id
                    FROM transcript_cache tc
                    JOIN video_state vs ON tc.video_id = vs.last_video_id
                    WHERE tc.summary LIKE '⚠️ Riassunto non disponibile%'
                    ORDER BY tc.updated_at DESC
                ''')
                results = cur.fetchall()
                
                if results:
                    return [{
                        "video_id": row[0],
                        "transcript": row[1],
                        "channel_name": row[2],
                        "channel_id": row[3],
                        "title": f"Video da {row[2]}",  # Titolo generico
                        "link": f"https://www.youtube.com/watch?v={row[0]}"  # Link generato dal video_id
                    } for row in results]
                return []
                
    except (psycopg.Error, DatabaseError) as e:
        print(f"❌ Errore nel recupero dei video da riprocessare: {str(e)}")
        return [] 