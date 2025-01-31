import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential
from config import GENAI_API_KEY, AI_MODEL, ALT_AI_MODEL, SYSTEM_INSTRUCTION
import time
from datetime import datetime

class AIError(Exception):
    """Classe base per le eccezioni dell'AI"""
    pass

class ContentTooLongError(AIError):
    """Errore specifico per contenuto troppo lungo"""
    pass

# Configurazione del modello
genai.configure(api_key=GENAI_API_KEY)

# Dizionario per tenere traccia dei modelli
models = {
    'primary': genai.GenerativeModel(model_name=AI_MODEL, 
                                   system_instruction=SYSTEM_INSTRUCTION),
    'alternative': genai.GenerativeModel(model_name=ALT_AI_MODEL,
                                       system_instruction=SYSTEM_INSTRUCTION)
}

# Variabile per tenere traccia dell'ultima chiamata
last_api_call = None
RATE_LIMIT_DELAY = 65  # 65 secondi di attesa tra le chiamate

def wait_for_rate_limit():
    """Gestisce il rate limiting per le chiamate API"""
    global last_api_call
    
    if last_api_call is not None:
        # Calcola quanto tempo è passato dall'ultima chiamata
        elapsed = (datetime.now() - last_api_call).total_seconds()
        
        # Se non è passato abbastanza tempo, aspetta
        if elapsed < RATE_LIMIT_DELAY:
            wait_time = RATE_LIMIT_DELAY - elapsed
            print(f"⏳ Attendo {wait_time:.1f} secondi per rispettare il rate limit di Gemini...")
            time.sleep(wait_time)
    
    # Aggiorna il timestamp dell'ultima chiamata
    last_api_call = datetime.now()

def try_generate_summary(model, prompt):
    """Tenta di generare un riassunto con un modello specifico"""
    try:
        response = model.generate_content(prompt)
        if not response.text:
            raise AIError("La risposta dell'AI è vuota")
        return response.text
    except Exception as e:
        error_msg = str(e).lower()
        if "500" in error_msg and "internal error" in error_msg:
            if "context is too long" in error_msg or "reduce your input" in error_msg:
                raise ContentTooLongError("Il contenuto è troppo lungo per questo modello")
        raise

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def get_summary(text, title, video_id=None):
    """Genera il riassunto tramite Gemini AI con retry e fallback su modello alternativo"""
    # Applica il rate limiting
    wait_for_rate_limit()
    
    prompt = f"""Ecco il titolo del video per un maggior contesto: "{title}".     
    Trascrizione:
    {text}
    """
    
    try:
        # Prima prova con il modello primario
        print("🤖 Tentativo di generazione riassunto con modello primario...")
        return try_generate_summary(models['primary'], prompt)
    
    except ContentTooLongError:
        # Se il contenuto è troppo lungo, prova con il modello alternativo
        print("⚠️ Contenuto troppo lungo per il modello primario, provo con il modello alternativo...")
        try:
            return try_generate_summary(models['alternative'], prompt)
        except Exception as e:
            print(f"❌ Errore anche con il modello alternativo: {str(e)}")
            raise AIError(f"Errore nella generazione del riassunto con entrambi i modelli: {str(e)}")
    
    except Exception as e:
        print(f"❌ Errore nella generazione del riassunto AI: {str(e)}")
        raise AIError(f"Errore nella generazione del riassunto: {str(e)}") 