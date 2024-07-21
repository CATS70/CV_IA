import os
from pathlib import Path
import json
import requests
from django.conf import settings
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime
import time
import functools

# Définir le chemin d'accès au répertoire racine du projet
BASE_DIR = Path(__file__).resolve().parent.parent

# Définir le chemin d'accès au fichier secrets.json
SECRETS_FILE = BASE_DIR / 'config' / 'secrets.json'

# Définir le chemin d'accès au répertoire data
DATA_DIR = BASE_DIR / 'data'

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(DATA_DIR / 'chatbot.log'),
        logging.StreamHandler()
    ]
)

# Configurez le logger
logger = logging.getLogger('chatbot')

# Variables globales pour stocker les données en mémoire
global_cv_text = None
global_qa_data = None
global_vectorizer = None
global_tfidf_matrix = None

def load_secrets():
    with open(SECRETS_FILE, 'r') as f:
        return json.load(f)

def get_secret(key):
    secrets = load_secrets()
    if key in secrets:
        return secrets[key]
    else:
        logger.warning(f"La clé '{key}' n'existe pas dans secrets.json")
        return None

def log_execution_time(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        log_times = get_secret('log_execution_times')
        if log_times is not None and log_times:
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            logger.info(f"Temps d'exécution de {func.__name__}: {end_time - start_time:.4f} secondes")
            return result
        else:
            return func(*args, **kwargs)
    return wrapper

@log_execution_time
def load_data(force_reload=False):
    global global_cv_text, global_qa_data, global_vectorizer, global_tfidf_matrix

    use_memory = get_secret('use_memory_for_data')
    if use_memory is None:
        use_memory = True  # Valeur par défaut si non spécifiée

    if use_memory and not force_reload and global_cv_text is not None and global_qa_data is not None:
        logger.info("Utilisation des données en mémoire")
        return global_cv_text, global_qa_data

    cv_file = DATA_DIR / 'cv.txt'
    qa_file = DATA_DIR / 'qa_data.json'

    try:
        with cv_file.open('r', encoding='utf-8') as file:
            cv_text = file.read()

        with qa_file.open('r', encoding='utf-8') as file:
            qa_data = json.load(file)

        logger.info("Données CV et Q&A chargées avec succès")

        if use_memory:
            global_cv_text = cv_text
            global_qa_data = qa_data

        return cv_text, qa_data
    except Exception as e:
        logger.error(f"Erreur lors du chargement des données : {str(e)}")
        raise

@log_execution_time
def prepare_data(cv_text, qa_data):
    global global_vectorizer, global_tfidf_matrix

    use_memory = get_secret('use_memory_for_data')
    if use_memory is None:
        use_memory = True  # Valeur par défaut si non spécifiée

    if use_memory and global_vectorizer is not None and global_tfidf_matrix is not None:
        logger.info("Utilisation des données TF-IDF en mémoire")
        return global_vectorizer, global_tfidf_matrix

    documents = [cv_text] + [qa['question'] + ' ' + qa['answer'] for qa in qa_data]
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(documents)

    if use_memory:
        global_vectorizer = vectorizer
        global_tfidf_matrix = tfidf_matrix

    return vectorizer, tfidf_matrix

@log_execution_time
def search_relevant_docs(query, top_k=3):
    cv_text, qa_data = load_data()
    vectorizer, tfidf_matrix = prepare_data(cv_text, qa_data)

    for qa in qa_data:
        if query.lower() in qa['question'].lower():
            return [qa['answer']]

    query_vec = vectorizer.transform([query])
    similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
    top_indices = similarities.argsort()[-top_k:][::-1]

    relevant_docs = []
    for i in top_indices:
        if i == 0:
            relevant_docs.append(cv_text)
        else:
            relevant_docs.append(qa_data[i-1]['answer'])

    return relevant_docs

@log_execution_time
def get_ollama_response(question):
    start_time = time.time()  # Début du chronométrage
    OLLAMA_URL = os.environ.get('OLLAMA_URL')
    SALAD_API_KEY = os.environ.get('SALAD_API_KEY')

    HEADERS = {
        'Content-Type': 'application/json',
        'Salad-Api-Key': SALAD_API_KEY
    }

    model = get_secret('model_name')
    if model is None:
        model = "mistral:latest"
        logger.warning("Aucun modèle spécifié dans secrets.json. Utilisation du modèle par défaut: mistral:latest")
    logger.info(f"Utilisation du modèle: {model}")

    relevant_docs = search_relevant_docs(question)
    context = "\n".join(relevant_docs)
	
    context_length = get_secret('context_length')
    if context_length is None:
        context_length = 8192  # Valeur par défaut si non spécifiée
    logger.info(f"Utilisation de context_length: {context_length}")

    embedding_length = get_secret('embedding_length')
    if embedding_length is None:
        embedding_length = 1024  # Valeur par défaut si non spécifiée
    logger.info(f"Utilisation de embedding_length: {embedding_length}")

    stream = get_secret('stream')
    if stream is None:
        stream = True  # Valeur par défaut si non spécifiée
    logger.info(f"Utilisation de stream: {stream}")
	
    prompt_instructions = get_secret('prompt_instructions')
    if prompt_instructions is None:
        prompt_instructions = []
    prompt_instructions = "\n".join(prompt_instructions)

    full_prompt = f"{prompt_instructions}\n\nContexte du CV:\n{context}\n\nQuestion: {question}\n\nRéponse:"

    try:
        response = requests.post(f'{OLLAMA_URL}/api/generate',
            headers=HEADERS,
            json={
                'model': model,
                'prompt': full_prompt,
                'context_length': context_length,
                'embedding_length': embedding_length,
                'stream': stream
            },
            stream=stream
        )

        if response.status_code == 200:
            full_response = ""
            for line in response.iter_lines():
                if line:
                    try:
                        json_line = json.loads(line.decode('utf-8'))
                        if 'response' in json_line:
                            chunk = json_line['response']
                            full_response += json_line['response']
                            yield chunk
                    except json.JSONDecodeError:
                        logger.error(f"Erreur de décodage JSON: {line}")
            end_time = time.time()  # Fin du chronométrage
            execution_time = end_time - start_time
            logger.info(f"Temps d'exécution de get_ollama_response: {execution_time:.4f} secondes")
            save_interaction(question, full_response)
        else:
            error_message = f"Erreur: {response.status_code} - {response.text}"
            logger.error(error_message)
            yield error_message
    except Exception as e:
        error_message = f"Exception lors de l'appel à Ollama: {str(e)}"
        logger.error(error_message)
        yield error_message

def save_interaction(question, answer):
    interaction = {
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "answer": answer
    }
    
    file_path = DATA_DIR / 'chat_history.jsonl'
    max_file_size = 1 * 1024 * 1024  # 1 MB
    max_backup_count = 10

    if file_path.exists() and file_path.stat().st_size > max_file_size:
        for i in range(max_backup_count - 1, 0, -1):
            old_file = DATA_DIR / f'chat_history.jsonl.{i}'
            new_file = DATA_DIR / f'chat_history.jsonl.{i+1}'
            if old_file.exists():
                old_file.rename(new_file)
        
        if file_path.exists():
            file_path.rename(DATA_DIR / 'chat_history.jsonl.1')
    
    with file_path.open('a', encoding='utf-8') as f:
        json.dump(interaction, f, ensure_ascii=False)
        f.write('\n')

# Chargement initial des données
load_data()