import Foundation

enum TradeDirection: String, Codable {
    case long = "LONG"
    case short = "SHORT"
}

struct TradeSignal: Identifiable, Codable {
    var id = UUID()
    let symbol: String
    let direction: TradeDirection
    let entry: Double
    let stopLoss: Double
    let takeProfit1: Double
    let takeProfit2: Double?
    let score: Double
    let pattern: String
    let timestamp: Date
    
    // Institutional Metadata
    var isBackendValidated: Bool = false
    var confluence: String? = nil
    var aiRationale: String? = nil
    
    enum CodingKeys: String, CodingKey {
        case symbol, direction, entry, score, pattern, timestamp
        case stopLoss = "sl"
        case takeProfit1 = "tp"
        case takeProfit2 = "tp2"
        case isBackendValidated = "validated"
        case confluence
        case aiRationale = "ai_rationale"
    }
}

struct MarketCandle: Identifiable, Codable {
    var id: Double { timestamp }
    let timestamp: Double
    let open: Double
    let high: Double
    let low: Double
    let close: Double
    let volume: Double
}

struct Position: Identifiable, Codable {
    var id: String { "\(symbol)-\(direction)" }
    let symbol: String
    let entryPrice: Double
    let markPrice: Double
    let size: Double
    let pnl: Double
    let direction: TradeDirection
    var broker: String? = nil // To support grouping
}

struct AccountSummary: Codable {
    let equity: Double
    let balance: Double
    let available: Double
    let openPositions: Int
}

struct BrokerAccount: Identifiable {
    let id: String // Broker Name (e.g. Binance, Exness)
    let summary: AccountSummary
    let positions: [Position]
}

struct EquityPoint: Codable, Identifiable {
    var id: String { time }
    let equity: Double
    let time: String
}

struct LeaderboardStat: Codable, Identifiable {
    var id: String { pattern }
    let pattern: String
    let total: Int
    let wins: Int
    let losses: Int
    let win_rate: Double
}
