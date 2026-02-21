import os, sys
from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit

app = Flask(__name__)
# Ping curto para manter o túnel do Render aberto e rápido
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent', ping_interval=2, ping_timeout=5)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Voz Direta</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { background: #000; color: #fff; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; font-family: sans-serif; }
        #vBtn { width: 200px; height: 200px; border-radius: 50%; border: none; background: #3b82f6; color: white; font-weight: bold; cursor: pointer; font-size: 1.2em; transition: 0.3s; }
        #vBtn.on { background: #ef4444; box-shadow: 0 0 20px #ef4444; }
        p { margin-top: 20px; color: #666; }
    </style>
</head>
<body>
    <button id="vBtn" onclick="t()">LIGAR VOZ</button>
    <p id="st">Status: Desconectado</p>

    <script>
        const socket = io({ transports: ['websocket'] });
        let ac; let isOn = false;
        const RATE = 12000; // Equilíbrio entre qualidade e peso para o Render

        socket.on('connect', () => document.getElementById('st').innerText = "Status: Online");

        async function t() {
            if(isOn) return location.reload();
            isOn = true;
            const btn = document.getElementById('vBtn');
            btn.innerText = "DESLIGAR";
            btn.classList.add('on');
            
            ac = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: RATE });
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const source = ac.createMediaStreamSource(stream);
            
            // Buffer pequeno para latência mínima
            const proc = ac.createScriptProcessor(2048, 1, 1);
            source.connect(proc);
            proc.connect(ac.destination);
            
            proc.onaudioprocess = (e) => {
                const inD = e.inputBuffer.getChannelData(0);
                const i16 = new Int16Array(inD.length);
                for (let i = 0; i < inD.length; i++) i16[i] = inD[i] * 0x7FFF;
                socket.emit('v', i16.buffer);
            };
        }

        socket.on('o', (buf) => {
            if(!ac) return;
            const i16 = new Int16Array(buf);
            const f32 = new Float32Array(i16.length);
            for (let i = 0; i < i16.length; i++) f32[i] = i16[i] / 0x7FFF;
            
            const ab = ac.createBuffer(1, f32.length, RATE);
            ab.getChannelData(0).set(f32);
            const src = ac.createBufferSource();
            src.buffer = ab;
            src.connect(ac.destination);
            src.start(ac.currentTime);
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@socketio.on('v')
def h_v(b):
    # Envia para todos, sem validação de senha para ser instantâneo
    emit('o', b, broadcast=True, include_self=False)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host='0.0.0.0', port=port)
