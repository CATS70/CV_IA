import os
import json
import requests
from django.conf import settings
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Configurez le logger
logger = logging.getLogger('chatbot')

# Variables globales pour stocker les données en mémoire
global_cv_text = None
global_qa_data = None
global_vectorizer = None
global_tfidf_matrix = None

def load_data(force_reload=False):
    global global_cv_text, global_qa_data, global_vectorizer, global_tfidf_matrix

    # Charger les paramètres depuis secrets.json
    with open(settings.SECRETS_FILE, 'r') as f:
        secrets = json.load(f)
    
    use_memory = secrets.get('use_memory_for_data', True)

    if use_memory and not force_reload and global_cv_text is not None and global_qa_data is not None:
        logger.info("Utilisation des données en mémoire")
        return global_cv_text, global_qa_data

    cv_file = os.path.join(settings.BASE_DIR, 'data', 'cv.txt')
    qa_file = os.path.join(settings.BASE_DIR, 'data', 'qa_data.json')

    try:
        with open(cv_file, 'r', encoding='utf-8') as file:
            cv_text = file.read()
        
        with open(qa_file, 'r', encoding='utf-8') as file:
            qa_data = json.load(file)
        
        logger.info("Données CV et Q&A chargées avec succès")

        if use_memory:
            global_cv_text = cv_text
            global_qa_data = qa_data

        return cv_text, qa_data
    except Exception as e:
        logger.error(f"Erreur lors du chargement des données : {str(e)}")
        raise

def prepare_data(cv_text, qa_data):
    global global_vectorizer, global_tfidf_matrix

    # Charger les paramètres depuis secrets.json
    with open(settings.SECRETS_FILE, 'r') as f:
        secrets = json.load(f)
    
    use_memory = secrets.get('use_memory_for_data', True)

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

def get_ollama_response(question):
    OLLAMA_URL = os.environ.get('OLLAMA_URL') 
    SALAD_API_KEY = os.environ.get('SALAD_API_KEY')
    
    HEADERS = {
        'Content-Type': 'application/json',
        'Salad-Api-Key': SALAD_API_KEY
    }
    model = "mistral:latest"
    
    # Recherche d'informations pertinentes
    relevant_docs = search_relevant_docs(question)
    context = "\n".join(relevant_docs)

    # Lire les instructions du prompt depuis secrets.json
    with open(settings.SECRETS_FILE, 'r') as f:
        secrets = json.load(f)
    
    prompt_instructions = "\n".join(secrets.get('prompt_instructions', []))
    
    full_prompt = f"{prompt_instructions}\n\nContexte du CV:\n{context}\n\nQuestion: {question}\n\nRéponse:"
    
    try:
        response = requests.post(f'{OLLAMA_URL}/api/generate', 
            headers=HEADERS,
            json={
                'model': model,
                'prompt': full_prompt,
                'max_tokens': 100,
                'temperature': 0.3
            },
            stream=True
        )
        
        if response.status_code == 200:
            full_response = ""
            for line in response.iter_lines():
                if line:
                    try:
                        json_line = json.loads(line.decode('utf-8'))
                        if 'response' in json_line:
                            full_response += json_line['response']
                    except json.JSONDecodeError:
                        logger.error(f"Erreur de décodage JSON: {line}")
            return full_response
        else:
            error_message = f"Erreur: {response.status_code} - {response.text}"
            logger.error(error_message)
            return error_message
    except Exception as e:
        error_message = f"Exception lors de l'appel à Ollama: {str(e)}"
        logger.error(error_message)
        return error_message

# Chargement initial des données
load_data()