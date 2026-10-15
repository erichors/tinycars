// TinyCars inventory service (.NET 8 minimal API).
// Plain app code: no OpenTelemetry packages. Tracing comes from the OTel Operator (inject-dotnet).
// Problem-pattern state is read from Redis (hash tc:flags).
using System.Text.Json;
using Npgsql;
using StackExchange.Redis;

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls("http://0.0.0.0:8083");
builder.Logging.ClearProviders();
builder.Logging.AddJsonConsole();

string Env(string k, string d) => Environment.GetEnvironmentVariable(k) ?? d;

// Small pool on purpose: inventory_pool_exhaustion saturates it.
var connString =
    $"Host={Env("DB_HOST", "postgres")};Port={Env("DB_PORT", "5432")};Database={Env("DB_NAME", "tinycars")};" +
    $"Username={Env("DB_USER", "tinycars")};Password={Env("DB_PASSWORD", "tinycars")};" +
    "Maximum Pool Size=6;Timeout=4;Command Timeout=30";
builder.Services.AddSingleton(NpgsqlDataSource.Create(connString));
builder.Services.AddSingleton<Flags>();

var app = builder.Build();
var log = app.Logger;

app.MapGet("/healthz", () => Results.Ok(new { status = "ok" }));

app.MapGet("/stock", async (string? location, NpgsqlDataSource ds, Flags flags) =>
{
    await using var conn = await Open(ds, flags, log, "list");
    await using var cmd = new NpgsqlCommand(
        "SELECT sku, location, qty FROM stock WHERE (@loc::text IS NULL OR location = @loc) ORDER BY sku, location", conn);
    cmd.Parameters.AddWithValue("loc", (object?)location ?? DBNull.Value);
    return Results.Ok(await ReadStock(cmd));
});

app.MapGet("/stock/{sku}", async (string sku, string? location, NpgsqlDataSource ds, Flags flags) =>
{
    await using var conn = await Open(ds, flags, log, sku);
    await SlowQueryIfEnabled(conn, flags, log, sku);
    await using var cmd = new NpgsqlCommand(
        "SELECT sku, location, qty FROM stock WHERE sku = @sku AND (@loc::text IS NULL OR location = @loc) ORDER BY location", conn);
    cmd.Parameters.AddWithValue("sku", sku);
    cmd.Parameters.AddWithValue("loc", (object?)location ?? DBNull.Value);
    var rows = await ReadStock(cmd);
    return rows.Count == 0 ? Results.NotFound(new { error = "unknown sku" }) : Results.Ok(rows);
});

app.MapPost("/reserve", async (StockChange req, NpgsqlDataSource ds, Flags flags) =>
{
    if (req.qty <= 0) return Results.BadRequest(new { error = "qty must be positive" });
    await using var conn = await Open(ds, flags, log, req.sku);
    await SlowQueryIfEnabled(conn, flags, log, req.sku);
    await using var cmd = new NpgsqlCommand(
        "UPDATE stock SET qty = qty - @q, updated_at = now() WHERE sku = @sku AND location = @loc AND qty >= @q RETURNING qty", conn);
    cmd.Parameters.AddWithValue("q", req.qty);
    cmd.Parameters.AddWithValue("sku", req.sku);
    cmd.Parameters.AddWithValue("loc", req.location);
    var remaining = await cmd.ExecuteScalarAsync();
    if (remaining is null)
    {
        log.LogWarning("insufficient stock sku={Sku} location={Location} requested={Qty}", req.sku, req.location, req.qty);
        return Results.Conflict(new { error = "insufficient stock", sku = req.sku, location = req.location });
    }
    return Results.Ok(new { sku = req.sku, location = req.location, remaining = Convert.ToInt32(remaining) });
});

