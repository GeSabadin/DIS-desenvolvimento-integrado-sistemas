"""Relatorio comparativo entre a versao interpretada e a compilada.
python comparar.py       -> usa os testes normais   -> relatorio_comparativo.html
python comparar.py sat   -> usa os testes de saturacao -> relatorio_saturacao.html
"""
import base64, csv, io, json, os, statistics, sys
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

AQUI = os.path.dirname(os.path.abspath(__file__))
SAT = len(sys.argv) > 1 and sys.argv[1] == 'sat'
VERSOES = {'Python (interpretada)': 'interpretada', 'C# (compilada)': 'compilada'}

dados = {}
for nome, pasta in VERSOES.items():
    res = json.load(open(os.path.join(AQUI, pasta, 'out_sat' if SAT else 'out', 'resultados.json')))
    # so as medicoes do periodo em que o cliente estava rodando
    met = [{k: float(v) for k, v in l.items()} for l in csv.DictReader(open(os.path.join(AQUI, pasta, 'metricas.csv')))]
    met = [m for m in met if res['inicio'] <= m['t'] <= res['fim']]
    for m in met: m['t'] -= res['inicio']
    dados[nome] = (res, met)

linhas = {}
for nome, (res, met) in dados.items():
    rs = res['resultados']
    fila = [int(m['fila']) for m in met]
    tempos = [(datetime.fromisoformat(r['fim']) - datetime.fromisoformat(r['inicio'])).total_seconds() for r in rs]
    linhas[nome] = {
        'Nº total de imagens reconstruídas': len(rs),
        'Tempo total de execução': f"{res['fim'] - res['inicio']:.1f} s",
        'Nº médio de imagens na fila': f'{statistics.mean(fila):.2f}',
        'Moda de imagens na fila': statistics.mode(fila),
        'Máximo de imagens na fila': max(fila),
        'Tempo médio de reconstrução': f'{statistics.mean(tempos):.2f} s',
        'Recusas por saturação (503)': sum(r['recusas_503'] for r in rs),
        'CPU média': f"{statistics.mean(m['cpu'] for m in met):.0f} %",
        'Memória máxima': f"{max(m['mem_mb'] for m in met):.0f} MB",
    }


def grafico(chave, titulo, unidade):
    fig, ax = plt.subplots(figsize=(8, 3))
    for nome, (_, met) in dados.items():
        ax.plot([m['t'] for m in met], [m[chave] for m in met], label=nome)
    ax.set_title(titulo); ax.set_xlabel('tempo (s)'); ax.set_ylabel(unidade); ax.grid(alpha=.3); ax.legend()
    buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=100, bbox_inches='tight'); plt.close(fig)
    return f"<img src='data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}'>"


nomes = list(linhas)
tabela = ''.join(f"<tr><td>{k}</td>" + ''.join(f'<td>{linhas[n][k]}</td>' for n in nomes) + '</tr>' for k in linhas[nomes[0]])
titulo = 'Teste de saturação' if SAT else 'Relatório comparativo'
html = f"""<meta charset=utf-8><title>{titulo}</title><body style="font-family:sans-serif;max-width:900px;margin:auto">
<h1>{titulo}</h1>
<table border=1 cellpadding=6><tr><th></th>{''.join(f'<th>{n}</th>' for n in nomes)}</tr>{tabela}</table>
<h2>CPU</h2>{grafico('cpu', 'Consumo de CPU', '% da máquina')}
<h2>Memória</h2>{grafico('mem_mb', 'Consumo de memória', 'MB')}
<h2>Fila</h2>{grafico('fila', 'Imagens na fila de reconstrução', 'imagens')}"""
saida = os.path.join(AQUI, 'relatorio_saturacao.html' if SAT else 'relatorio_comparativo.html')
open(saida, 'w', encoding='utf-8').write(html)
for n in nomes: print(n, linhas[n])
print('->', saida)
