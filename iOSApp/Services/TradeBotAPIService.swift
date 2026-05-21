import Foundation
import Combine

/// Sentinel V4 — Live GCP Bot API Service (iOS)
/// Single source of truth for all bot communication.
/// Endpoint: http://34.27.93.107:8080
final class TradeBotAPIService: ObservableObject {

    static let shared = TradeBotAPIService()

    // ── Config ────────────────────────────────────────────────────────────
    private let baseURL = "http://35.184.162.126:8000"
    private let wsURL   = "ws://35.184.162.126:8000/ws"
    private let webhookSecret = "SENTINEL_V4_SECRET"

    // ── WebSocket State ───────────────────────────────────────────────────
    @Published var liveState: BotState = BotState()
    @Published var isConnected: Bool = false

    private var webSocketTask: URLSessionWebSocketTask?
    private var cancellables = Set<AnyCancellable>()
    private var reconnectTimer: Timer?

    private init() {}

    // ── WebSocket ─────────────────────────────────────────────────────────

    func connect() {
        guard let url = URL(string: wsURL) else { return }
        webSocketTask = URLSession.shared.webSocketTask(with: url)
        webSocketTask?.resume()
        isConnected = true
        receiveMessage()
        reconnectTimer?.invalidate()
    }

    private func receiveMessage() {
        webSocketTask?.receive { [weak self] result in
            switch result {
            case .success(let message):
                if case .string(let text) = message,
                   let data = text.data(using: .utf8),
                   let state = try? JSONDecoder().decode(BotState.self, from: data) {
                    DispatchQueue.main.async { self?.liveState = state }
                }
                self?.receiveMessage() // keep listening
            case .failure:
                DispatchQueue.main.async { self?.isConnected = false }
                self?.scheduleReconnect()
            }
        }
    }

    func disconnect() {
        webSocketTask?.cancel(with: .normalClosure, reason: nil)
        isConnected = false
        reconnectTimer?.invalidate()
    }

    private func scheduleReconnect() {
        reconnectTimer = Timer.scheduledTimer(withTimeInterval: 3.0, repeats: false) { [weak self] _ in
            self?.connect()
        }
    }

    // ── REST Helpers ──────────────────────────────────────────────────────

    private func get<T: Decodable>(_ path: String, type: T.Type) -> AnyPublisher<T, Error> {
        guard let url = URL(string: "\(baseURL)\(path)") else {
            return Fail(error: URLError(.badURL)).eraseToAnyPublisher()
        }
        return URLSession.shared.dataTaskPublisher(for: url)
            .map(\.data)
            .decode(type: T.self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }

    private func post(_ path: String, body: [String: Any]) -> AnyPublisher<[String: String], Error> {
        guard let url = URL(string: "\(baseURL)\(path)"),
              let jsonData = try? JSONSerialization.data(withJSONObject: body) else {
            return Fail(error: URLError(.badURL)).eraseToAnyPublisher()
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = jsonData

        return URLSession.shared.dataTaskPublisher(for: request)
            .map(\.data)
            .decode(type: [String: String].self, decoder: JSONDecoder())
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }

    // ── Bot State ─────────────────────────────────────────────────────────

    func fetchStatus() -> AnyPublisher<BotState, Error> {
        get("/api/status", type: BotState.self)
    }

    // ── Signals ───────────────────────────────────────────────────────────

    func fetchSignals() -> AnyPublisher<[TradeSignal], Error> {
        get("/api/signals", type: [TradeSignal].self)
    }

    // ── Analytics ─────────────────────────────────────────────────────────

    func fetchAnalytics() -> AnyPublisher<[String: Double], Error> {
        get("/api/analytics", type: [String: Double].self)
    }

    // ── Settings ──────────────────────────────────────────────────────────

    func activateBot() -> AnyPublisher<[String: String], Error> {
        post("/api/settings", body: ["is_bot_active": true])
    }

    func deactivateBot() -> AnyPublisher<[String: String], Error> {
        post("/api/settings", body: ["is_bot_active": false])
    }

    func setDemoMode(_ demo: Bool) -> AnyPublisher<[String: String], Error> {
        post("/api/settings", body: ["demo_mode": demo])
    }

    // ── Market Management ─────────────────────────────────────────────────

    func addMarket(_ symbol: String) -> AnyPublisher<[String: String], Error> {
        post("/api/market/add", body: ["symbol": symbol])
    }

    func removeMarket(_ symbol: String) -> AnyPublisher<[String: String], Error> {
        post("/api/market/remove", body: ["symbol": symbol])
    }

    func toggleMarket(_ symbol: String) -> AnyPublisher<[String: String], Error> {
        post("/api/market/toggle", body: ["symbol": symbol])
    }

    // ── Trade Controls ────────────────────────────────────────────────────

    func closePosition(symbol: String) -> AnyPublisher<[String: String], Error> {
        post("/api/close_position", body: ["symbol": symbol])
    }

    func panicCloseAll() -> AnyPublisher<[String: String], Error> {
        post("/api/panic_close", body: [:])
    }

    // ── TradingView Webhook Simulator ─────────────────────────────────────

    func simulateSignal(ticker: String, action: String, price: Double,
                        tp: Double, sl: Double, pattern: String = "iOS Manual") 
    -> AnyPublisher<[String: String], Error> {
        post("/api/webhook/tradingview", body: [
            "secret":  webhookSecret,
            "action":  action,
            "ticker":  ticker,
            "price":   price,
            "tp":      tp,
            "sl":      sl,
            "pattern": pattern,
            "score":   95.0
        ])
    }
}

// ── Models ────────────────────────────────────────────────────────────────────

struct BotState: Codable {
    var status: String            = "INITIALIZING"
    var is_bot_active: Bool       = false
    var demo_mode: Bool           = true
    var demo_balance: Double      = 200.0
    var active_markets: [String]  = []
    var active_trades: [ActiveTrade] = []
    var signals: [TradeSignal]    = []
    var kill_switch: Bool         = false
    var execution_bias: String    = "TREND"
    var strategy_mode: String     = "PATTERN"
}

struct TradeSignal: Codable, Identifiable {
    let id: Int
    let symbol: String
    let direction: String
    let entry: Double
    let tp: Double
    let sl: Double
    let pattern: String?
    let created_at: String?
}

struct ActiveTrade: Codable, Identifiable {
    let id: Int
    let symbol: String
    let direction: String
    let entry: Double
    var pnl: Double?
    var status: String?
}
