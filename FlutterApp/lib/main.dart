import 'package:flutter/material.dart';
import 'dart:async';
import 'services/api_service.dart';
import 'models/trade_models.dart';

void main() {
  runApp(const JewelEliteTerminal());
}

class TerminalColors {
  static const bg = Color(0xFF0A0A0A);
  static const surface = Color(0xFF141414);
  static const accentCyan = Color(0xFF00E5FF);
  static const accentYellow = Color(0xFFFBC02D);
  static const accentGreen = Color(0xFF00C853);
  static const accentRed = Color(0xFFFF1744);
  static const textSecondary = Color(0xFF666666);
  static const gridLine = Color(0xFF1A1A1A);
}

class JewelEliteTerminal extends StatelessWidget {
  const JewelEliteTerminal({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: TerminalColors.bg,
      ),
      home: const MainTerminalView(),
    );
  }
}

class MainTerminalView extends StatefulWidget {
  const MainTerminalView({super.key});

  @override
  State<MainTerminalView> createState() => _MainTerminalViewState();
}

class _MainTerminalViewState extends State<MainTerminalView> {
  final ApiService _api = ApiService();
  int _selectedIndex = 0;
  
  String _balance = "103,500.00";
  String _equity = "98,420.00";
  bool _isDemo = true;
  List<TradeSignal> _signals = [];

  @override
  void initState() {
    super.initState();
    _startListening();
  }

  void _startListening() {
    _api.marketStream.listen((data) {
      if (mounted) {
        setState(() {
          if (data['balance'] != null) _balance = data['balance'].toStringAsFixed(2);
          if (data['demo_mode'] != null) _isDemo = data['demo_mode'];
        });
      }
    });
    _fetchSignals();
  }

  Future<void> _fetchSignals() async {
    final signals = await _api.fetchSignals();
    if (mounted) setState(() => _signals = signals);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          _buildGridBackground(),
          SafeArea(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildHeader(),
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    child: Column(
                      children: [
                        _buildEquityCard(),
                        const SizedBox(height: 20),
                        _buildRiskManagementCard(),
                        const SizedBox(height: 100), // Bottom padding
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
          _buildBottomNav(),
        ],
      ),
    );
  }

