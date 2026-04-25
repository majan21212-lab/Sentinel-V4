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
  bool _isDemo = true;
  bool _autoTrade = false;
  List<TradeSignal> _signals = [];
  List<String> _activeMarkets = ["XAUUSD"];

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
          if (data['is_bot_active'] != null) _autoTrade = data['is_bot_active'];
          if (data['active_markets'] != null) _activeMarkets = List<String>.from(data['active_markets']);
        });
      }
    });
    _fetchSignals();
    Timer.periodic(const Duration(seconds: 5), (timer) => _fetchSignals());
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
              children: [
                _buildHeader(),
                Expanded(
                  child: IndexedStack(
                    index: _selectedIndex,
                    children: [
                      _buildDashboardTab(),
                      _buildSignalsTab(),
                      _buildMarketsTab(),
                      _buildStrategiesTab(),
                      _buildProfileTab(),
                    ],
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
      child: CustomPaint(painter: GridPainter()),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 25, vertical: 20),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(_getTabTitle(), style: const TextStyle(color: TerminalColors.textSecondary, letterSpacing: 2, fontSize: 10, fontWeight: FontWeight.w900)),
              Text(_getTabSubtitle(), style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.w800, letterSpacing: -1)),
            ],
          ),
          _modeToggle(),
        ],
      ),
    );
  }

  String _getTabTitle() => ["TERMINAL", "INTELLIGENCE", "MARKETS", "LIBRARY", "IDENTITY"][_selectedIndex];
  String _getTabSubtitle() => ["DASHBOARD", "LIVE SIGNALS", "BOT DEPLOYMENT", "STRATEGIES", "ACCOUNT"][_selectedIndex];

  Widget _modeToggle() {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(color: Colors.black, borderRadius: BorderRadius.circular(12), border: Border.all(color: Colors.white10)),
      child: Row(
        children: [
          _modeBtn("LIVE", !_isDemo),
          _modeBtn("DEMO", _isDemo),
        ],
      ),
    );
  }

  Widget _modeBtn(String label, bool active) {
    return GestureDetector(
      onTap: () {
        setState(() => _isDemo = label == "DEMO");
        _api.updateSettings({"demo_mode": _isDemo});
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(color: active ? TerminalColors.surface : Colors.transparent, borderRadius: BorderRadius.circular(8)),
        child: Text(label, style: TextStyle(color: active ? Colors.white : TerminalColors.textSecondary, fontSize: 9, fontWeight: FontWeight.bold)),
      ),
    );
  }

  // --- TAB 0: DASHBOARD ---
  Widget _buildDashboardTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        children: [
          _buildEquityCard(),
          const SizedBox(height: 20),
          _buildRiskManagementCard(),
          const SizedBox(height: 20),
          _buildQuickActionCard(),
        ],
      ),
    );
  }

  Widget _buildEquityCard() {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(color: TerminalColors.surface, borderRadius: BorderRadius.circular(24), border: Border.all(color: Colors.white.withOpacity(0.05))),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.account_balance_wallet_outlined, color: TerminalColors.accentYellow, size: 18),
              const SizedBox(width: 10),
              Text("TOTAL EQUITY BALANCE", style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 10, letterSpacing: 1, fontWeight: FontWeight.bold)),
            ],
          ),
          const SizedBox(height: 20),
          Text("\$$_balance", style: const TextStyle(color: Colors.white, fontSize: 36, fontWeight: FontWeight.w900, fontFamily: 'monospace')),
          const SizedBox(height: 10),
          Row(
            children: [
              const Icon(Icons.trending_up, color: TerminalColors.accentGreen, size: 14),
              const SizedBox(width: 4),
              const Text("+2.4% TODAY", style: TextStyle(color: TerminalColors.accentGreen, fontSize: 10, fontWeight: FontWeight.bold)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildRiskManagementCard() {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(color: TerminalColors.surface, borderRadius: BorderRadius.circular(24), border: Border.all(color: Colors.white.withOpacity(0.05))),
      child: Column(
        children: [
          Row(
            children: [
              const Icon(Icons.shield_outlined, color: TerminalColors.accentCyan, size: 18),
              const SizedBox(width: 10),
              const Text("RISK PARAMETERS", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
            ],
          ),
          const SizedBox(height: 20),
          _riskRow("EXPOSURE", "12.5%", TerminalColors.accentCyan),
          const SizedBox(height: 15),
          _riskRow("DRAWDOWN", "1.2%", TerminalColors.accentRed),
          const SizedBox(height: 15),
          _riskRow("WIN RATE", "75%", TerminalColors.accentGreen),
        ],
      ),
    );
  }

  Widget _riskRow(String label, String value, Color color) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(color: TerminalColors.textSecondary, fontSize: 10, fontWeight: FontWeight.bold)),
        Text(value, style: TextStyle(color: color, fontWeight: FontWeight.w900, fontFamily: 'monospace')),
      ],
    );
  }

  Widget _buildQuickActionCard() {
    return GestureDetector(
      onTap: () {
        setState(() => _autoTrade = !_autoTrade);
        _api.updateSettings({"is_bot_active": _autoTrade});
      },
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: _autoTrade ? TerminalColors.accentGreen.withOpacity(0.1) : TerminalColors.surface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: _autoTrade ? TerminalColors.accentGreen : Colors.white10),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.bolt, color: _autoTrade ? TerminalColors.accentGreen : Colors.white),
            const SizedBox(width: 10),
            Text(_autoTrade ? "ENGINE: ACTIVE" : "INVOKE TRADING CORE", style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
          ],
        ),
      ),
    );
  }

  // --- TAB 1: SIGNALS ---
  Widget _buildSignalsTab() {
    if (_signals.isEmpty) {
      return const Center(child: Text("WAITING FOR INSTITUTIONAL FLOW...", style: TextStyle(color: TerminalColors.textSecondary, fontSize: 10, letterSpacing: 2)));
    }
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      itemCount: _signals.length,
      itemBuilder: (context, index) => _signalCard(_signals[index]),
    );
  }

  Widget _signalCard(TradeSignal sig) {
    final isLong = sig.direction.toUpperCase() == "LONG" || sig.direction.toUpperCase() == "BUY";
    return Container(
      margin: const EdgeInsets.only(bottom: 15),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(color: TerminalColors.surface, borderRadius: BorderRadius.circular(20), border: Border.all(color: Colors.white.withOpacity(0.05))),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(sig.symbol, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(color: (isLong ? TerminalColors.accentGreen : TerminalColors.accentRed).withOpacity(0.1), borderRadius: BorderRadius.circular(4)),
                child: Text(sig.direction, style: TextStyle(color: isLong ? TerminalColors.accentGreen : TerminalColors.accentRed, fontWeight: FontWeight.bold, fontSize: 10)),
              )
            ],
          ),
          const SizedBox(height: 15),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _dataPoint("ENTRY", sig.entry.toStringAsFixed(2)),
              _dataPoint("TP", sig.tp1.toStringAsFixed(2)),
              _dataPoint("SL", sig.sl.toStringAsFixed(2)),
            ],
          ),
          const SizedBox(height: 15),
          Text(sig.pattern, style: const TextStyle(color: TerminalColors.textSecondary, fontSize: 10, fontStyle: FontStyle.italic)),
        ],
      ),
    );
  }

  Widget _dataPoint(String label, String val) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: TerminalColors.textSecondary, fontSize: 8, fontWeight: FontWeight.bold)),
        Text(val, style: const TextStyle(fontWeight: FontWeight.w900, fontFamily: 'monospace')),
      ],
    );
  }

  // --- TAB 2: MARKETS ---
  Widget _buildMarketsTab() {
    final markets = ["XAUUSD", "BTCUSDT", "EURUSD", "GBPUSD", "US30", "NAS100"];
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      itemCount: markets.length,
      itemBuilder: (context, index) {
        final symbol = markets[index];
        final isActive = _activeMarkets.contains(symbol);
        return Container(
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.all(15),
          decoration: BoxDecoration(color: TerminalColors.surface, borderRadius: BorderRadius.circular(16)),
          child: Row(
            children: [
              const Icon(Icons.language, color: TerminalColors.accentCyan, size: 20),
              const SizedBox(width: 15),
              Text(symbol, style: const TextStyle(fontWeight: FontWeight.bold)),
              const Spacer(),
              Switch(
                value: isActive,
                activeColor: TerminalColors.accentCyan,
                onChanged: (val) {
                  setState(() {
                    if (val) _activeMarkets.add(symbol);
                    else _activeMarkets.remove(symbol);
                  });
                  _api.updateSettings({"active_markets": _activeMarkets});
                },
              )
            ],
          ),
        );
      },
    );
  }

  // --- TAB 3: STRATEGIES ---
  Widget _buildStrategiesTab() {
    final strats = ["AlphaGate V1", "GodMode Core", "Institutional Pulse", "SMC Alpha"];
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      itemCount: strats.length,
      itemBuilder: (context, index) => ListTile(
        title: Text(strats[index], style: const TextStyle(fontWeight: FontWeight.bold)),
        trailing: const Icon(Icons.check_circle, color: TerminalColors.accentGreen),
      ),
    );
  }

  // --- TAB 4: PROFILE ---
  Widget _buildProfileTab() {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        _profileAction("CONNECT BROKER", Icons.link, () => _showBrokerDialog()),
        _profileAction("DEMO DEPOSIT (\$1,000)", Icons.add_circle_outline, () {
          _api.updateSettings({"demo_deposit": 1000});
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Balance Updated")));
        }),
        _profileAction("RISK SETTINGS", Icons.settings_input_component, () {}),
        _profileAction("NOTIFICATION PREFERENCES", Icons.notifications_none, () {}),
      ],
    );
  }

  Widget _profileAction(String label, IconData icon, VoidCallback onTap) {
    return Container(
      margin: const EdgeInsets.only(bottom: 15),
      child: ListTile(
        onTap: onTap,
        tileColor: TerminalColors.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        leading: Icon(icon, color: TerminalColors.accentYellow),
        title: Text(label, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
        trailing: const Icon(Icons.chevron_right, color: TerminalColors.textSecondary),
      ),
    );
  }

  void _showBrokerDialog() {
    String selectedBroker = "Binance";
    final keyController = TextEditingController();
    final secretController = TextEditingController();

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: TerminalColors.surface,
        title: const Text("CONNECT BROKER"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            DropdownButtonFormField<String>(
              value: selectedBroker,
              items: ["Binance", "OKX", "Alpaca", "Exness"].map((b) => DropdownMenuItem(value: b, child: Text(b))).toList(),
              onChanged: (v) => selectedBroker = v!,
              decoration: const InputDecoration(labelText: "Select Broker"),
            ),
            TextField(controller: keyController, decoration: const InputDecoration(labelText: "API Key")),
            TextField(controller: secretController, decoration: const InputDecoration(labelText: "API Secret"), obscureText: true),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text("CANCEL")),
          ElevatedButton(onPressed: () {
            _api.updateSettings({
              "credentials": {selectedBroker: {"key": keyController.text, "secret": secretController.text}},
              "active_broker": selectedBroker,
              "demo_mode": false
            });
            Navigator.pop(context);
          }, child: const Text("CONNECT")),
        ],
      ),
    );
  }

  Widget _buildBottomNav() {
    return Positioned(
      bottom: 0, left: 0, right: 0,
      child: Container(
        height: 90,
        decoration: BoxDecoration(color: TerminalColors.bg, border: Border(top: BorderSide(color: Colors.white.withOpacity(0.05)))),
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
    final paint = Paint()..color = TerminalColors.gridLine..strokeWidth = 0.5;
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
