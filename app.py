import os
import random
import string
import sys
from flask import Flask, render_template_string, session
from flask_socketio import SocketIO, emit

# Forçar a senha a aparecer no LOG do Render (sys.stderr garante o envio)
def log_now(msg):
    print(msg, file=sys.stderr, flush=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'chave-ultra-secreta-99'
# Gevent é essencial para não dar erro de porta no Render
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# Gerar senha automática de 10 dígitos
AUTO_PASSWORD = ''.join(random.choices(string.digits, k=10))

log_now("\n" + "!"*40)
log_now(f"!!! SENHA DO CHAT: {AUTO_PASSWORD} !!!")
log_now("!"*40 + "\n")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Call HD & Chat Privado</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #09090b; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .box { width: 380px; background: #18181b; border: 1px solid #3f3f46; border-radius: 20px; padding: 30px; text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.7); }
        .hidden { display: none; }
        input { width: 100%; background: #09090b; border: 1px solid #3f3f46; color: #fff; padding: 12px; border-radius: 8px; margin-bottom: 12px; box-sizing: border-box; outline: none; }
        input:focus { border-color: #3b82f6; }
        .btn { width: 100%; padding: 12px; background: #3b82f6; color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; transition: 0.2s; }
        .btn:hover { background: #2563eb; }
        .btn-call { background: #10b981; margin-bottom: 15px; }
        .btn-call.active { background: #ef4444; }
        #chat-win { height: 250px; overflow-y: auto; background: #09090b; margin: 15px 0; padding: 15px; border-radius: 10px; text-align: left; font-size: 0.9em; border: 1px solid #27272a; }
        .msg-item { margin-bottom: 8px; line-height: 1.4; }
        .user-name { color: #3b82f6; font-weight: bold; }
        .sys-msg { color: #71717a; font-style: italic; font-size: 0.8em; text-align: center; }
    </style>
</head>
<body>
    <div id="login-screen" class="box">
        <h2 style="margin-top:0">🔒 Acesso</h2>
        <input type="text" id="nameInput" placeholder="Seu Nome">
        <input type="password" id="passInput" placeholder="Senha (veja no log do Render)">
        <button class="btn" onclick="login()">ENTRAR NO CHAT</button>
    </div>

    <div id="app-screen" class="box hidden">
        <h3 id="status-label" style="color:#a1a1aa; font-size:0.8em">SESSÃO ATIVA</h3>
        <button id="callBtn" class="btn btn-call" onclick="toggleCall()">LIGAR MICROFONE HD</button>
        <div id="chat-win"></div>
        <div style="display:flex; gap: 5px">
            <input type="text" id="msgInput" placeholder="Mensagem..." style="margin:0">
            <button class="btn" style="width:60px" onclick="sendMsg()">➤</button>
        </div>
    </div>

    <script>
        const socket = io();
        let audioCtx;
        let isCalling = false;
        const SAMPLE_RATE = 24000;

        function login() {
            const name = document.getElementById('nameInput').value;
            const password = document.getElementById('passInput').value;
            if(name && password) socket.emit('authenticate', {name, password});
        }

        socket.on('auth_result', (data) => {
            if(data.success) {
                document.getElementById('login-screen').classList.add('hidden');
                document.getElementById('app-screen').classList.remove('hidden');
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

        document.getElementById('msgInput').addEventListener('keypress', (e) => { if(e.key === 'Enter') sendMsg(); });

        socket.on('text_update', (data) => {
            const win = document.getElementById('chat-win');
            const isSys = data.user === 'Sistema';
            win.innerHTML += isSys ? `<div class="sys-msg">${data.text}</div>` : 
                                    `<div class="msg-item"><span class="user-name">${data.user}:</span> ${data.text}</div>`;
            win.scrollTop = win.scrollHeight;
        });

        async function toggleCall() {
            if (isCalling) return location.reload();
            isCalling = true;
            const btn = document.getElementById('callBtn');
            btn.innerText = "DESLIGAR MIC";
            btn.classList.add('active');
            
            audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: SAMPLE_RATE });
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    audio: { echoCancellation: true, noiseSuppression: true } 
                });
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
            } catch (err) { alert("Permita o microfone no navegador!"); }
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
        emit('text_update', {'user': 'Sistema', 'text': f"🟢 {session['user']} entrou na sala."}, broadcast=True)
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
    port = int(os.environ.get("PORT", 10000))
    # Rodar com socketio em vez de app.run para suportar WebSocket
    socketio.run(app, host='0.0.0.0', port=port)
