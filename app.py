import os, random, string, sys
from flask import Flask, render_template_string, session
from flask_socketio import SocketIO, emit

# Força a saída do log para você ver a senha rápido
def log_now(msg):
    print(msg, file=sys.stderr, flush=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'stabilidade-maxima'
# Usamos threading se o gevent estiver dando erro de porta
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent', ping_timeout=120)

AUTO_PASSWORD = ''.join(random.choices(string.digits, k=10))
log_now(f"\n" + "!"*30 + f"\nSENHA: {AUTO_PASSWORD}\n" + "!"*30)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Chat Estável</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { background: #000; color: #0f0; font-family: monospace; display: flex; justify-content: center; padding: 20px; }
        .container { width: 100%; max-width: 400px; border: 1px solid #0f0; padding: 20px; border-radius: 10px; }
        input { width: 100%; background: #111; border: 1px solid #0f0; color: #0f0; padding: 10px; margin-bottom: 10px; box-sizing: border-box; }
        .btn { width: 100%; padding: 10px; background: #0f0; color: #000; border: none; font-weight: bold; cursor: pointer; margin-bottom: 10px; }
        #chat { height: 200px; overflow-y: auto; border: 1px solid #333; margin: 10px 0; padding: 5px; font-size: 12px; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div id="login-box">
            <h3>ACESSO</h3>
            <input type="text" id="n" placeholder="Nome">
            <input type="password" id="p" placeholder="Senha">
            <button class="btn" onclick="auth()">CONECTAR</button>
        </div>
        <div id="chat-box" class="hidden">
            <button id="mBtn" class="btn" style="background: #555;" onclick="startV()">ATIVAR MICROFONE</button>
            <div id="chat"></div>
            <input type="text" id="msg" placeholder="Mensagem...">
        </div>
    </div>

    <script>
        const socket = io({ transports: ['websocket'], upgrade: false });
        let aCtx; let isV = false;

        function auth() { socket.emit('login', {n: document.getElementById('n').value, p: document.getElementById('p').value}); }
        
        socket.on('login_ok', (d) => {
            if(d.ok) {
                document.getElementById('login-box').classList.add('hidden');
                document.getElementById('chat-box').classList.remove('hidden');
            } else { alert("Senha incorreta"); }
        });

        document.getElementById('msg').onkeypress = (e) => {
            if(e.key === 'Enter') { socket.emit('m', e.target.value); e.target.value = ''; }
        };

        socket.on('m_msg', (d) => {
            const c = document.getElementById('chat');
            c.innerHTML += `<div>> <b>${d.u}:</b> ${d.t}</div>`;
            c.scrollTo(0, c.scrollHeight);
        });

        async function startV() {
            if(isV) return location.reload();
            isV = true;
            document.getElementById('mBtn').innerText = "MICROFONE LIGADO";
            document.getElementById('mBtn').style.background = "#f00";
            
            aCtx = new AudioContext({ sampleRate: 16000 }); // Reduzi para 16kHz (mais estável no Render)
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const source = aCtx.createMediaStreamSource(stream);
            const proc = aCtx.createScriptProcessor(8192, 1, 1); // Buffer maior para evitar cortes
            
            source.connect(proc); proc.connect(aCtx.destination);
            
            proc.onaudioprocess = (e) => {
                const input = e.inputBuffer.getChannelData(0);
                const i16 = new Int16Array(input.length);
                for (let i = 0; i < input.length; i++) i16[i] = input[i] * 0x7FFF;
                socket.emit('v_in', i16.buffer);
            };
        }

        let nTime = 0;
        socket.on('v_out', (buf) => {
            if(!aCtx) return;
            const i16 = new Int16Array(buf);
            const f32 = new Float32Array(i16.length);
            for (let i = 0; i < i16.length; i++) f32[i] = i16[i] / 0x7FFF;
            const ab = aCtx.createBuffer(1, f32.length, 16000);
            ab.getChannelData(0).set(f32);
            const src = aCtx.createBufferSource();
            src.buffer = ab; src.connect(aCtx.destination);
            const now = aCtx.currentTime;
            if (nTime < now) nTime = now + 0.15; // Jitter buffer maior
            src.start(nTime); nTime += ab.duration;
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@socketio.on('login')
def login(d):
    if d.get('p') == AUTO_PASSWORD:
        session['u'] = d.get('n', 'User')
        emit('login_ok', {'ok': True})
    else: emit('login_ok', {'ok': False})

@socketio.on('m')
def msg(t):
    if 'u' in session: emit('m_msg', {'u': session['u'], 't': t}, broadcast=True)

@socketio.on('v_in')
def voice(b):
    if 'u' in session: emit('v_out', b, broadcast=True, include_self=False)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host='0.0.0.0', port=port)
