import SwiftUI

struct PortfolioView: View {
    @StateObject var vm = PortfolioViewModel()
    
    var body: some View {
        ZStack {
            // 1. Midnight Sentinel Background
            AmbientGlow()
                .edgesIgnoringSafeArea(.all)
            
            VStack(spacing: 0) {
                // 1. Consolidated Equity Header
                VStack(spacing: 8) {
                    Text("TOTAL EQUITY")
                        .font(.system(size: 10, weight: .black))
                        .tracking(3)
                        .foregroundColor(Theme.primaryPurple)
                    
                    Text("$\(String(format: "%.2f", vm.totalEquity))")
                        .font(.system(size: 42, weight: .bold, design: .rounded))
                        .foregroundColor(.white)
                    
                    HStack(spacing: 6) {
                        Circle()
                            .fill(vm.isLoading ? Color.orange : Color.green)
                            .frame(width: 6, height: 6)
                        Text(vm.isLoading ? "SYNCING..." : "LIVE FEED")
                            .font(.system(size: 8, weight: .black))
                            .foregroundColor(.secondary)
                    }
                }
                .padding(.vertical, 40)
                
                // 2. Charts & Stats
                ScrollView {
                    VStack(spacing: 25) {
                        // A. Linear PNL Chart
                        VStack(alignment: .leading) {
                            Text("EQUITY PERFORMANCE (24H)")
                                .font(.caption2.bold())
                                .foregroundColor(.secondary)
                                .padding(.leading)
                            
                            PNLChartView(points: vm.pnlHistory)
                        }
                        
                        // B. Strategy Leaderboard
                        if !vm.leaderboard.isEmpty {
                            VStack(alignment: .leading, spacing: 12) {
                                Text("STRATEGY PERFORMANCE")
                                    .font(.caption2.bold())
                                    .foregroundColor(.secondary)
                                    .padding(.leading)
                                
                                ForEach(vm.leaderboard) { stat in
                                    HStack {
                                        VStack(alignment: .leading, spacing: 4) {
                                            Text(stat.pattern)
                                                .font(.system(size: 14, weight: .bold))
                                            Text("\(stat.total) SIGNALS")
                                                .font(.system(size: 8, weight: .black))
                                                .foregroundColor(.secondary)
                                        }
                                        
                                        Spacer()
                                        
                                        VStack(alignment: .trailing, spacing: 4) {
                                            Text("\(String(format: "%.1f", stat.win_rate))%")
                                                .font(.system(size: 16, weight: .black, design: .monospaced))
                                                .foregroundColor(stat.win_rate >= 50 ? .green : .orange)
                                            
                                            Text("\(stat.wins)W / \(stat.losses)L")
                                                .font(.system(size: 8, weight: .bold))
                                                .foregroundColor(.secondary)
                                        }
                                    }
                                    .padding()
                                    .glassCard(cornerRadius: 20, opacity: 0.15)
                                }
                            }
                        }
                        
                        // C. Broker Groups
                        VStack(alignment: .leading, spacing: 12) {
                            Text("ACTIVE BROKERS")
                                .font(.caption2.bold())
                                .foregroundColor(.secondary)
                                .padding(.leading)
                            
                            ForEach(vm.brokerAccounts) { account in
                                BrokerSection(account: account)
                            }
                        }
                    }
                    .padding()
                }
                
                // 3. Global Panic Button
                // 3. Global Panic Button (Modernized)
                Button(action: { vm.closeAllPositions() }) {
                    HStack(spacing: 12) {
                        Image(systemName: "bolt.shield.fill")
                        Text("LIQUIDATE ALL POSITIONS")
                            .font(.system(size: 14, weight: .black))
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 18)
                    .background(Color.red.opacity(0.8))
                    .foregroundColor(.white)
                    .clipShape(Capsule())
                    .shadow(color: .red.opacity(0.3), radius: 15, x: 0, y: 8)
                    .padding(.horizontal, 30)
                    .padding(.bottom, 30)
                }
            }
        }
        .navigationTitle("Portfolio")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button(action: { vm.refresh() }) {
                    Image(systemName: "arrow.clockwise.circle.fill")
                        .foregroundColor(.blue)
                }
            }
        }
    }
}

struct BrokerSection: View {
    let account: BrokerAccount
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Broker Header
            HStack {
                Text(account.id)
                    .font(.headline)
                    .foregroundColor(.white)
                
                Spacer()
                
                Text("$\(String(format: "%.2f", account.summary.equity))")
                    .font(.system(size: 16, weight: .bold, design: .monospaced))
                    .foregroundColor(.blue)
            }
            
            Divider().background(Color.white.opacity(0.1))
            
            // Stats Row
            HStack(spacing: 20) {
                VStack(alignment: .leading) {
                    Text("BALANCE").font(.system(size: 8)).foregroundColor(.secondary)
                    Text("$\(Int(account.summary.balance))").font(.system(size: 12, weight: .bold))
                }
                
                VStack(alignment: .leading) {
                    Text("AVAILABLE").font(.system(size: 8)).foregroundColor(.secondary)
                    Text("$\(Int(account.summary.available))").font(.system(size: 12, weight: .bold))
                }
                
                VStack(alignment: .leading) {
                    Text("POSITIONS").font(.system(size: 8)).foregroundColor(.secondary)
                    Text("\(account.summary.openPositions)").font(.system(size: 12, weight: .bold))
                }
            }
            
            // Positions List
            if !account.positions.isEmpty {
                VStack(spacing: 8) {
                    ForEach(account.positions) { pos in
                        HStack {
                            VStack(alignment: .leading) {
                                Text(pos.symbol)
                                    .font(.system(size: 12, weight: .bold))
                                Text(pos.direction.rawValue)
                                    .font(.system(size: 10))
                                    .foregroundColor(pos.direction == .long ? .green : .red)
                            }
                            
                            Spacer()
                            
                            VStack(alignment: .trailing) {
                                Text("$\(String(format: "%.2f", pos.pnl))")
                                    .font(.system(size: 12, weight: .black, design: .monospaced))
                                    .foregroundColor(pos.pnl >= 0 ? .green : .red)
                                
                                Text("\(String(format: "%.3f", pos.size)) SIZE")
                                    .font(.system(size: 9))
                                    .foregroundColor(.secondary)
                            }
                        }
                        .padding(8)
                        .background(Color.black.opacity(0.2))
                        .cornerRadius(8)
                    }
                }
                .padding(.top, 5)
            } else {
                Text("No active positions")
                    .font(.system(size: 10))
                    .foregroundColor(.secondary)
                    .padding(.top, 5)
            }
        }
        .padding()
        .glassCard(opacity: 0.1)
    }
}
