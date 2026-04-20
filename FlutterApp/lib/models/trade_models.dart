import 'dart:convert';

class TradeSignal {
  final int id;
  final String symbol;
  final String direction;
  final double entry;
  final double tp1;
  final double sl;
  final String timeframe;
  final String createdAt;

  TradeSignal({
    required this.id,
    required this.symbol,
    required this.direction,
    required this.entry,
    required this.tp1,
    required this.sl,
    required this.timeframe,
    required this.createdAt,
  });

  factory TradeSignal.fromJson(Map<String, dynamic> json) {
    return TradeSignal(
      id: json['id'] as int,
      symbol: json['symbol'] as String,
      direction: json['direction'] as String,
      entry: json['entry']?.toDouble() ?? 0.0,
      tp1: json['tp']?.toDouble() ?? 0.0,
      sl: json['sl']?.toDouble() ?? 0.0,
      timeframe: json['timeframe'] as String,
      createdAt: json['created_at'] as String,
    );
  }
}

class MarketCandle {
  final DateTime date;
  final double open;
  final double high;
  final double low;
  final double close;
  final double volume;

  MarketCandle({
    required this.date,
    required this.open,
    required this.high,
    required this.low,
    required this.close,
    required this.volume,
  });
}
