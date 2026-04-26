import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';
import '../models/trade_models.dart';

class ApiService {
  // Configured for Jewel Elite Global VPS Connectivity
  static const String baseUrl = "http://34.26.143.224:8000";
  static const String wsUrl = "ws://34.26.143.224:8000/ws";

  /// Connects to the real-time websocket stream
  Stream<dynamic> get marketStream {
    final channel = WebSocketChannel.connect(Uri.parse(wsUrl));
    return channel.stream.map((event) => jsonDecode(event));
  }

  /// Fetches the latest signals 
  Future<List<TradeSignal>> fetchSignals() async {
    final response = await http.get(Uri.parse("$baseUrl/api/signals"));
    if (response.statusCode == 200) {
      List<dynamic> data = jsonDecode(response.body);
      return data.map((item) => TradeSignal.fromJson(item)).toList();
    }
    return [];
  }

  /// Updates global bot settings (Profile, Demo, Auto-Trade, Bias)
  Future<void> updateSettings(Map<String, dynamic> settings) async {
    await http.post(
      Uri.parse("$baseUrl/api/settings"),
      body: jsonEncode(settings),
      headers: {"Content-Type": "application/json"},
    );
  }
}
