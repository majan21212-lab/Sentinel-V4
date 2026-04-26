import SwiftUI

struct DashboardView: View {
    @StateObject var vm = MarketViewModel()
    @State private var selectedSignal: TradeSignal? = nil
    
    // Grid layout for KPIs
    let columns = [
        GridItem(.flexible()),
        GridItem(.flexible())
    ]
    
    var body: some View {
        NavigationView {
            ZStack {
                AmbientGlow()
                    .edgesIgnoringSafeArea(.all)
                
                ScrollView(showsIndicators: false) {
                    VStack(spacing: 25) {
                        
                        // 1. Header & Master Switch
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("JEWEL ELITE")
                                    .font(.system(size: 20, weight: .black))
                                    .tracking(1)
                                
                                Text("BOT MANAGER")
                                    .font(.system(size: 10, weight: .bold))
                                    .foregroundColor(Theme.primaryPurple)
                                    .tracking(2)
                            }
                            
                            Spacer()
                            
                            // Prominent Master Switch
                            Button(action: { 
                                vm.toggleAutoTrade()
                                HapticManager.shared.triggerHighConfidence()
                            }) {
                                HStack {
                                    Circle()
                                        .fill(vm.autoTrade ? Color.green : Color.red)
                                        .frame(width: 8, height: 8)
                                    Text(vm.autoTrade ? "ENGINE ACTIVE" : "ENGINE STOPPED")
                                        .font(.system(size: 10, weight: .black))
                                }
                                .padding(.horizontal, 12)
                                .padding(.vertical, 8)
                                .background(Color.white.opacity(0.1))
                                .cornerRadius(8)
                                .overlay(
                                    RoundedRectangle(cornerRadius: 8)
                                        .stroke(vm.autoTrade ? Color.green.opacity(0.5) : Color.white.opacity(0.1), lineWidth: 1)
                                )
                            }
                        }
                        .padding(.horizontal)
                        .padding(.top, 10)
                        
                        // 2. KPI Grid (4 Cards)
                        LazyVGrid(columns: columns, spacing: 15) {
                            KPICard(title: "TOTAL BALANCE", value: "$\(vm.price)", subText: "+0.00% Today", color: .green)
                            KPICard(title: "AI WIN RATE", value: "85.4%", subText: "30D Avg", color: .green)
                            KPICard(title: "DAILY DRAWDOWN", value: "0.0%", subText: "Max Allowed: 5.0%", color: .red)
                            KPICard(title: "ACTIVE STRATEGY", value: "Pattern", subText: "Exposure: 12%", color: Theme.primaryPurple)
                        }
                        .padding(.horizontal)
                        
                        // 3. Asset Allocation (Donut Chart visual replacement)
                        VStack(alignment: .leading, spacing: 15) {
                            Text("CURRENT ASSET EXPOSURE")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundColor(.secondary)
                                .padding(.horizontal)
                            
                            HStack {
                                // Dummy donut visual
                                ZStack {
                                    Circle()
                                        .stroke(Color.white.opacity(0.1), lineWidth: 15)
                                        .frame(width: 100, height: 100)
                                    Circle()
                                        .trim(from: 0.0, to: 0.2)
                                        .stroke(Theme.primaryPurple, style: StrokeStyle(lineWidth: 15, lineCap: .round))
                                        .frame(width: 100, height: 100)
                                        .rotationEffect(.degrees(-90))
                                    Text("88%\nCASH")
                                        .font(.system(size: 12, weight: .bold))
                                        .multilineTextAlignment(.center)
                                }
                                
                                Spacer()
                                
                                VStack(alignment: .leading, spacing: 10) {
                                    AllocationRow(color: Theme.primaryPurple, symbol: "ETHUSD", pct: "12%")
                                    AllocationRow(color: .white.opacity(0.1), symbol: "CASH", pct: "88%")
                                }
                                .padding(.trailing, 20)
                            }
                            .padding()
                            .glassCard(cornerRadius: 20)
                            .padding(.horizontal)
                        }
                        
                        // 4. Live Bot Activity / Detections
                        VStack(alignment: .leading, spacing: 15) {
                            HStack {
                                Text("AI DETECTION LOG")
                                    .font(.system(size: 10, weight: .bold))
                                    .foregroundColor(.secondary)
                                
                                Spacer()
                                
                                if vm.isScanning {
                                    Text("SCANNING...")
                                        .font(.system(size: 8, weight: .bold))
                                        .foregroundColor(.green)
                                }
                            }
                            .padding(.horizontal)
                            
                            if vm.activeSignals.isEmpty {
                                VStack(spacing: 10) {
                                    ProgressView().tint(Theme.primaryPurple)
                                    Text("Awaiting market opportunities...")
                                        .font(.caption2)
                                        .foregroundColor(.secondary)
                                }
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 30)
                                .glassCard(cornerRadius: 16)
                                .padding(.horizontal)
                            } else {
                                ForEach(vm.activeSignals.prefix(5)) { signal in
                                    SignalCard(signal: signal)
                                        .padding(.horizontal)
                                }
                            }
                        }
                        .padding(.bottom, 30)
                    }
                }
            }
            .navigationBarHidden(true)
        }
    }
}

struct KPICard: View {
    let title: String
    let value: String
    let subText: String
    let color: Color
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.system(size: 9, weight: .bold))
                .foregroundColor(.secondary)
            
            Text(value)
                .font(.system(size: 18, weight: .black))
                .foregroundColor(.white)
            
            Text(subText)
                .font(.system(size: 10, weight: .bold))
                .foregroundColor(color)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(15)
        .glassCard(cornerRadius: 16)
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(color.opacity(0.3), lineWidth: 1)
        )
    }
}

struct AllocationRow: View {
    let color: Color
    let symbol: String
    let pct: String
    
    var body: some View {
        HStack {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(symbol).font(.system(size: 12, weight: .bold))
            Spacer()
            Text(pct).font(.system(size: 12, weight: .black))
        }
    }
}

struct SignalCard: View {
    let signal: TradeSignal
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(signal.symbol)
                    .font(.system(size: 14, weight: .black))
                Text(signal.pattern)
                    .font(.system(size: 10, weight: .medium))
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            Text(signal.direction.rawValue)
                .font(.system(size: 12, weight: .black))
                .padding(.horizontal, 10)
                .padding(.vertical, 4)
                .background(signal.direction == .long ? Color.green.opacity(0.1) : Color.red.opacity(0.1))
                .foregroundColor(signal.direction == .long ? .green : .red)
                .cornerRadius(6)
        }
        .padding(12)
        .background(Color.black.opacity(0.3))
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color.white.opacity(0.05), lineWidth: 1)
        )
    }
}

struct DashboardView_Previews: PreviewProvider {
    static var previews: some View {
        DashboardView()
            .preferredColorScheme(.dark)
    }
}
