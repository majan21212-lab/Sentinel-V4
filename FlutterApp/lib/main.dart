import 'package:flutter/material.dart';
import 'dart:async';
import 'package:glassmorphism/glassmorphism.dart';
import 'services/api_service.dart';
import 'models/trade_models.dart';

void main() {
  runApp(const JewelEliteApp());
}

class ThemeColors {
  static const bg = Color(0xFF05050A);
  static const surface = Color(0xFF10101A);
  static const primary = Color(0xFF7000FF); // Purple Accent
  static const secondary = Color(0xFF00E5FF); // Cyan
  static const success = Color(0xFF00C853);
  static const danger = Color(0xFFFF1744);
  static const warning = Color(0xFFFBC02D);
  static const textMain = Colors.white;
  static const textDim = Color(0xFF808090);

  static const primaryGradient = LinearGradient(
    colors: [primary, Color(0xFF9D50BB)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
}

class JewelEliteApp extends StatelessWidget {
  const JewelEliteApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: ThemeColors.bg,
        colorScheme: const ColorScheme.dark(primary: ThemeColors.primary),
      ),
      home: const MainDashboardView(),
    );
  }
}

class MainDashboardView extends StatefulWidget {
  const MainDashboardView({super.key});

  @override
  State<MainDashboardView> createState() => _MainDashboardViewState();
}

class _MainDashboardViewState extends State<MainDashboardView> {
  final ApiService _api = ApiService();
  int _selectedIndex = 0;
  
  String _balance = "0.00";
  bool _autoTrade = false;
  List<TradeSignal> _signals = [];
  double _winRate = 85.4;
  double _drawdown = 0.0;

  @override
  void initState() {
    super.initState();
    _startSync();
  }

  void _startSync() {
    _api.marketStream.listen((data) {
      if (mounted) {
        setState(() {
          // Sync Balance
          if (data['demo_balance'] != null) _balance = data['demo_balance'].toStringAsFixed(2);
          else if (data['balance'] != null) _balance = data['balance'].toStringAsFixed(2);
          
          // Sync Bot Status
          if (data['is_bot_active'] != null) _autoTrade = data['is_bot_active'];
          
          // Sync Risk Settings
          if (data['is_cent_account'] != null) _isCentAccount = data['is_cent_account'];
          if (data['active_profile'] != null) _activeProfile = data['active_profile'];
          
          // Sync Metrics
          if (data['win_rate'] != null) _winRate = data['win_rate'];
          if (data['drawdown'] != null) _drawdown = data['drawdown'];
          
          // Sync Active Trades
          if (data['active_trades'] != null) {
            _activeTrades = List<Map<String, dynamic>>.from(data['active_trades']);
          }
        });
      }
    });
    _fetchSignals();
    Timer.periodic(const Duration(seconds: 5), (timer) => _fetchSignals());
  }

