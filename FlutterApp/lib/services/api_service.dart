import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';
import '../models/trade_models.dart';

/// Sentinel V4 — Live GCP Bot API Service
/// Endpoint: http://34.27.93.107:8080
class ApiService {
  // ── Live GCP Bot Endpoints ───────────────────────────────────────────
  static const String baseUrl = "http://34.27.93.107:8080";
  static const String wsUrl   = "ws://34.27.93.107:8080/ws";

  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  WebSocketChannel? _channel;
  StreamController<Map<String, dynamic>>? _streamController;

  // ── WebSocket Real-Time Stream ────────────────────────────────────────
  Stream<Map<String, dynamic>> get liveStream {
    _streamController ??= StreamController<Map<String, dynamic>>.broadcast(
      onListen: _connectWebSocket,
      onCancel: _disconnectWebSocket,
    );
    return _streamController!.stream;
  }

  void _connectWebSocket() {
    _channel = WebSocketChannel.connect(Uri.parse(wsUrl));
    _channel!.stream.listen(
      (event) {
        try {
          final data = jsonDecode(event) as Map<String, dynamic>;
          _streamController?.add(data);
        } catch (_) {}
      },
      onError: (_) => Future.delayed(const Duration(seconds: 3), _connectWebSocket),
      onDone: ()  => Future.delayed(const Duration(seconds: 3), _connectWebSocket),
    );
  }

  void _disconnectWebSocket() {
    _channel?.sink.close();
    _channel = null;
  }

  // ── REST API Helpers ──────────────────────────────────────────────────
  Future<Map<String, dynamic>> _get(String path) async {
    try {
      final res = await http.get(Uri.parse("$baseUrl$path"))
          .timeout(const Duration(seconds: 10));
      if (res.statusCode == 200) return jsonDecode(res.body);
    } catch (_) {}
    return {};
  }

  Future<Map<String, dynamic>> _post(String path, Map<String, dynamic> body) async {
    try {
      final res = await http.post(
        Uri.parse("$baseUrl$path"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 10));
      if (res.statusCode == 200) return jsonDecode(res.body);
    } catch (_) {}
    return {"status": "error"};
  }

  // ── Bot State ─────────────────────────────────────────────────────────
  /// Full bot state: balance, active_trades, signals, markets, etc.
  Future<Map<String, dynamic>> fetchStatus() => _get("/api/status");

  // ── Signals ───────────────────────────────────────────────────────────
  /// Last 20 signals from the database.
  Future<List<TradeSignal>> fetchSignals() async {
    try {
      final res = await http.get(Uri.parse("$baseUrl/api/signals"))
          .timeout(const Duration(seconds: 10));
      if (res.statusCode == 200) {
        final List<dynamic> data = jsonDecode(res.body);
        return data.map((item) => TradeSignal.fromJson(item)).toList();
      }
    } catch (_) {}
    return [];
  }

  // ── Analytics ─────────────────────────────────────────────────────────
  /// Pattern win-rate analytics map.
  Future<Map<String, dynamic>> fetchAnalytics() => _get("/api/analytics");

  // ── Settings ──────────────────────────────────────────────────────────
  /// Toggle bot on/off, set demo/live mode, change active broker.
  Future<Map<String, dynamic>> updateSettings(Map<String, dynamic> settings) =>
      _post("/api/settings", settings);

  Future<Map<String, dynamic>> activateBot()   => updateSettings({"is_bot_active": true});
  Future<Map<String, dynamic>> deactivateBot() => updateSettings({"is_bot_active": false});
  Future<Map<String, dynamic>> setDemoMode(bool demo) => updateSettings({"demo_mode": demo});

  // ── Market Management ─────────────────────────────────────────────────
  Future<Map<String, dynamic>> addMarket(String symbol) =>
      _post("/api/market/add", {"symbol": symbol});

  Future<Map<String, dynamic>> removeMarket(String symbol) =>
      _post("/api/market/remove", {"symbol": symbol});

  Future<Map<String, dynamic>> toggleMarket(String symbol) =>
      _post("/api/market/toggle", {"symbol": symbol});

  // ── Trade Controls ────────────────────────────────────────────────────
  Future<Map<String, dynamic>> closePosition(String symbol) =>
      _post("/api/close_position", {"symbol": symbol});

  Future<Map<String, dynamic>> panicClose() =>
      _post("/api/panic_close", {});

  // ── TradingView Webhook Simulator (for testing) ───────────────────────
  Future<Map<String, dynamic>> simulateSignal({
    required String ticker,
    required String action,
    required double price,
    required double tp,
    required double sl,
    String pattern = "Manual Test",
  }) =>
      _post("/api/webhook/tradingview", {
        "secret":  "SENTINEL_V4_SECRET",
        "action":  action,
        "ticker":  ticker,
        "price":   price,
        "tp":      tp,
        "sl":      sl,
        "pattern": pattern,
        "score":   95.0,
      });
}
