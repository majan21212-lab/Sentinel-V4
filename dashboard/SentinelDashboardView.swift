import SwiftUI

struct SentinelDashboardView: View {
    @StateObject var viewModel = SentinelViewModel()
    
    var body: some View {
        NavigationView {
            VStack {
                StatusHeader(isOnline: viewModel.isOnline)
                
                List(viewModel.signals) { signal in
                    SignalRow(signal: signal)
                }
                .refreshable {
                    viewModel.fetchHistory()
                }
                
                EmergencyButton(action: {
                    viewModel.killSwitch()
                })
            }
            .navigationTitle("Jewel Sentinel")
            .onAppear {
                viewModel.fetchStatus()
                viewModel.fetchHistory()
            }
        }
    }
}

struct StatusHeader: View {
    let isOnline: Bool
    var body: some View {
        HStack {
            Circle()
                .fill(isOnline ? Color.green : Color.red)
                .frame(width: 10, height: 10)
            Text(isOnline ? "Bot Online" : "Bot Offline")
                .font(.subheadline)
        }
        .padding()
        .background(Color.secondary.opacity(0.1))
        .cornerRadius(10)
    }
}

struct SignalRow: View {
    let signal: TradeSignal
    var body: some View {
        HStack {
            VStack(alignment: .leading) {
                Text(signal.symbol)
                    .font(.headline)
                Text(signal.timestamp)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            Spacer()
            Text(signal.direction)
                .padding(8)
                .background(signal.direction == "LONG" ? Color.green.opacity(0.2) : Color.red.opacity(0.2))
                .cornerRadius(5)
        }
    }
}

struct EmergencyButton: View {
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            Text("🚨 KILL ALL TRADES")
                .font(.headline)
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color.red)
                .cornerRadius(15)
        }
        .padding()
    }
}
