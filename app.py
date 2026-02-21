from flask import Flask, render_template_string, session
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'radio-secret-99'
socketio = SocketIO(app, cors_allowed_origins="*")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Call HD & Chat</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #09090b; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .main-container { width: 400px; background: #18181b; border: 1px solid #3f3f46; border-radius: 20px; display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        
        /* Cabeçalho de Voz */
        .voice-panel { padding: 20px; background: #27272a; text-align: center; border-bottom: 1px solid #3f3f46; }
        .btn-call { width: 100%; padding: 12px; background: #3b82f6; color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; transition: 0.3s; }
        .btn-call.active { background: #ef4444; }
        
        /* Área de Chat */
        #chat-window { flex-grow: 1; height: 300px; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 8px; }
        .msg { background: #27272a; padding: 8px 12px; border-radius: 8px; font-size: 0.9em; max-width: 85%; }
        .system { color: #71717a; font-size: 0.8em; text-align: center; font-style: italic; }
        
        /* Input */
        .input-area { padding: 15px; background: #18181b; display: flex; gap: 8px; }
        input { flex-grow: 1; background: #09090b; border: 1px solid #3f3f46; color: #fff; padding: 10px; border-radius: 6px; outline: none; }
        .btn-send { background: #3b82f6; border: none; color: white; padding: 10px; border-radius: 6px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="main-container">
        <div class="voice-panel">
            <h3 id="status-label" style="margin: 0 0 10px 0; font-size: 0.9em; color: #a1a1aa;">VOZ: DESCONECTADA</h3>
            <button id="callBtn" class="btn-call" onclick="toggleCall()">ENTRAR NA CHAMADA</button>
        </div>

        <div id="chat-window">
            <div class="system">Bem-vindo ao chat seguro</div>
        </div>

        <div class="input-area">
            <input type="text" id="msgInput" placeholder="Digite uma mensagem...">
            <button class="btn-send" onclick="sendMsg()">➤</button>
        </div>
    </div>

    <script>
        const socket = io();
        const userName = prompt("Seu Nome:") || "Anônimo";
        let audioCtx;
        let isCalling = false;
        const SAMPLE_RATE = 24000;

        socket.on('connect', () => {
            socket.emit('join', {name: userName});
        });

        // --- LÓGICA DE TEXTO ---
        function sendMsg() {
            const input = document.getElementById('msgInput');
            if(input.value.trim()){
                socket.emit('chat_msg', {text: input.value});
                input.value = '';
            }
        }

        document.getElementById('msgInput').addEventListener('keypress', (e) => { if(e.key === 'Enter') sendMsg(); });

        socket.on('text_update', (data) => {
            const win = document.getElementById('chat-window');
            const type = data.user === 'Sistema' ? 'system' : 'msg';
            win.innerHTML += `<div class="${type}"><strong>${data.user}:</strong> ${data.text}</div>`;
            win.scrollTop = win.scrollHeight;
        });

        // --- LÓGICA DE VOZ (ESTÁVEL) ---
        async function toggleCall() {
            if (isCalling) return location.reload(); // Jeito fácil de sair da call

            isCalling = true;
            const btn = document.getElementById('callBtn');
            btn.innerText = "SAIR DA CHAMADA";
            btn.classList.add('active');
            document.getElementById('status-label').innerText = "VOZ: AO VIVO (24kHz)";

            audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: SAMPLE_RATE });

            try {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } 
                });
                const source = audioCtx.createMediaStreamSource(stream);
                const processor = audioCtx.createScriptProcessor(2048, 1, 1);

                source.connect(processor);
                processor.connect(audioCtx.destination);

                processor.onaudioprocess = (e) => {
                    const inputData = e.inputBuffer.getChannelData(0);
                    const int16Data = new Int16Array(inputData.length);
                    for (let i = 0; i < inputData.length; i++) {
                        int16Data[i] = Math.max(-1, Math.min(1, inputData[i])) * 0x7FFF;
                    }
                    socket.emit('voice_stream', int16Data.buffer);
                };
            } catch (err) { alert("Erro no Mic: Use HTTPS!"); }
        }

        let nextStartTime = 0;
        socket.on('audio_out', (buffer) => {
            if (!audioCtx) return;
            const int16Data = new Int16Array(buffer);
            const float32Data = new Float32Array(int16Data.length);
            for (let i = 0; i < int16Data.length; i++) { float32Data[i] = int16Data[i] / 0x7FFF; }

            const audioBuffer = audioCtx.createBuffer(1, float32Data.length, SAMPLE_RATE);
            audioBuffer.getChannelData(0).set(float32Data);
            const source = audioCtx.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(audioCtx.destination);

            const currentTime = audioCtx.currentTime;
            if (nextStartTime < currentTime) { nextStartTime = currentTime + 0.08; }
            source.start(nextStartTime);
            nextStartTime += audioBuffer.duration;
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@socketio.on('join')
def handle_join(data):
    session['user'] = data['name']
    emit('text_update', {'user': 'Sistema', 'text': f"{data['name']} entrou."}, broadcast=True)

@socketio.on('chat_msg')
def handle_chat(data):
    emit('text_update', {'user': session.get('user', 'User'), 'text': data['text']}, broadcast=True)

@socketio.on('voice_stream')
def handle_voice(data):
    emit('audio_out', data, broadcast=True, include_self=False)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)