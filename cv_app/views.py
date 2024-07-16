from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.csrf import requires_csrf_token, ensure_csrf_cookie
from django.conf import settings
import json
from ollama_client.client import get_ollama_response

SECRETS_FILE = getattr(settings, 'SECRETS_FILE', None)

def index_view(request):
    return render(request, 'cv_app/index.html')

def cv_view(request):
    return render(request, 'cv_app/cv.html')
@csrf_protect
@require_http_methods(["POST"])
@requires_csrf_token
@ensure_csrf_cookie
def chatbot(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        question = data.get('question')
        session_id = data.get('session_id')

        answer = get_ollama_response(question)

        return JsonResponse({'answer': answer, 'session_id': session_id})

def get_initial_message(request):
    with open(SECRETS_FILE, 'r') as f:
        secrets = json.load(f)
    return JsonResponse({'message': secrets['initial_message']})