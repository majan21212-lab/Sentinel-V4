import Foundation
import Combine

class BinanceWebSocketService: NSObject {
    static let shared = BinanceWebSocketService()
    
    private var webSocket: URLSessionWebSocketTask?
    private let url = URL(string: "wss://fstream.binance.com/ws")!
    
    // Publishers
    let klinePublisher = PassthroughSubject<MarketCandle, Never>()
    let pricePublisher = PassthroughSubject<Double, Never>()
    
    func connect(symbol: String) {
        let session = URLSession(configuration: .default, delegate: self, delegateQueue: OperationQueue())
        webSocket = session.webSocketTask(with: url)
        webSocket?.resume()
        
        subscribe(to: symbol)
        receiveMessage()
    }
    
    private func subscribe(to symbol: String) {
        let subscribeMessage = """
        {
          "method": "SUBSCRIBE",
          "params": ["\(symbol.lowercased())@kline_1m", "\(symbol.lowercased())@ticker"],
          "id": 1
        }
        """
        let message = URLSessionWebSocketMessage.string(subscribeMessage)
        webSocket?.send(message) { error in
            if let error = error {
                print("❌ WebSocket Send Error: \(error)")
            }
        }
    }
    
    private func receiveMessage() {
        webSocket?.receive { [weak self] result in
            switch result {
            case .success(let message):
                switch message {
                case .string(let text):
                    self?.handleMessage(text)
                default: break
                }
                self?.receiveMessage() // Continue listening
            case .failure(let error):
                print("❌ WebSocket Receive Error: \(error)")
                self?.reconnect()
            }
        }
    }
    
    private func handleMessage(_ text: String) {
        guard let data = text.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }
        
        // Handle Kline
        if let e = json["e"] as? String, e == "kline",
           let k = json["k"] as? [String: Any] {
            let candle = MarketCandle(
                timestamp: k["t"] as? Double ?? 0,
                open: Double(k["o"] as? String ?? "0") ?? 0,
                high: Double(k["h"] as? String ?? "0") ?? 0,
                low: Double(k["l"] as? String ?? "0") ?? 0,
                close: Double(k["c"] as? String ?? "0") ?? 0,
                volume: Double(k["v"] as? String ?? "0") ?? 0
            )
            klinePublisher.send(candle)
        }
        
        // Handle Ticker (Price)
        if let e = json["e"] as? String, e == "24hrTicker",
           let c = json["c"] as? String {
            if let price = Double(c) {
                pricePublisher.send(price)
            }
        }
    }
    
    private func reconnect() {
        DispatchQueue.global().asyncAfter(deadline: .now() + 5) {
            print("🔄 Attempting WebSocket Reconnection...")
            // Logic to resubscribe to previous symbol
        }
    }
}

extension BinanceWebSocketService: URLSessionWebSocketDelegate {
    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didOpenWithProtocol protocol: String?) {
        print("✅ WebSocket Connected")
    }
    
    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didCloseWith closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) {
        print("🛑 WebSocket Closed")
    }
}
