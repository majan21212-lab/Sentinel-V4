import Foundation
import Combine

class FastAPIService: ObservableObject {
    static let shared = FastAPIService()
    
    private let baseURL = "http://34.26.143.224:8000" // Default backend URL
    private var webSocketTask: URLSessionWebSocketTask?
    private let token = KeychainManager.shared.load(for: "sentinel_api_token") ?? "sentinel_debug_key"
    
    @Published var latestSignals: [TradeSignal] = []
    @Published var connectionStatus: String = "Disconnected"
    @Published var balance: Double = 0.0
    @Published var activeBroker: String = "DEMO"
    
    private var cancellables = Set<AnyCancellable>()
    
    // MARK: - REST API
    
    func fetchAccountSummary() -> AnyPublisher<[String: AccountSummary], Error> {
        let url = URL(string: "\(baseURL)/account")!
        var request = URLRequest(url: url)
        request.addValue(token, forHTTPHeaderField: "X-Token")
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map { $0.data }
            .decode(type: [String: AccountSummary].self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    func fetchTradeHistory() -> AnyPublisher<[TradeSignal], Error> {
        let url = URL(string: "\(baseURL)/history")!
        var request = URLRequest(url: url)
        request.addValue(token, forHTTPHeaderField: "X-Token")
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map { $0.data }
            .decode(type: [TradeSignal].self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    func fetchPositions() -> AnyPublisher<[Position], Error> {
        let url = URL(string: "\(baseURL)/positions")!
        var request = URLRequest(url: url)
        request.addValue(token, forHTTPHeaderField: "X-Token")
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map { $0.data }
            .decode(type: [Position].self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    func fetchPNLHistory(days: Int = 1) -> AnyPublisher<[EquityPoint], Error> {
        let url = URL(string: "\(baseURL)/api/pnl_history?days=\(days)")!
        var request = URLRequest(url: url)
        request.addValue(token, forHTTPHeaderField: "X-Token")
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map { $0.data }
            .decode(type: [EquityPoint].self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    func fetchLeaderboard() -> AnyPublisher<[LeaderboardStat], Error> {
        let url = URL(string: "\(baseURL)/api/leaderboard")!
        var request = URLRequest(url: url)
        request.addValue(token, forHTTPHeaderField: "X-Token")
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map { $0.data }
            .decode(type: [LeaderboardStat].self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    func updateRiskSettings(data: [String: Any]) -> AnyPublisher<Bool, Error> {
        let url = URL(string: "\(baseURL)/api/settings")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.addValue(token, forHTTPHeaderField: "X-Token")
        
        guard let jsonData = try? JSONSerialization.data(withJSONObject: data) else {
            return Fail(error: URLError(.badURL)).eraseToAnyPublisher()
        }
        request.httpBody = jsonData
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map { $0.response as? HTTPURLResponse }
            .map { $0?.statusCode == 200 }
            .mapError { $0 }
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    func fetchRiskConfig() -> AnyPublisher<[String: Any], Error> {
        // We'll fetch the current SHARED_DATA from a new status endpoint or /settings (GET)
        // For now, let's assume we can get it from /status
        let url = URL(string: "\(baseURL)/status")!
        var request = URLRequest(url: url)
        request.addValue(token, forHTTPHeaderField: "X-Token")
        
        return URLSession.shared.dataTaskPublisher(for: request)
            .map { $0.data }
            .tryMap { data in
                let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
                return json?["risk_config"] as? [String: Any] ?? [:]
            }
            .mapError { $0 }
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    // MARK: - WebSocket (Live Streams)
    
    func connectWebSocket() {
        let wsURL = URL(string: "ws://34.26.143.224:8000/ws")!
        webSocketTask = URLSession.shared.webSocketTask(with: wsURL)
        webSocketTask?.resume()
        
        self.connectionStatus = "Connected"
        receiveMessage()
    }
    
    private func receiveMessage() {
        webSocketTask?.receive { [weak self] result in
            switch result {
            case .success(let message):
                switch message {
                case .string(let text):
                    self?.handleIncomingData(text)
                default: break
                }
                self?.receiveMessage() // Loop
            case .failure(let error):
                print("WebSocket Error: \(error)")
                DispatchQueue.main.async {
                    self?.connectionStatus = "Reconnecting..."
                }
                // Retry after delay
                DispatchQueue.main.asyncAfter(deadline: .now() + 5) {
                    self?.connectWebSocket()
                }
            }
        }
    }
    
    private func handleIncomingData(_ text: String) {
        guard let data = text.data(using: .utf8) else { return }
        
        // The backend broadcasts SHARED_DATA which contains "signals"
        if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            DispatchQueue.main.async {
                if let demoBal = json["demo_balance"] as? Double, self.activeBroker == "DEMO" {
                    self.balance = demoBal
                } else if let liveBal = json["balance"] as? Double {
                    self.balance = liveBal
                }
                
                if let broker = json["active_broker"] as? String {
                    self.activeBroker = broker
                }
            }

            if let signalsArray = json["signals"] as? [[String: Any]] {
                // Map raw JSON to TradeSignal
                let decoder = JSONDecoder()
                if let signalsData = try? JSONSerialization.data(withJSONObject: signalsArray),
                   var decodedSignals = try? decoder.decode([TradeSignal].self, from: signalsData) {
                    
                    DispatchQueue.main.async {
                        for i in 0..<decodedSignals.count {
                            decodedSignals[i].isBackendValidated = true
                        }
                        self.latestSignals = decodedSignals
                    }
                }
            }
        }
    }
}
