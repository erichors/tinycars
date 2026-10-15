package tinycars;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import redis.clients.jedis.Jedis;
import redis.clients.jedis.JedisPool;
import redis.clients.jedis.JedisPoolConfig;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.URLDecoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.ThreadLocalRandom;

/**
 * TinyCars cart + checkout service (Java, JDK HttpServer).
 * Plain app code: no OpenTelemetry dependencies. Tracing comes from the OTel Operator
 * (inject-java annotation). Problem-pattern state is read from Redis (hash tc:flags).
 */
public class Main {
    static final Gson GSON = new Gson();
    static final String DB_URL = "jdbc:postgresql://" + env("DB_HOST", "postgres") + ":" + env("DB_PORT", "5432")
            + "/" + env("DB_NAME", "tinycars");
    static final String DB_USER = env("DB_USER", "tinycars");
    static final String DB_PASSWORD = env("DB_PASSWORD", "tinycars");
    static final String CATALOG_URL = env("CATALOG_URL", "http://catalog:8081");
    static final String INVENTORY_URL = env("INVENTORY_URL", "http://inventory:8083");
    static final JedisPool REDIS = new JedisPool(new JedisPoolConfig(), env("REDIS_HOST", "redis"),
            Integer.parseInt(env("REDIS_PORT", "6379")), 1500);
    static final HttpClient HTTP = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();
    static final int CART_TTL_SECONDS = 3600;

    static String env(String k, String d) {
        String v = System.getenv(k);
        return v == null || v.isEmpty() ? d : v;
    }

