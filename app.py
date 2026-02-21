import os
import random
import string
from flask import Flask, render_template_string, session, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret-key-123'
socketio = SocketIO(app, cors_allowed_origins="*")

# Gerar senha automática de 10 dígitos
AUTO_PASSWORD = ''.join(random.choices(string.digits, k=10))

print("\n" + "="*30)
print(f" SENHA DE ACESSO: {AUTO_PASSWORD}")
print("="*30 + "\n")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Chat Privado HD</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #09090b; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .box { width: 350px; background: #18181b; border: 1px solid #3f3f46; border-radius: 15px; padding: 25px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        .hidden { display: none; }
        input { width: 100%; background: #09090b; border: 1px solid #3f3f46; color: #fff; padding: 10px; border-radius: 6px; margin-bottom: 10px; box-sizing: border-box; }
        .btn { width: 100%; padding: 12px; background: #3b82f6; color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; }
        #chat-win { height: 200px; overflow-y: auto; background: #09090b; margin: 15px 0; padding: 10px; border-radius: 8px; text-align: left; font-size: 0.9em; border: 1px solid #27272a; }
        .sys { color: #71717a; font-size: 0.8em; }
    </style>
</head>
<body>
    <div id="login-screen" class="box">
        <h2>🔒 Acesso Restrito</h2>
        <input type="text" id="nameInput" placeholder="Seu Nome">
        <input type="password" id="passInput" placeholder="Senha de 10 dígitos">
        <button class="btn" onclick="login()">ENTRAR</button>
    </div>

    <div id="app-screen" class="box hidden">
        <h3 id="user-label">Conectado</h3>
        <button id="callBtn" class="btn" onclick="toggleCall()">LIGAR ÁUDIO HD</button>
        <div id="chat-win"></div>
        <input type="text" id="msgInput" placeholder="Mensagem...">
        <button class="btn" style="background:#27272a" onclick="sendMsg()">Enviar</button>
    </div>

    <script>
        const socket = io();
        let audioCtx;
        let isCalling = false;
        const SAMPLE_RATE = 24000;

        function login() {
            const name = document.getElementById('nameInput').value;
            const password = document.getElementById('passInput').value;
            socket.emit('authenticate', {name, password});
        }

        socket.on('auth_result', (data) => {
            if(data.success) {
                document.getElementById('login-screen').classList.add('hidden');
                document.getElementById('app-screen').classList.remove('hidden');
                document.getElementById('user-label').innerText = "Olá, " + data.name;
            } else {
                alert("Senha Incorreta!");
            }
        });

        function sendMsg() {
            const input = document.getElementById('msgInput');
            if(input.value.trim()) {
                socket.emit('chat_msg', {text: input.value});
                input.value = '';
            }
        }

        socket.on('text_update', (data) => {
            const win = document.getElementById('chat-win');
            win.innerHTML += `<div><strong style="color:#3b82f6">${data.user}:</strong> ${data.text}</div>`;
            win.scrollTop = win.scrollHeight;
        });

        async function toggleCall() {
            if (isCalling) return location.reload();
            isCalling = true;
            const btn = document.getElementById('callBtn');
            btn.innerText = "SAIR DA CHAMADA";
            btn.style.background = "#ef4444";
            
            audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: SAMPLE_RATE });
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                const source = audioCtx.createMediaStreamSource(stream);
                const processor = audioCtx.createScriptProcessor(2048, 1, 1);
                source.connect(processor);
                processor.connect(audioCtx.destination);
                processor.onaudioprocess = (e) => {
                    const inputData = e.inputBuffer.getChannelData(0);
                    const int16 = new Int16Array(inputData.length);
                    for (let i = 0; i < inputData.length; i++) {
                        int16[i] = Math.max(-1, Math.min(1, inputData[i])) * 0x7FFF;
                    }
                    socket.emit('voice_stream', int16.buffer);
                };
            } catch (err) { alert("Erro Mic!"); }
        }

        let nextStartTime = 0;
        socket.on('audio_out', (buffer) => {
            if (!audioCtx) return;
            const int16 = new Int16Array(buffer);
            const float32 = new Float32Array(int16.length);
            for (let i = 0; i < int16.length; i++) { float32[i] = int16[i] / 0x7FFF; }
            const audioBuf = audioCtx.createBuffer(1, float32.length, SAMPLE_RATE);
            audioBuf.getChannelData(0).set(float32);
            const source = audioCtx.createBufferSource();
            source.buffer = audioBuf;
            source.connect(audioCtx.destination);
            const now = audioCtx.currentTime;
            if (nextStartTime < now) nextStartTime = now + 0.08;
            source.start(nextStartTime);
            nextStartTime += audioBuf.duration;
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@socketio.on('authenticate')
def handle_auth(data):
    if data.get('password') == AUTO_PASSWORD:
        session['user'] = data.get('name', 'Anônimo')
        session['auth'] = True
        emit('auth_result', {'success': True, 'name': session['user']})
        emit('text_update', {'user': 'Sistema', 'text': f"{session['user']} entrou."}, broadcast=True)
    else:
        emit('auth_result', {'success': False})

@socketio.on('chat_msg')
def handle_chat(data):
    if session.get('auth'):
        emit('text_update', {'user': session.get('user'), 'text': data['text']}, broadcast=True)

@socketio.on('voice_stream')
def handle_voice(data):
    if session.get('auth'):
        emit('audio_out', data, broadcast=True, include_self=False)

if __name__ == '__main__':
    # Porta dinâmica para o Render
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
