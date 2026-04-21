import 'package:flutter/material.dart';
import 'package:glassmorphism/glassmorphism.dart';
import 'dart:async';
import 'services/api_service.dart';
import 'models/trade_models.dart';

void main() {
  runApp(const GeneralAutomationApp());
}

class ThemeColors {
  static const background = Color(0xFF050814);
  static const midnightBlue = Color(0xFF0D1226);
  static const primaryPurple = Color(0xFF5E2EEB);
  static const accentBlue = Color(0xFF00E6FF);
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
          seedColor: ThemeColors.primaryPurple,
          brightness: Brightness.dark,
        ),
      ),
      home: const DashboardView(),
    );
  }
}

class AmbientGlow extends StatefulWidget {
  const AmbientGlow({super.key});

  @override
  State<AmbientGlow> createState() => _AmbientGlowState();
}

class _AmbientGlowState extends State<AmbientGlow> with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(seconds: 15),
      vsync: this,
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return Stack(
          children: [
            Container(color: ThemeColors.background),
            // Purple Glow
            Positioned(
              top: -100 + (150 * _controller.value),
              left: -50 + (100 * _controller.value),
              child: Container(
                width: 400,
                height: 400,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: ThemeColors.primaryPurple.withOpacity(0.25),
                ),
              ).withBlur(100),
            ),
            // Blue Glow
            Positioned(
              bottom: -50 + (100 * (1 - _controller.value)),
              right: -50 + (150 * _controller.value),
              child: Container(
                width: 300,
                height: 300,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: ThemeColors.accentBlue.withOpacity(0.12),
                ),
              ).withBlur(80),
            ),
          ],
        );
      },
    );
  }
}

extension BlurExtension on Widget {
  Widget withBlur(double radius) => ImageFiltered(
        imageFilter: ColorFilter.mode(Colors.transparent, BlendMode.multiply), // Placeholder logic if sigma is needed
        // In real app we'd use BackdropFilter, but for background shapes we can just use decoration blur
        child: this,
      ); // Not the most efficient, but works for the concept. 
      // Better: Container decoration with BoxShadow(blurRadius).
}

class DashboardView extends StatefulWidget {
  const DashboardView({super.key});

  @override
  State<DashboardView> createState() => _DashboardViewState();
}

