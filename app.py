import os, sys
from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit

app = Flask(__name__)
# Ajuste fino de buffers para evitar o atraso que você reclamou
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent', ping_interval=2, ping_timeout=5)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Voz Realtime</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { background: #000; color: #fff; margin: 0; display: flex; align-items: center; justify-content: center; height: 100vh; font-family: sans-serif; }
        #vBtn { width: 220px; height: 220px; border-radius: 50%; border: 8px solid #333; background: #111; color: #fff; font-size: 1.5em; font-weight: bold; cursor: pointer; transition: 0.2s; }
        #vBtn.active { background: #f00; border-color: #ff5555; box-shadow: 0 0 50px #f00; }
        #status { position: absolute; top: 20px; font-family: monospace; color: #0f0; }
        /* Vídeo invisível para forçar a tela acesa */
        video { position: absolute; width: 1px; height: 1px; opacity: 0.01; }
    </style>
</head>
<body>
    <div id="status">SINAL: AGUARDANDO...</div>
    
    <video id="keepAlive" playsinline loop muted>
        <source src="https://raw.githubusercontent.com/bower-media-samples/big-buck-bunny-1080p-30s/master/video.mp4" type="video/mp4">
    </video>

    <button id="vBtn" onclick="init()">LIGAR</button>

    <script>
        const socket = io({ transports: ['websocket'] });
        let ac;
        const RATE = 12000;

        socket.on('connect', () => document.getElementById('status').innerText = "SINAL: ONLINE");

        async function init() {
            const btn = document.getElementById('vBtn');
            const video = document.getElementById('keepAlive');
            
            if(btn.classList.contains('active')) return location.reload();
            
            btn.classList.add('active');
            btn.innerText = "SESSÃO ON";
            
            // 1. Força a tela a ficar acesa via Vídeo Loop
            video.play().catch(e => console.log("Erro video:", e));
            
            // 2. Configura Áudio
            ac = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: RATE });
            
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } 
                });
                const source = ac.createMediaStreamSource(stream);
                const proc = ac.createScriptProcessor(1024, 1, 1); // Buffer menor = menos atraso
                
                source.connect(proc);
                proc.connect(ac.destination);
                
                proc.onaudioprocess = (e) => {
                    const input = e.inputBuffer.getChannelData(0);
                    const i16 = new Int16Array(input.length);
                    for (let i = 0; i < input.length; i++) i16[i] = input[i] * 0x7FFF;
                    socket.emit('v', i16.buffer);
                };
            } catch (err) {
                alert("Erro microfone. Use HTTPS!");
            }
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
            // Toca no tempo exato para evitar o atraso de 10s
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
    emit('o', b, broadcast=True, include_self=False)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host='0.0.0.0', port=port)
