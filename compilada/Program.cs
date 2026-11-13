using System.Diagnostics;
using System.Globalization;

// carrega as matrizes H direto do CSV (demora uns segundos, so na subida)
var H = new Dictionary<int, Matriz> { [1] = Matriz.Carregar("../data/H-1.csv"), [2] = Matriz.Carregar("../data/H-2.csv") };
GC.Collect();

var cpuLivre = new SemaphoreSlim(2);  // no maximo 2 reconstrucoes ao mesmo tempo
int fila = 0;                          // quantos estao esperando
const int MAX_FILA = 10;               // controle de saturacao: acima disso responde 503

var builder = WebApplication.CreateBuilder();
builder.Logging.ClearProviders();
var app = builder.Build();

app.MapPost("/", async (Pedido req) =>
{
    if (Interlocked.Increment(ref fila) > MAX_FILA)
    {
        Interlocked.Decrement(ref fila);
        return Results.Json(new { erro = "servidor cheio, tenta depois" }, statusCode: 503);
    }
    await cpuLivre.WaitAsync();
    Interlocked.Decrement(ref fila);
    try
    {
        var inicio = DateTime.Now;
        var (f, it) = req.algoritmo == "CGNE" ? Algoritmos.Cgne(H[req.modelo], req.g) : Algoritmos.Cgnr(H[req.modelo], req.g);
        var fim = DateTime.Now;
        return Results.Json(new
        {
            req.cliente, req.sinal, req.algoritmo, req.modelo,
            inicio = inicio.ToString("yyyy-MM-dd HH:mm:ss.ffffff"),
            fim = fim.ToString("yyyy-MM-dd HH:mm:ss.ffffff"),
            iteracoes = it, imagem = f
        });
    }
    finally { cpuLivre.Release(); }
});

// grava CPU, memoria e fila pro relatorio
_ = Task.Run(async () =>
{
    var p = Process.GetCurrentProcess();
    using var arq = new StreamWriter("metricas.csv");
    arq.WriteLine("t,cpu,mem_mb,fila");
    var t0 = Stopwatch.StartNew();
    var cpuAntes = p.TotalProcessorTime; var tAntes = t0.Elapsed;
    while (true)
    {
        await Task.Delay(500);
        p.Refresh();
        var cpu = (p.TotalProcessorTime - cpuAntes).TotalMilliseconds / (t0.Elapsed - tAntes).TotalMilliseconds / Environment.ProcessorCount * 100;
        cpuAntes = p.TotalProcessorTime; tAntes = t0.Elapsed;
        arq.WriteLine(string.Format(CultureInfo.InvariantCulture, "{0:F2},{1:F1},{2},{3}", DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0, cpu, p.WorkingSet64 / (1 << 20), fila));
        arq.Flush();
    }
});

Console.WriteLine("servidor C# no ar: http://127.0.0.1:8002");
app.Run("http://127.0.0.1:8002");


record Pedido(string cliente, string sinal, int modelo, string algoritmo, double[] g);

class Matriz
{
    public int Linhas, Colunas;
    public double[] V = [];  // guardada linha por linha

    public static Matriz Carregar(string caminho)
    {
        var m = new Matriz();
        var valores = new List<double>();
        foreach (var linha in File.ReadLines(caminho))
        {
            var partes = linha.Split(',');
            m.Colunas = partes.Length;
            foreach (var s in partes) valores.Add(double.Parse(s, CultureInfo.InvariantCulture));
            m.Linhas++;
        }
        m.V = valores.ToArray();
        Console.WriteLine($"{caminho}: {m.Linhas} x {m.Colunas}");
        return m;
    }

    // y = H * x  (cada linha em paralelo)
    public double[] Mul(double[] x)
    {
        var y = new double[Linhas];
        Parallel.For(0, Linhas, i =>
        {
            double s = 0; int b = i * Colunas;
            for (int j = 0; j < Colunas; j++) s += V[b + j] * x[j];
            y[i] = s;
        });
        return y;
    }

    // y = H^T * x  (cada thread soma um bloco de linhas, depois junta)
    public double[] MulT(double[] x)
    {
        var y = new double[Colunas];
        var trava = new object();
        Parallel.For(0, Environment.ProcessorCount, () => new double[Colunas], (bloco, _, parcial) =>
        {
            int tam = (Linhas + Environment.ProcessorCount - 1) / Environment.ProcessorCount;
            for (int i = bloco * tam; i < Math.Min(Linhas, (bloco + 1) * tam); i++)
            {
                double xi = x[i]; if (xi == 0) continue;
                int b = i * Colunas;
                for (int j = 0; j < Colunas; j++) parcial[j] += V[b + j] * xi;
            }
            return parcial;
        }, parcial => { lock (trava) for (int j = 0; j < Colunas; j++) y[j] += parcial[j]; });
        return y;
    }
}

static class Algoritmos
{
    static double Dot(double[] a, double[] b) { double s = 0; for (int i = 0; i < a.Length; i++) s += a[i] * b[i]; return s; }

    public static (double[], int) Cgnr(Matriz H, double[] g)
    {
        var f = new double[H.Colunas]; var r = (double[])g.Clone(); var z = H.MulT(r); var p = (double[])z.Clone();
        int i;
        for (i = 1; i <= 10; i++)
        {
            var w = H.Mul(p);
            double alpha = Dot(z, z) / Dot(w, w);
            for (int j = 0; j < f.Length; j++) f[j] += alpha * p[j];
            var rNovo = new double[r.Length];
            for (int j = 0; j < r.Length; j++) rNovo[j] = r[j] - alpha * w[j];
            var zNovo = H.MulT(rNovo);
            double beta = Dot(zNovo, zNovo) / Dot(z, z);
            for (int j = 0; j < p.Length; j++) p[j] = zNovo[j] + beta * p[j];
            double erro = Math.Abs(Math.Sqrt(Dot(rNovo, rNovo)) - Math.Sqrt(Dot(r, r)));
            r = rNovo; z = zNovo;
            if (erro < 1e-4) break;
        }
        return (f, Math.Min(i, 10));
    }

    public static (double[], int) Cgne(Matriz H, double[] g)
    {
        var f = new double[H.Colunas]; var r = (double[])g.Clone(); var p = H.MulT(r);
        int i;
        for (i = 1; i <= 10; i++)
        {
            double alpha = Dot(r, r) / Dot(p, p);
            for (int j = 0; j < f.Length; j++) f[j] += alpha * p[j];
            var hp = H.Mul(p);
            var rNovo = new double[r.Length];
            for (int j = 0; j < r.Length; j++) rNovo[j] = r[j] - alpha * hp[j];
            double beta = Dot(rNovo, rNovo) / Dot(r, r);
            var htr = H.MulT(rNovo);
            for (int j = 0; j < p.Length; j++) p[j] = htr[j] + beta * p[j];
            double erro = Math.Abs(Math.Sqrt(Dot(rNovo, rNovo)) - Math.Sqrt(Dot(r, r)));
            r = rNovo;
            if (erro < 1e-4) break;
        }
        return (f, Math.Min(i, 10));
    }
}