  Widget _buildGridBackground() {
    return Positioned.fill(
      child: CustomPaint(
        painter: GridPainter(),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.all(25),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text("TERMINAL", style: TextStyle(color: TerminalColors.textSecondary, letterSpacing: 2, fontSize: 10, fontWeight: FontWeight.w900)),
              const Text("DASHBOARD", style: TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.w800, letterSpacing: -1)),
            ],
          ),
          Container(
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(color: Colors.black, borderRadius: BorderRadius.circular(12), border: Border.all(color: Colors.white10)),
            child: Row(
              children: [
                _modeToggle("LIVE", !_isDemo),
                _modeToggle("DEMO", _isDemo),
              ],
            ),
          )
        ],
      ),
    );
  }

  Widget _modeToggle(String label, bool active) {
    return GestureDetector(
      onTap: () {
        setState(() => _isDemo = label == "DEMO");
        _api.updateSettings({"demo_mode": _isDemo});
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: active ? TerminalColors.surface : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(label, style: TextStyle(color: active ? Colors.white : TerminalColors.textSecondary, fontSize: 10, fontWeight: FontWeight.bold)),
      ),
    );
  }

  Widget _buildEquityCard() {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: TerminalColors.surface,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: Colors.white.withOpacity(0.05)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(color: Colors.black, borderRadius: BorderRadius.circular(12)),
                child: const Icon(Icons.show_chart, color: TerminalColors.accentYellow, size: 20),
              ),
              const SizedBox(width: 15),
              Text("TOTAL EQUITY BALANCE", style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 10, letterSpacing: 1.5, fontWeight: FontWeight.bold)),
            ],
          ),
          const SizedBox(height: 25),
          Text("\$$_balance", style: const TextStyle(color: Colors.white, fontSize: 38, fontWeight: FontWeight.w900, fontFamily: 'monospace')),
          const SizedBox(height: 15),
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(color: TerminalColors.accentGreen.withOpacity(0.1), borderRadius: BorderRadius.circular(8)),
                child: Row(
                  children: [
                    const Icon(Icons.trending_up, color: TerminalColors.accentGreen, size: 14),
                    const SizedBox(width: 4),
                    const Text("+0.00%", style: TextStyle(color: TerminalColors.accentGreen, fontSize: 12, fontWeight: FontWeight.bold)),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              Text("TODAY'S PERFORMANCE", style: TextStyle(color: TerminalColors.textSecondary, fontSize: 10, fontWeight: FontWeight.bold)),
            ],
          ),
          const SizedBox(height: 30),
          Divider(color: Colors.white.withOpacity(0.05)),
          const SizedBox(height: 10),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text("WIN RATE", style: TextStyle(color: TerminalColors.textSecondary, fontSize: 12, fontWeight: FontWeight.bold)),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(color: TerminalColors.accentCyan.withOpacity(0.05), border: Border.all(color: TerminalColors.accentCyan.withOpacity(0.2)), borderRadius: BorderRadius.circular(4)),
                child: const Text("50.0%", style: TextStyle(color: TerminalColors.accentCyan, fontWeight: FontWeight.bold, fontFamily: 'monospace')),
              )
            ],
          )
        ],
      ),
    );
  }

  Widget _buildRiskManagementCard() {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: TerminalColors.surface,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: Colors.white.withOpacity(0.05)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.shield_outlined, color: TerminalColors.accentYellow, size: 18),
              const SizedBox(width: 10),
              Text("RISK MANAGEMENT", style: TextStyle(color: Colors.white, fontSize: 12, letterSpacing: 1.5, fontWeight: FontWeight.bold)),
            ],
          ),
          const SizedBox(height: 25),
          Row(
            children: [
              _riskBox("EXPOSURE", "12.5%"),
              const SizedBox(width: 15),
              _riskBox("SIGNALS", "${_signals.length}"),
            ],
          ),
          const SizedBox(height: 30),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text("DAILY DRAWDOWN", style: TextStyle(color: TerminalColors.textSecondary, fontSize: 10, fontWeight: FontWeight.bold)),
              RichText(text: const TextSpan(children: [
                TextSpan(text: "1.2%", style: TextStyle(color: TerminalColors.accentRed, fontWeight: FontWeight.bold, fontSize: 10)),
                TextSpan(text: " / 5.0%", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 10)),
              ])),
            ],
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(value: 0.24, backgroundColor: Colors.white.withOpacity(0.05), color: TerminalColors.accentYellow, minHeight: 6),
          ),
          const SizedBox(height: 30),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(color: TerminalColors.accentGreen.withOpacity(0.03), border: Border.all(color: TerminalColors.accentGreen.withOpacity(0.1)), borderRadius: BorderRadius.circular(12)),
            child: const Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text("AVAILABLE CAPACITY", style: TextStyle(color: TerminalColors.accentGreen, fontSize: 10, fontWeight: FontWeight.bold)),
                Text("87.5%", style: TextStyle(color: TerminalColors.accentGreen, fontSize: 12, fontWeight: FontWeight.bold, fontFamily: 'monospace')),
              ],
            ),
          )
        ],
      ),
    );
  }

  Widget _riskBox(String title, String value) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(color: Colors.black.withOpacity(0.3), borderRadius: BorderRadius.circular(16), border: Border.all(color: Colors.white.withOpacity(0.03))),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: TextStyle(color: TerminalColors.textSecondary, fontSize: 8, fontWeight: FontWeight.bold, letterSpacing: 1)),
            const SizedBox(height: 8),
            Text(value, style: const TextStyle(color: TerminalColors.accentCyan, fontSize: 18, fontWeight: FontWeight.w900, fontFamily: 'monospace')),
          ],
        ),
      ),
    );
  }

  Widget _buildBottomNav() {
    return Positioned(
      bottom: 0,
      left: 0,
      right: 0,
      child: Container(
        height: 90,
        decoration: BoxDecoration(
          color: TerminalColors.bg,
          border: Border(top: BorderSide(color: Colors.white.withOpacity(0.05))),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            _navItem(0, Icons.grid_view_rounded, "DASHBOARD"),
            _navItem(1, Icons.bolt, "SIGNALS"),
            _navItem(2, Icons.analytics_outlined, "MARKETS"),
            _navItem(3, Icons.menu_book_outlined, "STRATEGIES"),
            _navItem(4, Icons.person_outline, "PROFILE"),
          ],
        ),
      ),
    );
  }

  Widget _navItem(int index, IconData icon, String label) {
    bool active = _selectedIndex == index;
    return GestureDetector(
      onTap: () => setState(() => _selectedIndex = index),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, color: active ? TerminalColors.accentYellow : TerminalColors.textSecondary, size: 24),
          const SizedBox(height: 6),
          Text(label, style: TextStyle(color: active ? TerminalColors.accentYellow : TerminalColors.textSecondary, fontSize: 8, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }
}

class GridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = TerminalColors.gridLine
      ..strokeWidth = 0.5;

    const spacing = 30.0;
    for (var i = 0.0; i < size.width; i += spacing) {
      canvas.drawLine(Offset(i, 0), Offset(i, size.height), paint);
    }
    for (var i = 0.0; i < size.height; i += spacing) {
      canvas.drawLine(Offset(0, i), Offset(size.width, i), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
