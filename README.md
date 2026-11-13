# APS de Reconstrução de Imagens — ICSM31 (UTFPR)

Projeto da disciplina **ICSM31 – Desenvolvimento Integrado de Sistemas**.

Um cliente envia sinais de ultrassom (`g`) para um servidor, que reconstrói a imagem (`f`) resolvendo `H · f = g` com os algoritmos **CGNR** ou **CGNE**. O servidor existe em duas versões, comparadas lado a lado:

| Versão | Linguagem | Pasta | Porta |
|---|---|---|---|
| Interpretada, não fortemente tipada | Python + numpy | `interpretada/` | 8001 |
| Compilada, fortemente tipada | C# (.NET 10) | `compilada/` | 8002 |

---

## 0. Baixar o projeto

```
git clone https://github.com/GeSabadin/DIS-desenvolvimento-integrado-sistemas.git
cd DIS-desenvolvimento-integrado-sistemas
```

## 1. Pré-requisitos

- **Python 3.10+** com as bibliotecas:
  ```
  pip install numpy psutil pillow matplotlib
  ```
- **.NET 10 SDK** (só para a versão compilada). No Windows:
  ```
  winget install Microsoft.DotNet.SDK.10
  ```
- ~4 GB de RAM livre (a matriz H do modelo 60×60 ocupa ~1,5 GB em cada servidor).

## 2. Dados

As matrizes **H** passam do limite de 100 MB do GitHub, por isso **não estão no repositório**. Baixe da página da disciplina no Moodle (seções "Dados de testes para o modelo 1" e "modelo 2"), descompacte e coloque em `data/`:

| Arquivo | Origem | Tamanho |
|---|---|---|
| `H-1.csv` | Modelo 1 (60×60): link "Matriz H" (vem como `H-1.csv.zip`) | 680 MB |
| `H-2.csv` | Modelo 2 (30×30): link "Matriz H" (vem como `H-2.csv.zip`) | 110 MB |

Os sinais (`G-1.csv`, `G-2.csv`, `A-60x60-1.csv`, `g-30x30-1.csv`, `g-30x30-2.csv`, `A-30x30-1.csv`) e `data/dados_teste/` (atividade 2) já estão no repositório.

No final, `data/` deve ficar assim:
```
data/
├── H-1.csv  H-2.csv
├── G-1.csv  G-2.csv  A-60x60-1.csv
├── g-30x30-1.csv  g-30x30-2.csv  A-30x30-1.csv
└── dados_teste/  (M.csv, N.csv, a.csv, MN.csv, aM.csv)
```

## 3. Rodar tudo de uma vez

No PowerShell, na raiz do projeto:
```
.\testar.ps1
```
Se o Windows bloquear o script: `powershell -ExecutionPolicy Bypass -File .\testar.ps1`

Leva ~8 minutos. O script:
1. roda a atividade 2 (operações básicas);
2. compila o C# e sobe os dois servidores;
3. roda o **teste normal** (3 clientes × 15 sinais) nas duas versões;
4. roda o **teste de saturação** (20 clientes × 5 sinais, quase sem pausa) nas duas versões;
5. gera `relatorio_comparativo.html` e `relatorio_saturacao.html` e desliga os servidores.

## 4. Rodar manualmente

São dois terminais. Primeiro sobe um servidor:

```
# Python                                  # C#
cd interpretada                           cd compilada
python server.py                          dotnet run -c Release
```

Na primeira execução, o servidor Python leva ~20 s pra subir porque converte as matrizes pra `.npy` (cache). Depois sobe em segundos. O C# leva ~16 s.

Depois, no outro terminal, na raiz do projeto:

```
python client.py py          # teste normal no Python  -> interpretada/out/
python client.py cs          # teste normal no C#      -> compilada/out/
python client.py py sat      # saturação no Python     -> interpretada/out_sat/
python client.py cs sat      # saturação no C#         -> compilada/out_sat/

python comparar.py           # -> relatorio_comparativo.html (precisa dos dois testes normais)
python comparar.py sat       # -> relatorio_saturacao.html   (precisa das duas saturações)

python interpretada/atividade2.py   # atividade 2: M·N, a·M, M·a
```