  Future<void> _fetchSignals() async {
    try {
      final signals = await _api.fetchSignals();
      if (mounted) setState(() => _signals = signals);
    } catch (e) {
      // Handle silently
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      bottomNavigationBar: _buildBottomNav(),
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            Expanded(
              child: IndexedStack(
                index: _selectedIndex,
                children: [
                  _buildDashboardTab(),
                  _buildSignalsTab(),
                  _buildPortfolioTab(),
                  _buildSettingsTab(),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 15),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text("JEWEL ELITE", 
                style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w900, letterSpacing: 1.5)),
              Text("BOT MANAGER", 
                style: TextStyle(color: ThemeColors.primary, fontSize: 9, fontWeight: FontWeight.bold, letterSpacing: 2)),
            ],
          ),
          _buildEngineSwitch(),
        ],
      ),
    );
  }

  Widget _buildEngineSwitch() {
    return GestureDetector(
      onTap: () {
        setState(() => _autoTrade = !_autoTrade);
        _api.updateSettings({"is_bot_active": _autoTrade});
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.05),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: _autoTrade ? ThemeColors.success.withOpacity(0.5) : Colors.white10),
        ),
        child: Row(
          children: [
            Container(
              width: 8, height: 8,
              decoration: BoxDecoration(
                color: _autoTrade ? ThemeColors.success : ThemeColors.danger,
                shape: BoxShape.circle,
                boxShadow: [
                  if (_autoTrade) BoxShadow(color: ThemeColors.success.withOpacity(0.5), blurRadius: 4)
                ],
              ),
            ),
            const SizedBox(width: 8),
            Text(_autoTrade ? "ENGINE ACTIVE" : "ENGINE STOPPED", 
              style: const TextStyle(fontSize: 9, fontWeight: FontWeight.bold)),
          ],
        ),
      ),
    );
  }

  Widget _buildDashboardTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisSpacing: 15,
            mainAxisSpacing: 15,
            childAspectRatio: 1.4,
            children: [
              _buildKPICard("TOTAL BALANCE", "\$$_balance", "+0.00% Today", ThemeColors.success),
              _buildKPICard("AI WIN RATE", "$_winRate%", "30D Avg", ThemeColors.success),
              _buildKPICard("DAILY DRAWDOWN", "$_drawdown%", "Max: 5.0%", ThemeColors.danger),
              _buildKPICard("ACTIVE STRATEGY", "Pattern", "Exp: 12%", ThemeColors.primary),
            ],
          ),
          const SizedBox(height: 30),
          const Text("AI DETECTION LOG", style: TextStyle(color: ThemeColors.textDim, fontSize: 10, fontWeight: FontWeight.bold, letterSpacing: 1)),
          const SizedBox(height: 15),
          if (_signals.isEmpty) 
            _buildEmptyState()
          else 
            ..._signals.take(5).map((s) => _buildSignalRow(s)),
        ],
      ),
    );
  }

  Widget _buildKPICard(String title, String value, String sub, Color color) {
    return GlassmorphicContainer(
      width: double.infinity,
      height: double.infinity,
      borderRadius: 16,
      blur: 20,
      alignment: Alignment.bottomLeft,
      border: 2,
      linearGradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Colors.white.withOpacity(0.1),
            Colors.white.withOpacity(0.05),
          ],
          stops: const [0.1, 1]),
      borderGradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            color.withOpacity(0.5),
            color.withOpacity(0.2),
          ]),
      child: Padding(
        padding: const EdgeInsets.all(15),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(color: ThemeColors.textDim, fontSize: 9, fontWeight: FontWeight.bold)),
            const Spacer(),
            Text(value, style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w900)),
            const SizedBox(height: 4),
            Text(sub, style: TextStyle(color: color, fontSize: 9, fontWeight: FontWeight.bold)),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return GlassmorphicContainer(
      width: double.infinity,
      height: 160,
      borderRadius: 16,
      blur: 20,
      alignment: Alignment.center,
      border: 2,
      linearGradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Colors.white.withOpacity(0.02),
            Colors.white.withOpacity(0.05),
          ]),
      borderGradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            ThemeColors.primary.withOpacity(0.2),
            Colors.transparent,
          ]),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          TweenAnimationBuilder<double>(
            tween: Tween(begin: 0.0, end: 1.0),
            duration: const Duration(seconds: 2),
            curve: Curves.easeInOut,
            builder: (context, value, child) {
              return Container(
                padding: const EdgeInsets.all(2),
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: ThemeColors.primary.withOpacity(0.2 * value),
                      blurRadius: 15 * value,
                      spreadRadius: 5 * value,
                    )
                  ],
                ),
                child: const CircularProgressIndicator(
                  strokeWidth: 2, 
                  valueColor: AlwaysStoppedAnimation<Color>(ThemeColors.primary),
                ),
              );
            },
            onEnd: () {}, // Handled by repetitive animation if needed
          ),
          const SizedBox(height: 20),
          const Text("Awaiting institutional opportunities...", 
            style: TextStyle(color: ThemeColors.textDim, fontSize: 11, letterSpacing: 0.5)),
        ],
      ),
    );
  }

  Widget _buildSignalRow(TradeSignal sig) {
    final bool isLong = sig.direction.contains("LONG");
    final Color color = isLong ? ThemeColors.success : ThemeColors.danger;
    
    return GlassmorphicContainer(
      width: double.infinity,
      height: 70,
      borderRadius: 12,
      blur: 15,
      alignment: Alignment.center,
      border: 1,
      linearGradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Colors.white.withOpacity(0.05),
            Colors.white.withOpacity(0.02),
          ]),
      borderGradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            color.withOpacity(0.2),
            Colors.transparent,
          ]),
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 15),
        child: Row(
          children: [
            Container(
              width: 4, height: 30,
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(2),
                boxShadow: [BoxShadow(color: color.withOpacity(0.5), blurRadius: 4)],
              ),
            ),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(sig.symbol, style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 14, letterSpacing: 0.5)),
                Text(sig.pattern.toUpperCase(), style: const TextStyle(color: ThemeColors.textDim, fontSize: 8, fontWeight: FontWeight.bold, letterSpacing: 1)),
              ],
            ),
            const Spacer(),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                color: color.withOpacity(0.1),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: color.withOpacity(0.2)),
              ),
              child: Text(sig.direction, 
                style: TextStyle(color: color, fontSize: 9, fontWeight: FontWeight.w900)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSignalsTab() {
    return ListView.builder(
      padding: const EdgeInsets.all(20),
      itemCount: _signals.length,
      itemBuilder: (context, index) => _buildSignalRow(_signals[index]),
    );
  }

  List<Map<String, dynamic>> _activeTrades = [];

  Widget _buildPortfolioTab() {
    if (_activeTrades.isEmpty) {
      return const Center(child: Text("No Active Trades", style: TextStyle(color: ThemeColors.textDim)));
    }
    return ListView.builder(
      padding: const EdgeInsets.all(20),
      itemCount: _activeTrades.length,
      itemBuilder: (context, index) {
        final t = _activeTrades[index];
        return _buildTradeCard(t);
      },
    );
  }

  Widget _buildTradeCard(Map<String, dynamic> trade) {
    final bool isLong = trade['direction'].toString().contains("BUY") || trade['direction'].toString().contains("LONG");
    final Color color = isLong ? ThemeColors.success : ThemeColors.danger;

    return GlassmorphicContainer(
      width: double.infinity,
      height: 80,
      borderRadius: 12,
      blur: 15,
      alignment: Alignment.center,
      border: 1,
      linearGradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Colors.white.withOpacity(0.05),
            Colors.white.withOpacity(0.02),
          ]),
      borderGradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            color.withOpacity(0.2),
            Colors.transparent,
          ]),
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 15),
        child: Row(
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(trade['symbol'], style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 14, letterSpacing: 0.5)),
                Text("ENTRY: ${trade['entry']}", style: const TextStyle(color: ThemeColors.textDim, fontSize: 9, fontWeight: FontWeight.bold)),
              ],
            ),
            const Spacer(),
            Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(isLong ? "BUY" : "SELL", 
                  style: TextStyle(color: color, fontWeight: FontWeight.w900, fontSize: 12)),
                const SizedBox(height: 4),
                const Text("LIVE", style: TextStyle(color: ThemeColors.success, fontSize: 8, fontWeight: FontWeight.bold)),
              ],
            ),
          ],
        ),
      ),
    );
  }

  bool _isCentAccount = false;
  String _activeProfile = "CONSERVATIVE";

  Widget _buildSettingsTab() {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        _settingsTile("Account Funding", Icons.account_balance_wallet, () {
          _showInfo("Deposit/Withdrawal via Exness Dashboard is recommended.");
        }),
        _settingsTile("Broker Connectivity", Icons.link, () {
          _showInfo("Connected to Exness MT5 (Live)");
        }),
        _settingsTile("Risk Parameters", Icons.security, () {
          _showRiskSettings();
        }),
        _settingsTile("Master Kill Switch", Icons.power_settings_new, () {
          _api.updateSettings({"is_bot_active": false});
          setState(() => _autoTrade = false);
        }, color: ThemeColors.danger),
      ],
    );
  }

  void _showInfo(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg), backgroundColor: ThemeColors.primary));
  }

  void _showRiskSettings() {
    showModalBottomSheet(
      context: context,
      backgroundColor: ThemeColors.surface,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(25))),
      builder: (context) => StatefulBuilder(
        builder: (context, setModalState) => Container(
          padding: const EdgeInsets.all(25),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text("RISK PARAMETERS", style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 1)),
              const SizedBox(height: 20),
              SwitchListTile(
                title: const Text("Cent Account Mode", style: TextStyle(fontSize: 14)),
                subtitle: const Text("Optimizes for $20 - $500 balances", style: TextStyle(fontSize: 10, color: ThemeColors.textDim)),
                value: _isCentAccount,
                activeColor: ThemeColors.primary,
                onChanged: (val) {
                  _api.updateSettings({"is_cent_account": val});
                  setModalState(() => _isCentAccount = val);
                  setState(() => _isCentAccount = val);
                },
              ),
              const Divider(color: Colors.white10),
              ListTile(
                title: const Text("Risk Profile", style: TextStyle(fontSize: 14)),
                trailing: Text(_activeProfile, style: const TextStyle(color: ThemeColors.primary, fontWeight: FontWeight.bold)),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _settingsTile(String title, IconData icon, VoidCallback onTap, {Color color = Colors.white}) {
    return ListTile(
      onTap: onTap,
      leading: Icon(icon, color: color == Colors.white ? ThemeColors.primary : color),
      title: Text(title, style: TextStyle(color: color, fontSize: 14, fontWeight: FontWeight.bold)),
      trailing: const Icon(Icons.chevron_right, color: ThemeColors.textDim),
    );
  }

  Widget _buildBottomNav() {
    return BottomNavigationBar(
      currentIndex: _selectedIndex,
      onTap: (index) => setState(() => _selectedIndex = index),
      backgroundColor: ThemeColors.bg,
      type: BottomNavigationBarType.fixed,
      selectedItemColor: ThemeColors.primary,
      unselectedItemColor: ThemeColors.textDim,
      selectedFontSize: 9,
      unselectedFontSize: 9,
      items: [
        const BottomNavigationBarItem(icon: Icon(Icons.dashboard_rounded), label: "DASHBOARD"),
        const BottomNavigationBarItem(icon: Icon(Icons.bolt), label: "SIGNALS"),
        const BottomNavigationBarItem(icon: Icon(Icons.pie_chart_rounded), label: "PORTFOLIO"),
        const BottomNavigationBarItem(icon: Icon(Icons.settings_rounded), label: "SETTINGS"),
      ],
    );
  }
}
