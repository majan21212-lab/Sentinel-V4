import 'package:flutter/material.dart';
import 'package:glassmorphism/glassmorphism.dart';
import 'dart:async';
import 'services/api_service.dart';
import 'models/trade_models.dart';

void main() {
  runApp(const GeneralAutomationApp());
}

class ThemeColors {
  static const background = Color(0xFF000000); // Deepest Black
  static const surface = Color(0xFF111111); // Elevated Surface
  static const primaryGold = Color(0xFFD4AF37);
  static const accentPurple = Color(0xFF6200EE);
  static const successGreen = Color(0xFF00C853);
  static const errorRed = Color(0xFFFF1744);
  static const textGrey = Color(0xFF888888);
}

class GeneralAutomationApp extends StatelessWidget {
  const GeneralAutomationApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark(useMaterial3: true).copyWith(
        scaffoldBackgroundColor: ThemeColors.background,
        colorScheme: ColorScheme.fromSeed(
          seedColor: ThemeColors.accentPurple,
          brightness: Brightness.dark,
        ),
      ),
      home: const DashboardView(),
    );
  }
}

class DashboardView extends StatefulWidget {
  const DashboardView({super.key});

  @override
  State<DashboardView> createState() => _DashboardViewState();
}

class _DashboardViewState extends State<DashboardView> with SingleTickerProviderStateMixin {
  final ApiService _api = ApiService();
  late TabController _tabController;
  
  String _balance = "3,968.82";
  String _equity = "3,940.08";
  bool _autoTrade = false;
  List<TradeSignal> _signals = [];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _startListening();
  }

  void _startListening() {
    _api.marketStream.listen((data) {
      if (mounted) {
        setState(() {
          if (data['auto_trade'] != null) _autoTrade = data['auto_trade'];
          if (data['balance'] != null) _balance = data['balance'].toStringAsFixed(2);
          if (data['equity'] != null) _equity = data['equity'].toStringAsFixed(2);
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
      backgroundColor: ThemeColors.background,
      body: SafeArea(
        child: Column(
          children: [
            _buildEliroxHeader(),
            _buildChecklist(),
            _buildTabSection(),
            Expanded(
              child: TabBarView(
                controller: _tabController,
                children: [
                  _buildSignalList(_signals.where((s) => s.status == "OPEN").toList()),
                  _buildSignalList(_signals.where((s) => s.status == "PENDING").toList()),
                  _buildSignalList(_signals.where((s) => s.status == "CLOSED").toList()),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEliroxHeader() {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: GlassmorphicContainer(
        width: double.infinity,
        height: 180,
        borderRadius: 24,
        blur: 20,
        alignment: Alignment.center,
        border: 1,
        linearGradient: LinearGradient(colors: [Colors.white.withOpacity(0.05), Colors.white.withOpacity(0.02)]),
        borderGradient: LinearGradient(colors: [Colors.white.withOpacity(0.1), Colors.transparent]),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.gamepad, color: ThemeColors.textGrey, size: 16),
                  const SizedBox(width: 8),
                  const Text("Demo account", style: TextStyle(color: ThemeColors.textGrey, fontSize: 14)),
                  const Spacer(),
                  const Icon(Icons.keyboard_arrow_right, color: ThemeColors.textGrey),
                ],
              ),
              const SizedBox(height: 12),
              Text("\$$_balance", style: const TextStyle(fontSize: 36, fontWeight: FontWeight.bold, color: Colors.white)),
              const SizedBox(height: 4),
              Text("Free margin: \$$_equity", style: const TextStyle(color: ThemeColors.textGrey, fontSize: 14)),
              const Spacer(),
              ElevatedButton.icon(
                onPressed: () {},
                icon: const Icon(Icons.file_upload_outlined, size: 18),
                label: const Text("Deposit"),
                style: ElevatedButton.styleFrom(
                  backgroundColor: ThemeColors.surface,
                  foregroundColor: Colors.white,
                  minimumSize: const Size(double.infinity, 45),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildChecklist() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(color: ThemeColors.surface, borderRadius: BorderRadius.circular(24)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text("Get started checklist", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
              const Icon(Icons.keyboard_arrow_up),
            ],
          ),
          const SizedBox(height: 15),
          LinearProgressIndicator(value: 0.5, backgroundColor: Colors.white10, color: ThemeColors.accentPurple, borderRadius: BorderRadius.circular(10), minHeight: 6),
          const SizedBox(height: 20),
          _checklistTile("Create Elirox account", true),
          _checklistTile("Start your first bot", true),
          _checklistTile("Connect a trading account", false),
          _checklistTile("Choose your plan", false),
        ],
      ),
    );
  }

  Widget _checklistTile(String title, bool done) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(2),
            decoration: BoxDecoration(color: done ? ThemeColors.accentPurple : Colors.transparent, border: Border.all(color: Colors.white24), shape: BoxShape.circle),
            child: Icon(Icons.check, size: 14, color: done ? Colors.white : Colors.transparent),
          ),
          const SizedBox(width: 12),
          Text(title, style: TextStyle(color: done ? Colors.white : ThemeColors.textGrey)),
        ],
      ),
    );
  }

  Widget _buildTabSection() {
    return TabBar(
      controller: _tabController,
      dividerColor: Colors.transparent,
      indicatorColor: ThemeColors.accentPurple,
      labelColor: Colors.white,
      unselectedLabelColor: ThemeColors.textGrey,
      tabs: [
        Tab(child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [const Text("Open "), Container(padding: const EdgeInsets.all(4), decoration: BoxDecoration(color: Colors.white10, borderRadius: BorderRadius.circular(4)), child: const Text("3", style: TextStyle(fontSize: 10)))])),
        Tab(child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [const Text("Pending "), Container(padding: const EdgeInsets.all(4), decoration: BoxDecoration(color: Colors.white10, borderRadius: BorderRadius.circular(4)), child: const Text("12", style: TextStyle(fontSize: 10)))])),
        const Tab(text: "Closed"),
      ],
    );
  }

  Widget _buildSignalList(List<TradeSignal> signals) {
    return ListView.builder(
      padding: const EdgeInsets.all(20),
      itemCount: 5, // Simulated for UI
      itemBuilder: (context, index) => _buildTradeCard(),
    );
  }

  Widget _buildTradeCard() {
    return Container(
      margin: const EdgeInsets.only(bottom: 15),
      child: Row(
        children: [
          const CircleAvatar(radius: 18, backgroundColor: Colors.white10, child: Text("🇺🇸", style: TextStyle(fontSize: 18))),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text("XAUUSDm", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              Row(
                children: [
                  const Text("Sell ", style: TextStyle(color: ThemeColors.errorRed, fontSize: 12)),
                  const Text("0.03 lots at ~4 737.177", style: TextStyle(color: ThemeColors.textGrey, fontSize: 12)),
                ],
              ),
              Container(
                margin: const EdgeInsets.only(top: 4),
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(color: Colors.white10, borderRadius: BorderRadius.circular(4)),
                child: const Text("My Demo bot #3", style: TextStyle(color: ThemeColors.textGrey, fontSize: 10)),
              ),
            ],
          ),
          const Spacer(),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              const Text("-58.24\$", style: TextStyle(color: ThemeColors.errorRed, fontWeight: FontWeight.bold)),
              const Text("-0.41%", style: TextStyle(color: ThemeColors.errorRed, fontSize: 12)),
            ],
          ),
        ],
      ),
    );
  }
}
