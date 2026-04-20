import SwiftUI

struct NotificationSettingsView: View {
    @StateObject var store = NotificationSettingsStore()
    @State private var newSymbol: String = ""
    
    var body: some View {
        Form {
            Section(header: Text("Filter Logic")) {
                VStack(align: .leading) {
                    Text("Minimum Confluence: \(Int(store.minScore))%")
                    Slider(value: $store.minScore, in: 0...100, step: 5)
                }
                
                Toggle("Notify on Local Detection", isOn: $store.notifyLocal)
                Toggle("Notify on Backend Signals", isOn: $store.notifyValidated)
            }
            
            Section(header: Text("Symbol Whitelist")) {
                Text("If empty, you will receive alerts for all symbols.")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                HStack {
                    TextField("Add Symbol (e.g. BTCUSD)", text: $newSymbol)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                        .autocapitalization(.allCharacters)
                    
                    Button(action: addSymbol) {
                        Image(systemName: "plus.circle.fill")
                            .foregroundColor(.blue)
                    }
                }
                
                ForEach(store.filteredSymbols, id: \.self) { symbol in
                    HStack {
                        Text(symbol)
                        Spacer()
                        Button(action: { removeSymbol(symbol) }) {
                            Image(systemName: "trash")
                                .foregroundColor(.red)
                        }
                    }
                }
            }
            
            Section(header: Text("Haptic Intensity (Jewel Standard)")) {
                Text("💎 90%+ Confluence: Heavy Impact")
                Text("🔥 80%+ Confluence: Medium Impact")
                Text("⚡ Standard/Local: Light Impact")
            }
            .font(.caption)
            .foregroundColor(.secondary)
        }
        .navigationTitle("Notifications")
    }
    
    private func addSymbol() {
        let sym = newSymbol.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        if !sym.isEmpty && !store.filteredSymbols.contains(sym) {
            store.filteredSymbols.append(sym)
            newSymbol = ""
        }
    }
    
    private func removeSymbol(_ symbol: String) {
        store.filteredSymbols.removeAll { $0 == symbol }
    }
}
