let sessionId = null;

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

$(document).ready(function() {
    const csrftoken = getCookie('csrftoken');

    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            }
        }
    });

    $('#load-cv-btn').click(function() {
        $('#cv-frame').attr('src', '/cv/');
        $('#cv-container').show();
        loadInitialMessage();
    });

    $('.close').click(function() {
        $('#cv-container').hide();
    });

    $('#user-input').on('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    $('#send-button').click(sendMessage);
});

function loadInitialMessage() {
    $.get('/initial-message/', function(data) {
        $('#chat-messages').append(`<p><strong>Chatbot:</strong> ${data.message}</p>`);
    });
}

function sendMessage() {
    const userInput = $('#user-input');
    const chatMessages = $('#chat-messages');
    const question = userInput.val().trim();

    if (question) {
        chatMessages.append(`<p><strong>Vous:</strong> ${question}</p>`);
        userInput.val('');

        const eventSource = new EventSource(`/chatbot/?question=${encodeURIComponent(question)}&session_id=${sessionId}`);
        
        let currentResponse = $('<p><strong>Chatbot:</strong> </p>');
        chatMessages.append(currentResponse);

        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            currentResponse.append(data.chunk);
            chatMessages.scrollTop(chatMessages[0].scrollHeight);
        };

        eventSource.onerror = function(event) {
            console.error("EventSource failed:", event);
            eventSource.close();
            chatMessages.append(`<p><strong>Erreur:</strong> La connexion a été interrompue.</p>`);
        };

        eventSource.addEventListener('close', function(event) {
            eventSource.close();
            const data = JSON.parse(event.data);
            sessionId = data.session_id;
        });
    }
}
