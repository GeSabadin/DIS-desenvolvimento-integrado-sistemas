import json, os, threading, time
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import numpy as np, psutil

AQUI = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(AQUI, '..', 'data')


def carregar(m):  # CSV demora, entao salva um .npy na primeira vez
    npy = os.path.join(DATA, f'H-{m}.npy')
    if not os.path.exists(npy):
        np.save(npy, np.loadtxt(os.path.join(DATA, f'H-{m}.csv'), delimiter=','))
    return np.load(npy)


H = {1: carregar(1), 2: carregar(2)}


def cgnr(H, g):
    f = np.zeros(H.shape[1]); r = g.copy(); z = H.T @ r; p = z.copy()
    for i in range(1, 11):
        w = H @ p
        alpha = (z @ z) / (w @ w)
        f += alpha * p
        r_novo = r - alpha * w
        z_novo = H.T @ r_novo
        beta = (z_novo @ z_novo) / (z @ z)
        p = z_novo + beta * p
        erro = abs(np.linalg.norm(r_novo) - np.linalg.norm(r))
        r, z = r_novo, z_novo
        if erro < 1e-4:
            break
    return f, i


def cgne(H, g):
    f = np.zeros(H.shape[1]); r = g.copy(); p = H.T @ r
    for i in range(1, 11):
        alpha = (r @ r) / (p @ p)
        f += alpha * p
        r_novo = r - alpha * (H @ p)
        beta = (r_novo @ r_novo) / (r @ r)
        p = H.T @ r_novo + beta * p
        erro = abs(np.linalg.norm(r_novo) - np.linalg.norm(r))
        r = r_novo
        if erro < 1e-4:
            break
    return f, i


ALGS = {'CGNR': cgnr, 'CGNE': cgne}
cpu_livre = threading.Semaphore(2)  # no maximo 2 reconstrucoes ao mesmo tempo
fila = 0                            # quantos estao esperando
MAX_FILA = 10                       # controle de saturacao: acima disso responde 503
lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def responder(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header('Content-Length', len(b)); self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        global fila
        req = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        with lock:
            if fila >= MAX_FILA:
                return self.responder(503, {'erro': 'servidor cheio, tenta depois'})
            fila += 1
        with cpu_livre:
            with lock:
                fila -= 1
            inicio = datetime.now()
            f, it = ALGS[req['algoritmo']](H[req['modelo']], np.array(req['g']))
            fim = datetime.now()
        self.responder(200, {'cliente': req['cliente'], 'sinal': req['sinal'], 'algoritmo': req['algoritmo'],
                             'modelo': req['modelo'], 'inicio': str(inicio), 'fim': str(fim),
                             'iteracoes': it, 'imagem': f.tolist()})


def monitor():  # grava CPU, memoria e fila pro relatorio
    p = psutil.Process()
    with open(os.path.join(AQUI, 'metricas.csv'), 'w') as arq:
        arq.write('t,cpu,mem_mb,fila\n')
        while True:
            time.sleep(0.5)
            arq.write(f'{time.time():.2f},{p.cpu_percent()/psutil.cpu_count():.1f},{p.memory_info().rss/2**20:.0f},{fila}\n')
            arq.flush()


threading.Thread(target=monitor, daemon=True).start()
print('servidor no ar: http://127.0.0.1:8001')
ThreadingHTTPServer(('127.0.0.1', 8001), Handler).serve_forever()