class _DashboardViewState extends State<DashboardView> {
  final ApiService _api = ApiService();
  String _price = "0.00";
  String _activeProfile = "CONSERVATIVE";
  String _strategyMode = "PATTERN";
  bool _demoMode = true;
  bool _autoTrade = false;
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
          if (data['auto_trade'] != null) _autoTrade = data['auto_trade'];
          if (data['active_profile'] != null) _activeProfile = data['active_profile'];
          if (data['demo_mode'] != null) _demoMode = data['demo_mode'];
          if (data['strategy_mode'] != null) _strategyMode = data['strategy_mode'];
          if (data['prices'] != null && data['prices']['BTCUSDm'] != null) {
            _price = data['prices']['BTCUSDm'].toStringAsFixed(2);
          }
        });
      }
    });
    _fetchSignals();
  }

  Future<void> _fetchSignals() async {
    final signals = await _api.fetchSignals();
    if (mounted) setState(() => _signals = signals);
  }

  void _toggleAutoTrade() {
    setState(() => _autoTrade = !_autoTrade);
    _api.updateSettings({"auto_trade": _autoTrade});
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          const AmbientGlow(),
          SafeArea(
            child: Column(
              children: [
                _buildPremiumHeader(),
                Expanded(
                  child: ListView(
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    children: [
                      const SizedBox(height: 10),
                      _buildStrategySwitcher(),
                      const SizedBox(height: 20),
                      _buildChartSection(),
                      const SizedBox(height: 30),
                      _buildSignalFeed(),
                      const SizedBox(height: 100),
                    ],
                  ),
                ),
              ],
            ),
          ),
          _buildBottomActionArea(),
        ],
      ),
    );
  }

  Widget _buildPremiumHeader() {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text("G.A.B CORE", style: TextStyle(fontSize: 10, fontWeight: FontWeight.w900, letterSpacing: 3, color: ThemeColors.primaryPurple)),
              Text("\$$_price", style: const TextStyle(fontSize: 42, fontWeight: FontWeight.bold, color: Colors.white)),
            ],
          ),
          GestureDetector(
            onTap: _toggleAutoTrade,
            child: Column(
              children: [
                Container(
                  width: 55,
                  height: 55,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: _autoTrade ? Colors.green.withOpacity(0.2) : Colors.white.withOpacity(0.05),
                    border: Border.all(color: _autoTrade ? Colors.green : Colors.white.withOpacity(0.1)),
                  ),
                  child: Icon(
                    _autoTrade ? Icons.bolt : Icons.bolt_outlined,
                    color: _autoTrade ? Colors.green : Colors.grey,
                    size: 28,
                  ),
                ),
                const SizedBox(height: 6),
                Text(_autoTrade ? "AUTO: ON" : "AUTO: OFF", style: TextStyle(fontSize: 8, fontWeight: FontWeight.w900, color: _autoTrade ? Colors.green : Colors.grey)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStrategySwitcher() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.only(left: 4, bottom: 8),
          child: Text("ACTIVE STRATEGY", style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Colors.grey)),
        ),
        SegmentedButton<String>(
          segments: const [
            ButtonSegment(value: 'PATTERN', label: Text('PATTERN'), icon: Icon(Icons.auto_graph, size: 16)),
            ButtonSegment(value: 'GRID', label: Text('GRID'), icon: Icon(Icons.grid_4x4, size: 16)),
            ButtonSegment(value: 'DCA', label: Text('DCA'), icon: Icon(Icons.layers, size: 16)),
          ],
          selected: {_strategyMode},
          onSelectionChanged: (Set<String> newSelection) {
            final mode = newSelection.first;
            setState(() => _strategyMode = mode);
            _api.updateSettings({"strategy_mode": mode});
          },
          style: ButtonStyle(
            backgroundColor: WidgetStateProperty.resolveWith<Color?>((states) {
              if (states.contains(WidgetState.selected)) return ThemeColors.primaryPurple;
              return Colors.white.withOpacity(0.05);
            }),
          ),
        ),
      ],
    );
  }

  Widget _buildChartSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.only(left: 4, bottom: 12),
          child: Text("MARKET REASONER", style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Colors.grey)),
        ),
        GlassmorphicContainer(
          width: double.infinity,
          height: 200,
          borderRadius: 32,
          blur: 30,
          alignment: Alignment.center,
          border: 1,
          linearGradient: LinearGradient(colors: [Colors.white.withOpacity(0.05), Colors.white.withOpacity(0.02)]),
          borderGradient: LinearGradient(colors: [Colors.white.withOpacity(0.2), Colors.white.withOpacity(0.05)]),
          child: const Center(child: Icon(Icons.waves, color: Colors.white24, size: 40)),
        ),
      ],
    );
  }

  Widget _buildSignalFeed() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.only(left: 4, bottom: 16),
          child: Text("DETECTION FEED", style: TextStyle(fontSize: 10, fontWeight: FontWeight.w900, color: Colors.grey, letterSpacing: 1.5)),
        ),
        if (_signals.isEmpty)
          const Center(child: Padding(padding: EdgeInsets.all(40), child: CircularProgressIndicator()))
        else
          ..._signals.map((sig) => _buildSignalCard(sig)).toList(),
      ],
    );
  }

  Widget _buildSignalCard(TradeSignal sig) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      child: GlassmorphicContainer(
        width: double.infinity,
        height: 80,
        borderRadius: 24,
        blur: 20,
        alignment: Alignment.center,
        border: 1,
        linearGradient: LinearGradient(colors: [Colors.white.withOpacity(0.08), Colors.white.withOpacity(0.03)]),
        borderGradient: LinearGradient(colors: [Colors.white.withOpacity(0.1), Colors.transparent]),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Row(
            children: [
              Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(sig.symbol, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                  Text(sig.pattern, style: const TextStyle(fontSize: 10, color: Colors.grey)),
                ],
              ),
              const Spacer(),
              Text(sig.direction, style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: sig.direction == "LONG" ? Colors.greenAccent : Colors.redAccent)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildBottomActionArea() {
    return Positioned(
      bottom: 40,
      left: 40,
      right: 40,
      child: Container(
        height: 60,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(30),
          gradient: const LinearGradient(colors: [ThemeColors.primaryPurple, ThemeColors.midnightBlue]),
          boxShadow: [BoxShadow(color: ThemeColors.primaryPurple.withOpacity(0.4), blurRadius: 15, offset: const Offset(0, 8))],
        ),
        child: const Center(
          child: Text("INVOKE CORE ENGINE", style: TextStyle(fontWeight: FontWeight.w900, color: Colors.white, fontSize: 14)),
        ),
      ),
    );
  }
}
