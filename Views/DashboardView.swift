import SwiftUI

struct DashboardView: View {
    @StateObject var vm = MarketViewModel()
    @State private var selectedSignal: TradeSignal? = nil
    
    var body: some View {
        NavigationView {
            ZStack {
                // 1. Midnight Sentinel Background
                AmbientGlow()
                    .edgesIgnoringSafeArea(.all)
                
                ScrollView(showsIndicators: false) {
                    VStack(spacing: 30) {
                        
                        // 2. Premium Header & Auto-Trade Switch
                        HStack(alignment: .top) {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("SENTINEL V4")
                                    .font(.system(size: 12, weight: .black))
                                    .tracking(3)
                                    .foregroundColor(Theme.primaryPurple)
                                
                                Text("$\(vm.price)")
                                    .font(.system(size: 48, weight: .bold, design: .rounded))
                                    .foregroundColor(.white)
                            }
                            
                            Spacer()
                            
                            // Prominent Auto-Trade Toggle
                            VStack(spacing: 6) {
                                Button(action: { vm.toggleAutoTrade() }) {
                                    ZStack {
                                        Circle()
                                            .fill(vm.autoTrade ? Color.green.opacity(0.2) : Color.white.opacity(0.05))
                                            .frame(width: 50, height: 50)
                                            .overlay(
                                                Circle().stroke(vm.autoTrade ? Color.green : Color.white.opacity(0.1), lineWidth: 1)
                                            )
                                        
                                        Image(systemName: vm.autoTrade ? "bolt.fill" : "bolt.slash.fill")
                                            .foregroundColor(vm.autoTrade ? .green : .secondary)
                                            .font(.system(size: 20, weight: .bold))
                                    }
                                }
                                
                                Text(vm.autoTrade ? "AUTO: ON" : "AUTO: OFF")
                                    .font(.system(size: 8, weight: .black))
                                    .foregroundColor(vm.autoTrade ? .green : .secondary)
                            }
                        }
                        .padding(.horizontal)
                        .padding(.top, 25)
                        
                        // 3. Technical Chart (High Intensity Glass)
                        VStack(alignment: .leading, spacing: 12) {
                            Label("MARKET REASONER", systemImage: "waveform.path.ecg")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundColor(.secondary)
                                .padding(.horizontal)
                            
                            if !vm.candleHistory.isEmpty {
                                CandlestickChartView(candles: vm.candleHistory)
                                    .frame(height: 200)
                                    .glassCard(cornerRadius: 32, opacity: 0.2)
                                    .padding(.horizontal)
                            }
                        }
                        
                        // 4. Institutional Signals Feed
                        VStack(alignment: .leading, spacing: 18) {
                            HStack {
                                Text("DETECTION FEED")
                                    .font(.system(size: 10, weight: .black))
                                    .tracking(1.5)
                                    .foregroundColor(.secondary)
                                
                                Spacer()
                                
                                if vm.isScanning {
                                    HStack(spacing: 4) {
                                        Circle().fill(Color.green).frame(width: 4, height: 4)
                                        Text("LIVE SCANNING")
                                            .font(.system(size: 8, weight: .bold))
                                            .foregroundColor(.green)
                                    }
                                }
                            }
                            .padding(.horizontal)
                            
                            if vm.activeSignals.isEmpty {
                                VStack(spacing: 15) {
                                    ProgressView()
                                        .tint(Theme.primaryPurple)
                                    Text("WAITING FOR INSTITUTIONAL CONFLUENCE...")
                                        .font(.system(size: 10, weight: .medium))
                                        .foregroundColor(.secondary)
                                }
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 40)
                                .glassCard(cornerRadius: 24)
                                .padding(.horizontal)
                            } else {
                                ForEach(vm.activeSignals) { signal in
                                    SignalCard(signal: signal)
                                        .onTapGesture {
                                            selectedSignal = signal
                                        }
                                        .padding(.horizontal)
                                }
                            }
                        }
                        
                        // 5. Invoke Button (Floating Style)
                        Button(action: { 
                            vm.startScanner(symbol: "BTCUSDT") 
                            HapticManager.shared.triggerHighConfidence()
                        }) {
                            Text(vm.isScanning ? "SENTINEL ACTIVE" : "INVOKE CORE ENGINE")
                                .font(.system(size: 14, weight: .black))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 18)
                                .background(
                                    ZStack {
                                        if vm.isScanning {
                                            Theme.primaryPurple.opacity(0.8)
                                        } else {
                                            LinearGradient(colors: [Theme.primaryPurple, Theme.midnightBlue], startPoint: .leading, endPoint: .trailing)
                                        }
                                    }
                                )
                                .foregroundColor(.white)
                                .clipShape(Capsule())
                                .shadow(color: Theme.primaryPurple.opacity(0.4), radius: 15, x: 0, y: 8)
                        }
                        .padding(.horizontal, 40)
                        .padding(.bottom, 40)
                        .disabled(vm.isScanning)
                }
            }
            .navigationBarHidden(true)
            .navigationTitle("💎 Jewel Elite")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    NavigationLink(destination: NotificationSettingsView()) {
                        Image(systemName: "bell.badge.fill")
                            .foregroundColor(.white)
                    }
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    NavigationLink(destination: RiskSettingsView()) {
                        Image(systemName: "shield.lefthalf.filled")
                            .foregroundColor(.white)
                    }
                }
            }
        }
    }
}

struct SignalCard: View {
    let signal: TradeSignal
    
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                VStack(alignment: .leading) {
                    HStack {
                        Text(signal.symbol)
                            .font(.headline)
                        
                        if signal.isBackendValidated {
                            Text("VALIDATED")
                                .font(.system(size: 8, weight: .black))
                                .padding(.horizontal, 4)
                                .padding(.vertical, 2)
                                .background(Color.blue)
                                .cornerRadius(4)
                        }
                    }
                    
                    Text("\(signal.pattern)")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                VStack(alignment: .trailing) {
                    Text(signal.direction.rawValue)
                        .font(.system(size: 18, weight: .black))
                        .foregroundColor(signal.direction == .long ? .green : .red)
                    
                    Text("\(Int(signal.score))%")
                        .font(.system(size: 14, weight: .bold, design: .monospaced))
                        .foregroundColor(.white)
                }
            }
            
            if let confluence = signal.confluence {
                Divider().background(Color.white.opacity(0.1))
                Text(confluence)
                    .font(.system(size: 10, weight: .medium))
                    .foregroundColor(.secondary)
                    .italic()
            }
        }
        .padding()
        .glassCard(opacity: 0.1)
    }
}

struct DashboardView_Previews: PreviewProvider {
    static var previews: some View {
        DashboardView()
            .preferredColorScheme(.dark)
    }
}
