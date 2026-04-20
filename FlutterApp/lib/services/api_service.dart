import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';
import '../models/trade_models.dart';

class ApiService {
  static const String baseUrl = "http://192.168.100.10:8000";
  static const String wsUrl = "ws://192.168.100.10:8000/ws";

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

  /// Panic Button: Closes all positions
  Future<void> panicClose() async {
    await http.post(
      Uri.parse("$baseUrl/api/trade"),
      body: jsonEncode({"action": "close_all"}),
      headers: {"Content-Type": "application/json"},
    );
  }

  /// Updates global bot settings (Profile, Demo, Auto-Trade)
  Future<void> updateSettings(Map<String, dynamic> settings) async {
    await http.post(
      Uri.parse("$baseUrl/api/settings"),
      body: jsonEncode(settings),
      headers: {"Content-Type": "application/json"},
    );
  }
}