    // ------------------------------------------------------------ logging
    static void log(String level, String msg, Object... kv) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("ts", Instant.now().toString());
        m.put("level", level);
        m.put("service", "cart-checkout");
        m.put("msg", msg);
        for (int i = 0; i + 1 < kv.length; i += 2) m.put(String.valueOf(kv[i]), kv[i + 1]);
        System.out.println(GSON.toJson(m));
    }

    // ------------------------------------------------------------ problem-pattern flags
    static volatile Map<String, Integer> flagLevels = new HashMap<>();
    static volatile long flagsFetched = 0;

    static int flagLevel(String name) {
        long now = System.currentTimeMillis();
        if (now - flagsFetched > 2000) {
            flagsFetched = now;
            try (Jedis j = REDIS.getResource()) {
                Map<String, Integer> next = new HashMap<>();
                for (Map.Entry<String, String> e : j.hgetAll("tc:flags").entrySet()) {
                    JsonObject o = JsonParser.parseString(e.getValue()).getAsJsonObject();
                    boolean on = o.has("on") && o.get("on").getAsBoolean();
                    int level = o.has("level") ? o.get("level").getAsInt() : 1;
                    if (on) next.put(e.getKey(), level);
                }
                flagLevels = next;
            } catch (Exception ex) {
                log("WARN", "flag refresh failed", "error", String.valueOf(ex.getMessage()));
            }
        }
        return flagLevels.getOrDefault(name, 0);
    }

    // ------------------------------------------------------------ HTTP helpers
    static void send(HttpExchange ex, int status, Object body) throws IOException {
        byte[] bytes = GSON.toJson(body).getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().set("Content-Type", "application/json");
        ex.sendResponseHeaders(status, bytes.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(bytes);
        }
    }

    static Map<String, Object> err(String message) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("error", message);
        return m;
    }

    static JsonObject readBody(HttpExchange ex) throws IOException {
        String s = new String(ex.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
        return s.isBlank() ? new JsonObject() : JsonParser.parseString(s).getAsJsonObject();
    }

    static String query(HttpExchange ex, String key, String dflt) {
        String q = ex.getRequestURI().getRawQuery();
        if (q == null) return dflt;
        for (String part : q.split("&")) {
            String[] kv = part.split("=", 2);
            if (kv[0].equals(key) && kv.length == 2) return URLDecoder.decode(kv[1], StandardCharsets.UTF_8);
        }
        return dflt;
    }

    static JsonElement httpJson(String method, String url, Object body) throws IOException, InterruptedException {
        HttpRequest.Builder b = HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(10))
                .header("Content-Type", "application/json");
        b = body == null ? b.method(method, HttpRequest.BodyPublishers.noBody())
                : b.method(method, HttpRequest.BodyPublishers.ofString(GSON.toJson(body)));
        HttpResponse<String> r = HTTP.send(b.build(), HttpResponse.BodyHandlers.ofString());
        JsonObject out = new JsonObject();
        out.addProperty("_status", r.statusCode());
        if (r.body() != null && !r.body().isBlank()) {
            JsonElement parsed = JsonParser.parseString(r.body());
            if (parsed.isJsonObject()) {
                parsed.getAsJsonObject().addProperty("_status", r.statusCode());
                return parsed;
            }
            out.add("data", parsed);
        }
        return out;
    }

    // ------------------------------------------------------------ cart (Redis)
    static JsonObject loadCart(String id) {
        try (Jedis j = REDIS.getResource()) {
            String raw = j.get("tc:cart:" + id);
            if (raw != null) return JsonParser.parseString(raw).getAsJsonObject();
        }
        JsonObject cart = new JsonObject();
        cart.addProperty("id", id);
        cart.addProperty("currency", "USD");
        cart.add("items", new JsonArray());
        return cart;
    }

    static void saveCart(JsonObject cart) {
        try (Jedis j = REDIS.getResource()) {
            j.setex("tc:cart:" + cart.get("id").getAsString(), CART_TTL_SECONDS, GSON.toJson(cart));
        }
    }

    static void handleCart(HttpExchange ex, String[] parts) throws Exception {
        // /cart/{id}  or  /cart/{id}/items
        if (parts.length < 2) { send(ex, 404, err("not found")); return; }
        String id = parts[1];
        String method = ex.getRequestMethod();
        if (parts.length == 2 && method.equals("GET")) {
            send(ex, 200, GSON.fromJson(loadCart(id), Object.class));
        } else if (parts.length == 2 && method.equals("DELETE")) {
            try (Jedis j = REDIS.getResource()) { j.del("tc:cart:" + id); }
            send(ex, 200, Map.of("deleted", id));
        } else if (parts.length == 3 && parts[2].equals("items") && method.equals("POST")) {
            JsonObject body = readBody(ex);
            String sku = body.get("sku").getAsString();
            int qty = body.has("qty") ? body.get("qty").getAsInt() : 1;
            String currency = body.has("currency") ? body.get("currency").getAsString() : "USD";
            JsonElement product = httpJson("GET", CATALOG_URL + "/products/" + sku, null);
            int status = product.getAsJsonObject().get("_status").getAsInt();
            if (status != 200) { send(ex, status == 404 ? 404 : 502, err("catalog lookup failed (" + status + ")")); return; }
            JsonObject p = product.getAsJsonObject();
            double unit = p.get(currency.equals("GBP") ? "price_gbp" : "price_usd").getAsDouble();
            JsonObject cart = loadCart(id);
            if (cart.getAsJsonArray("items").size() == 0) cart.addProperty("currency", currency);
            JsonArray items = cart.getAsJsonArray("items");
            boolean merged = false;
            for (JsonElement el : items) {
                JsonObject it = el.getAsJsonObject();
                if (it.get("sku").getAsString().equals(sku)) {
                    it.addProperty("qty", it.get("qty").getAsInt() + qty);
                    merged = true;
                }
            }
            if (!merged) {
                JsonObject it = new JsonObject();
                it.addProperty("sku", sku);
                it.addProperty("name", p.get("name").getAsString());
                it.addProperty("image", p.get("image").getAsString());
                it.addProperty("qty", qty);
                it.addProperty("unit_price", unit);
                items.add(it);
            }
            saveCart(cart);
            send(ex, 200, GSON.fromJson(cart, Object.class));
        } else {
            send(ex, 405, err("method not allowed"));
        }
    }

    // ------------------------------------------------------------ checkout
    static void release(List<Map<String, Object>> reserved) {
        for (Map<String, Object> r : reserved) {
            try {
                httpJson("POST", INVENTORY_URL + "/restock", r);
            } catch (Exception e) {
                log("ERROR", "failed to release stock", "sku", r.get("sku"), "error", String.valueOf(e.getMessage()));
            }
        }
    }

    static void handleCheckout(HttpExchange ex) throws Exception {
        JsonObject body = readBody(ex);
        String cartId = body.get("cartId").getAsString();
        String email = body.has("email") ? body.get("email").getAsString() : "guest@example.com";
        String location = body.has("location") ? body.get("location").getAsString() : "warehouse";
        String channel = body.has("channel") ? body.get("channel").getAsString() : "web";
        String card = body.has("cardNumber") ? body.get("cardNumber").getAsString() : "4242424242424242";

        JsonObject cart = loadCart(cartId);
        JsonArray items = cart.getAsJsonArray("items");
        if (items.size() == 0) { send(ex, 400, err("cart is empty")); return; }
        String currency = cart.get("currency").getAsString();

        // 1) reserve stock
        List<Map<String, Object>> reserved = new ArrayList<>();
        double total = 0;
        for (JsonElement el : items) {
            JsonObject it = el.getAsJsonObject();
            Map<String, Object> req = new LinkedHashMap<>();
            req.put("sku", it.get("sku").getAsString());
            req.put("qty", it.get("qty").getAsInt());
            req.put("location", location);
            JsonObject res = httpJson("POST", INVENTORY_URL + "/reserve", req).getAsJsonObject();
            int status = res.get("_status").getAsInt();
            if (status == 200) {
                reserved.add(req);
                total += it.get("unit_price").getAsDouble() * it.get("qty").getAsInt();
            } else {
                release(reserved);
                log("WARN", "reserve failed", "sku", req.get("sku"), "status", status, "location", location);
                send(ex, status == 409 ? 409 : 502, err(status == 409 ? "out of stock: " + req.get("sku") : "inventory unavailable"));
                return;
            }
        }

        // 2) payment (simulated). Pattern: checkout_dependency_stall
        int stall = flagLevel("checkout_dependency_stall");
        if (stall > 0) {
            log("WARN", "payment processor not responding", "pattern", "checkout_dependency_stall", "level", stall);
            Thread.sleep(stall * 2000L);
            release(reserved);
            log("ERROR", "payment processor timeout", "pattern", "checkout_dependency_stall", "cartId", cartId);
            send(ex, 504, err("payment processor timed out"));
            return;
        }
        boolean declined = card.startsWith("4000") || ThreadLocalRandom.current().nextDouble() < 0.03;
        String orderId = "ORD-" + UUID.randomUUID().toString().substring(0, 8).toUpperCase();
        if (declined) release(reserved);

        // 3) persist order
        try (Connection c = DriverManager.getConnection(DB_URL, DB_USER, DB_PASSWORD)) {
            c.setAutoCommit(false);
            try (PreparedStatement ps = c.prepareStatement(
                    "INSERT INTO orders(order_id,channel,location,customer_email,currency,total,status,payment_status) VALUES (?,?,?,?,?,?,?,?)")) {
                ps.setString(1, orderId);
                ps.setString(2, channel);
                ps.setString(3, location);
                ps.setString(4, email);
                ps.setString(5, currency);
                ps.setBigDecimal(6, java.math.BigDecimal.valueOf(Math.round(total * 100) / 100.0));
                ps.setString(7, declined ? "declined" : "completed");
                ps.setString(8, declined ? "declined" : "approved");
                ps.executeUpdate();
            }
            if (!declined) {
                try (PreparedStatement ps = c.prepareStatement(
                        "INSERT INTO order_items(order_id,sku,qty,unit_price) VALUES (?,?,?,?)")) {
                    for (JsonElement el : items) {
                        JsonObject it = el.getAsJsonObject();
                        ps.setString(1, orderId);
                        ps.setString(2, it.get("sku").getAsString());
                        ps.setInt(3, it.get("qty").getAsInt());
                        ps.setBigDecimal(4, java.math.BigDecimal.valueOf(it.get("unit_price").getAsDouble()));
                        ps.addBatch();
                    }
                    ps.executeBatch();
                }
            }
            c.commit();
        }
        try (Jedis j = REDIS.getResource()) { j.del("tc:cart:" + cartId); }

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("order_id", orderId);
        out.put("status", declined ? "declined" : "completed");
        out.put("total", Math.round(total * 100) / 100.0);
        out.put("currency", currency);
        out.put("channel", channel);
        out.put("location", location);
        out.put("email", email);
        log(declined ? "WARN" : "INFO", declined ? "payment declined" : "order completed", "order_id", orderId,
                "channel", channel, "location", location, "total", total, "currency", currency, "email", email);
        send(ex, declined ? 402 : 201, out);
    }

    // ------------------------------------------------------------ orders / stats
    static void handleOrders(HttpExchange ex, String[] parts) throws Exception {
        try (Connection c = DriverManager.getConnection(DB_URL, DB_USER, DB_PASSWORD)) {
            if (parts.length == 2 && parts[1].equals("recent")) {
                int limit = Math.min(Integer.parseInt(query(ex, "limit", "10")), 50);
                List<Map<String, Object>> rows = new ArrayList<>();
                try (PreparedStatement ps = c.prepareStatement(
                        "SELECT order_id, created_at, channel, location, customer_email, currency, total, status FROM orders ORDER BY created_at DESC LIMIT ?")) {
                    ps.setInt(1, limit);
                    try (ResultSet rs = ps.executeQuery()) {
                        while (rs.next()) {
                            Map<String, Object> m = new LinkedHashMap<>();
                            m.put("order_id", rs.getString(1));
                            m.put("created_at", rs.getTimestamp(2).toInstant().toString());
                            m.put("channel", rs.getString(3));
                            m.put("location", rs.getString(4));
                            m.put("email", rs.getString(5));
                            m.put("currency", rs.getString(6));
                            m.put("total", rs.getDouble(7));
                            m.put("status", rs.getString(8));
                            rows.add(m);
                        }
                    }
                }
                send(ex, 200, rows);
            } else if (parts.length == 2 && parts[1].equals("stats")) {
                Map<String, Object> m = new LinkedHashMap<>();
                try (PreparedStatement ps = c.prepareStatement(
                        "SELECT coalesce(sum(oi.qty),0), count(DISTINCT o.order_id) FROM orders o JOIN order_items oi USING(order_id) WHERE o.status = 'completed'");
                     ResultSet rs = ps.executeQuery()) {
                    rs.next();
                    m.put("cars_sold", rs.getLong(1));
                    m.put("orders", rs.getLong(2));
                }
                send(ex, 200, m);
            } else {
                send(ex, 404, err("not found"));
            }
        }
    }

    // ------------------------------------------------------------ server
    public static void main(String[] args) throws Exception {
        int port = Integer.parseInt(env("PORT", "8082"));
        HttpServer server = HttpServer.create(new InetSocketAddress("0.0.0.0", port), 0);
        server.createContext("/", ex -> {
            String path = ex.getRequestURI().getPath();
            String[] parts = path.replaceAll("^/+", "").split("/");
            try {
                if (path.equals("/healthz")) send(ex, 200, Map.of("status", "ok"));
                else if (parts[0].equals("cart")) handleCart(ex, parts);
                else if (parts[0].equals("checkout") && ex.getRequestMethod().equals("POST")) handleCheckout(ex);
                else if (parts[0].equals("orders")) handleOrders(ex, parts);
                else send(ex, 404, err("not found"));
            } catch (Exception e) {
                log("ERROR", "request failed", "path", path, "error", e.toString());
                try { send(ex, 500, err("internal error")); } catch (IOException ignored) { }
            } finally {
                ex.close();
            }
        });
        server.setExecutor(Executors.newFixedThreadPool(32));
        server.start();
        log("INFO", "cart-checkout started", "port", port);
    }
}
