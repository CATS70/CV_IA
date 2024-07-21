from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.csrf import requires_csrf_token, ensure_csrf_cookie
from django.conf import settings
from django.http import StreamingHttpResponse, HttpResponseNotAllowed
import json
from ollama_client.client import get_ollama_response

SECRETS_FILE = getattr(settings, 'SECRETS_FILE', None)

def index_view(request):
    return render(request, 'cv_app/index.html')

def cv_view(request):
    return render(request, 'cv_app/cv.html')
@csrf_protect
@requires_csrf_token
@ensure_csrf_cookie
def chatbot(request):
    if request.method == 'GET':
        question = request.GET.get('question')
        session_id = request.GET.get('session_id')

        def generate_response():
            for chunk in get_ollama_response(question):
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            yield f"event: close\ndata: {json.dumps({'session_id': session_id})}\n\n"

        return StreamingHttpResponse(generate_response(), content_type='text/event-stream')
    else:
        return HttpResponseNotAllowed(['GET'])
def get_initial_message(request):
    with open(SECRETS_FILE, 'r') as f:
        secrets = json.load(f)
    return JsonResponse({'message': secrets['initial_message']})