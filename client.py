import json, os, random, sys, threading, time, urllib.request, urllib.error
import numpy as np
from PIL import Image

# python client.py py        -> testa a interpretada (3 clientes x 15 sinais)
# python client.py cs        -> testa a compilada
# python client.py py sat    -> teste de saturacao (20 clientes x 5 sinais, quase sem pausa)
ALVO = sys.argv[1] if len(sys.argv) > 1 else 'py'
SAT = len(sys.argv) > 2 and sys.argv[2] == 'sat'
AQUI = os.path.dirname(os.path.abspath(__file__))
URL = {'py': 'http://127.0.0.1:8001', 'cs': 'http://127.0.0.1:8002'}[ALVO]
OUT = os.path.join(AQUI, {'py': 'interpretada', 'cs': 'compilada'}[ALVO], 'out_sat' if SAT else 'out')
N_CLIENTES, N_SINAIS, ESPERA = (20, 5, (0, 0.2)) if SAT else (3, 15, (0.2, 2))

SINAIS = {1: (60, 794, ['G-1.csv', 'G-2.csv', 'A-60x60-1.csv']),
          2: (30, 436, ['g-30x30-1.csv', 'g-30x30-2.csv', 'A-30x30-1.csv'])}

random.seed(42)  # semente fixa = mesma sequencia de sinais pras duas versoes do servidor
plano = {f'c{c}': [dict(modelo=(m := random.choice([1, 2])), arquivo=random.choice(SINAIS[m][2]),
                        algoritmo=random.choice(['CGNR', 'CGNE']), k=random.uniform(0.5, 2),
                        espera=random.uniform(*ESPERA)) for _ in range(N_SINAIS)] for c in range(1, N_CLIENTES + 1)}
resultados = []
os.makedirs(OUT, exist_ok=True)


def ganho(g, S, k):  # gamma_l = k * (100 + 1/20 * l * sqrt(l)), aplicado em cada sensor
    l = np.arange(1, S + 1)
    return (g.reshape(64, S) * k * (100 + l * np.sqrt(l) / 20)).ravel()


def cliente(nome, sinais):
    for i, s in enumerate(sinais, 1):
        time.sleep(s['espera'])
        n, S, _ = SINAIS[s['modelo']]
        g = ganho(np.loadtxt(os.path.join(AQUI, 'data', s['arquivo'])), S, s['k'])
        corpo = json.dumps(dict(cliente=nome, sinal=f'{nome}-s{i:02d}', modelo=s['modelo'],
                                algoritmo=s['algoritmo'], g=g.tolist())).encode()
        recusas = 0
        while True:
            try:
                r = json.loads(urllib.request.urlopen(urllib.request.Request(URL, corpo, {'Content-Type': 'application/json'})).read())
                break
            except urllib.error.HTTPError as e:  # 503 = servidor cheio, espera e tenta de novo
                if e.code != 503: raise
                recusas += 1
                time.sleep(1)
        img = np.abs(np.array(r.pop('imagem'))).reshape(n, n, order='F')
        Image.fromarray((255 * img / img.max()).astype(np.uint8)).resize((240, 240)).save(os.path.join(OUT, r['sinal'] + '.png'))
        resultados.append({**r, 'arquivo': s['arquivo'], 'recusas_503': recusas})
        print(r['sinal'], r['algoritmo'], r['iteracoes'], 'iteracoes', f'({recusas}x 503)' if recusas else '')


t0 = time.time()
threads = [threading.Thread(target=cliente, args=item) for item in plano.items()]
for t in threads: t.start()
for t in threads: t.join()
t1 = time.time()

resultados.sort(key=lambda r: r['sinal'])
json.dump({'inicio': t0, 'fim': t1, 'resultados': resultados}, open(os.path.join(OUT, 'resultados.json'), 'w'), indent=1)
linhas = ''.join(f"<tr><td><img src='{r['sinal']}.png'></td><td>{r['cliente']}</td><td>{r['sinal']}</td><td>{r['algoritmo']}</td>"
                 f"<td>{r['inicio']}</td><td>{r['fim']}</td><td>{r['iteracoes']}</td></tr>" for r in resultados)
open(os.path.join(OUT, 'relatorio.html'), 'w', encoding='utf-8').write(
    f"<meta charset=utf-8><h1>{len(resultados)} imagens em {t1-t0:.1f}s</h1><table border=1>"
    f"<tr><th>Imagem</th><th>Cliente</th><th>Sinal</th><th>Algoritmo</th><th>Início</th><th>Fim</th><th>Iterações</th></tr>{linhas}</table>")
print('relatorio em', os.path.join(OUT, 'relatorio.html'))