## 5. Como saber que funcionou

- O cliente imprime uma linha por imagem, por exemplo `c2-s01 CGNR 10 iteracoes`. No teste de saturação aparece também `(Nx 503)`, quantas vezes aquele pedido foi recusado antes de entrar.
- `*/out/relatorio.html` mostra as 45 imagens com cliente, sinal, algoritmo, início, fim e iterações.
- As imagens são fundo preto com pontos brancos. Os sinais `G-*` e `g-*` dão pontos bem definidos; os `A-*` saem granulados (é esperado).
- `atividade2.py` deve imprimir `True` duas vezes (bate com os gabaritos `MN.csv` e `aM.csv`).
- No teste de saturação, as **100** imagens devem sair mesmo com a fila batendo em 10 e centenas de recusas 503.

## 6. Estrutura

```
├── client.py             cliente (o mesmo para as duas versões)
├── comparar.py           gera os relatórios comparativo e de saturação
├── testar.ps1            roda tudo
├── data/                 matrizes e sinais
├── interpretada/
│   ├── server.py         servidor Python (CGNR, CGNE, fila, métricas)
│   └── atividade2.py     operações básicas com numpy/BLAS
└── compilada/
    ├── Program.cs        servidor C# (mesma lógica do Python)
    └── compilada.csproj
```

Cada servidor grava `metricas.csv` na própria pasta (CPU, memória e fila a cada 0,5 s). O cliente grava os resultados em `out/` ou `out_sat/` dentro da pasta da versão testada. Nada disso vai pro Git: é recriado pelos testes.

## 7. Como funciona

**Cliente (`client.py`)**
- Sorteia um plano com semente fixa (`random.seed(42)`): modelo (60×60 ou 30×30), arquivo de sinal, algoritmo, ganho e intervalo. A **mesma sequência** vai pras duas versões.
- Inicia 3 clientes simultâneos (threads), cada um enviando 15 sinais em intervalos aleatórios (0,2 a 2 s).
- Aplica o **ganho** no cliente: `γ(l) = k · (100 + l·√l / 20)` para cada amostra `l` de cada sensor, com `k` sorteado entre 0,5 e 2.
- Envia `POST` com JSON `{cliente, sinal, modelo, algoritmo, g}`. Se receber **503**, espera 1 s e tenta de novo.
- Monta a imagem em ordem de coluna (`order='F'`) e gera o relatório HTML.

**Servidores (`interpretada/server.py` e `compilada/Program.cs`)**
- Carregam as matrizes H na subida.
- Executam CGNR ou CGNE até `|‖r(i+1)‖ − ‖r(i)‖| < 1e-4` ou 10 iterações.
- Devolvem a imagem com cliente, sinal, algoritmo, início, fim e número de iterações.
- **Controle de saturação:** no máximo 2 reconstruções simultâneas e 10 pedidos na fila. Acima disso, respondem `503` e o cliente tenta de novo.
- O Python usa numpy (BLAS). O C# usa laços próprios paralelizados com `Parallel.For`.

## 8. Resultados de referência

Ryzen 5 5500, 16 GB RAM:

| | Python | C# |
|---|---|---|
| **Teste normal:** imagens / tempo total | 45 / 81,7 s | 45 / 59,9 s |
| Tempo médio de reconstrução | 3,33 s | 2,22 s |
| Fila média / moda | 0,44 / 0 | 0,38 / 0 |
| **Saturação:** imagens / tempo total | 100 / 142,1 s | 100 / 110,4 s |
| Fila média / moda / máx | 8,68 / 10 / 10 | 9,21 / 10 / 10 |
| Recusas 503 | 718 | 548 |

## 9. Observações

- O critério de parada do enunciado ("1e10-4") foi interpretado como `1e-4`.
- O enunciado define o fator de redução `c = ‖HᵀH‖₂` e a regularização `λ = max|Hᵀg| · 0,10`, mas o pseudocódigo do CGNR e do CGNE não os usa, então não foram implementados.
- "Ganho aleatório" foi interpretado como o fator `k` sorteado multiplicando a fórmula do ganho.
