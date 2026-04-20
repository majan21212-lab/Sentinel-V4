import Foundation
import Combine

struct TradeSignal: Codable, Identifiable {
    let id: Int
    let symbol: String
    let direction: String
    let timestamp: String
    let status: String?
}

class SentinelViewModel: ObservableObject {
    @Published var signals: [TradeSignal] = []
    @Published var balances: [String: Any] = [:]
    @Published var isOnline: Bool = false
    
    private let baseURL = "http://YOUR_SERVER_IP:8000"
    private let apiToken = "sentinel_debug_key"
    
    func fetchStatus() {
        guard let url = URL(string: "\(baseURL)/status") else { return }
        var request = URLRequest(url: url)
        request.addValue(apiToken, forHTTPHeaderField: "X-Token")
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                self.isOnline = error == nil
            }
        }.resume()
    }
    
    func fetchHistory() {
        guard let url = URL(string: "\(baseURL)/history?limit=20") else { return }
        var request = URLRequest(url: url)
        request.addValue(apiToken, forHTTPHeaderField: "X-Token")
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            if let data = data {
                if let decoded = try? JSONDecoder().decode([TradeSignal].self, from: data) {
                    DispatchQueue.main.async {
                        self.signals = decoded
                    }
                }
            }
        }.resume()
    }
    
    func killSwitch() {
        // Logic to stop all trading and close positions
        // This would call a POST /kill endpoint in sentinel_api.py
        print("🚨 EMERGENY STOP TRIGGERED")
    }
}
