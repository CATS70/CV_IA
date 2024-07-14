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
        $.ajax({
            url: '/chatbot/',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                question: question,
                session_id: sessionId
            }),
            success: function(response) {
                chatMessages.append(`<p><strong>Chatbot:</strong> ${response.answer}</p>`);
                sessionId = response.session_id;
                chatMessages.scrollTop(chatMessages[0].scrollHeight);
            },
            error: function(jqXHR, textStatus, errorThrown) {
                console.error("AJAX error: " + textStatus + ' : ' + errorThrown);
                chatMessages.append(`<p><strong>Erreur:</strong> Impossible d'obtenir une réponse.</p>`);
            }
        });
    }
}