app.MapPost("/restock", async (StockChange req, NpgsqlDataSource ds, Flags flags) =>
{
    if (req.qty <= 0) return Results.BadRequest(new { error = "qty must be positive" });
    await using var conn = await Open(ds, flags, log, req.sku);
    await using var cmd = new NpgsqlCommand(
        "INSERT INTO stock(sku, location, qty) VALUES (@sku, @loc, @q) " +
        "ON CONFLICT (sku, location) DO UPDATE SET qty = stock.qty + @q, updated_at = now() RETURNING qty", conn);
    cmd.Parameters.AddWithValue("sku", req.sku);
    cmd.Parameters.AddWithValue("loc", req.location);
    cmd.Parameters.AddWithValue("q", req.qty);
    var qty = await cmd.ExecuteScalarAsync();
    log.LogInformation("restocked sku={Sku} location={Location} added={Qty}", req.sku, req.location, req.qty);
    return Results.Ok(new { sku = req.sku, location = req.location, qty = Convert.ToInt32(qty) });
});

app.Run();

// ---------------------------------------------------------------- helpers
static async Task<NpgsqlConnection> Open(NpgsqlDataSource ds, Flags flags, ILogger log, string sku)
{
    var down = await flags.Level("inventory_db_not_responding");
    if (down > 0)
    {
        log.LogError("pattern=inventory_db_not_responding could not connect to server: connection refused (simulated) sku={Sku}", sku);
        throw new InvalidOperationException("database is not responding (simulated)");
    }
    var conn = await ds.OpenConnectionAsync(); // throws a pool timeout when exhausted
    var hold = await flags.Level("inventory_pool_exhaustion");
    if (hold > 0)
    {
        log.LogWarning("pattern=inventory_pool_exhaustion holding connection {Seconds}s sku={Sku}", hold * 1.5, sku);
        await Task.Delay(TimeSpan.FromSeconds(hold * 1.5));
    }
    return conn;
}

static async Task SlowQueryIfEnabled(NpgsqlConnection conn, Flags flags, ILogger log, string sku)
{
    var level = await flags.Level("inventory_slow_query");
    if (level == 0) return;
    log.LogWarning("pattern=inventory_slow_query running slow query level={Level} sku={Sku}", level, sku);
    // order_items has no index on sku, so this is a sequential scan plus an artificial sleep.
    await using var cmd = new NpgsqlCommand(
        "SELECT pg_sleep(@s), count(*) FROM order_items WHERE sku = @sku", conn);
    cmd.Parameters.AddWithValue("s", level * 0.8);
    cmd.Parameters.AddWithValue("sku", sku);
    await cmd.ExecuteScalarAsync();
}

static async Task<List<object>> ReadStock(NpgsqlCommand cmd)
{
    var rows = new List<object>();
    await using var r = await cmd.ExecuteReaderAsync();
    while (await r.ReadAsync())
        rows.Add(new { sku = r.GetString(0), location = r.GetString(1), qty = r.GetInt32(2) });
    return rows;
}

record StockChange(string sku, int qty, string location);

class Flags
{
    private readonly Lazy<ConnectionMultiplexer> _redis = new(() =>
        ConnectionMultiplexer.Connect(
            (Environment.GetEnvironmentVariable("REDIS_HOST") ?? "redis") + ":" +
            (Environment.GetEnvironmentVariable("REDIS_PORT") ?? "6379") + ",abortConnect=false,connectTimeout=1500,syncTimeout=1500"));
    private Dictionary<string, int> _levels = new();
    private DateTime _fetched = DateTime.MinValue;

    public async Task<int> Level(string name)
    {
        if ((DateTime.UtcNow - _fetched).TotalSeconds > 2)
        {
            _fetched = DateTime.UtcNow;
            try
            {
                var entries = await _redis.Value.GetDatabase().HashGetAllAsync("tc:flags");
                var next = new Dictionary<string, int>();
                foreach (var e in entries)
                {
                    using var doc = JsonDocument.Parse(e.Value.ToString());
                    var root = doc.RootElement;
                    var on = root.TryGetProperty("on", out var o) && o.ValueKind == JsonValueKind.True;
                    var level = root.TryGetProperty("level", out var l) && l.ValueKind == JsonValueKind.Number ? l.GetInt32() : 1;
                    if (on) next[e.Name.ToString()] = level;
                }
                _levels = next;
            }
            catch (Exception) { /* keep last known flags */ }
        }
        return _levels.TryGetValue(name, out var v) ? v : 0;
    }
}
