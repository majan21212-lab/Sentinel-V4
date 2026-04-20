import Foundation
import Combine

class BinanceAPIService {
    static let shared = BinanceAPIService()
    private let baseURL = "https://fapi.binance.com" // Futures API
    
    /// Fetches the latest 500 candles for a symbol.
    func fetchCandles(symbol: String, interval: String = "5m") -> AnyPublisher<[MarketCandle], Error> {
        let endpoint = "\(baseURL)/fapi/v1/klines?symbol=\(symbol)&interval=\(interval)&limit=500"
        guard let url = URL(string: endpoint) else {
            return Fail(error: URLError(.badURL)).eraseToAnyPublisher()
        }
        
        return URLSession.shared.dataTaskPublisher(for: url)
            .map { $0.data }
            .decode(type: [[Double]].self, decoder: JSONDecoder())
            .map { rawData in
                rawData.map { MarketCandle(timestamp: $0[0], open: $0[1], high: $0[2], low: $0[3], close: $0[4], volume: $0[5]) }
            }
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }
    
    /// Placeholder for signed order placement.
    func placeOrder(symbol: String, side: String, qty: Double, price: Double?, sl: Double, tp: Double) {
        // Implementation would involve HMAC-SHA256 signature using Secret from Keychain
        print("🚀 [iOS] Dispatching \(side) order for \(symbol) | Qty: \(qty)")
    }
}
