import Foundation
import Combine

class MarketViewModel: ObservableObject {
    @Published var price: String = "0.00"
    @Published var activeSignals: [TradeSignal] = []
    @Published var isScanning: Bool = false
    @Published var autoTrade: Bool = false
    @Published var candleHistory: [MarketCandle] = []
    
    private var cancellables = Set<AnyCancellable>()
    private let ws = BinanceWebSocketService.shared
    private let api = BinanceAPIService.shared
    
    // MARK: - Scanner Logic
    
    func startScanner(symbol: String) {
        if isScanning { return }
        isScanning = true
        
        // Request Notifications
        NotificationManager.shared.requestPermissions()
        
        // 1. Initial Load (REST)
        api.fetchCandles(symbol: symbol)
            .sink(receiveCompletion: { _ in }, receiveValue: { [weak self] candles in
                self?.candleHistory = candles
            })
            .store(in: &cancellables)
            
        // 2. Real-Time Updates (WebSocket - Local Binance)
        ws.connect(symbol: symbol)
        
        // Price Updates
        ws.pricePublisher
            .receive(on: DispatchQueue.main)
            .sink { [weak self] newPrice in
                self?.price = String(format: "%.2f", newPrice)
            }
            .store(in: &cancellables)
            
        // Candle/Signal Updates
        ws.klinePublisher
            .receive(on: DispatchQueue.main)
            .sink { [weak self] candle in
                self?.processNewCandle(candle, symbol: symbol)
            }
            .store(in: &cancellables)
            
        // 3. Backend Priority Signals (FastAPI Synchronization)
        startBackendSignalSync()
    }
    
    private func processNewCandle(_ candle: MarketCandle, symbol: String) {
        // Update history
        if let last = candleHistory.last, last.timestamp == candle.timestamp {
            candleHistory[candleHistory.count - 1] = candle
        } else {
            candleHistory.append(candle)
            if candleHistory.count > 500 { candleHistory.removeFirst() }
        }
        
        // Run Detection on every tick
        if let result = PatternEngine.detectPatterns(candles: candleHistory) {
            let newSignal = TradeSignal(
                symbol: symbol,
                direction: result.direction,
                entry: candle.close,
                stopLoss: 0, 
                takeProfit1: 0,
                takeProfit2: nil,
                score: result.score,
                pattern: result.type,
                timestamp: Date(),
                isBackendValidated: false,
                confluence: "Local Logic: \(result.type)"
            )
            
            self.addSignalWithHaptics(newSignal)
        }
    }
    
    private func addSignalWithHaptics(_ signal: TradeSignal) {
        // Avoid duplicate signals for the same pattern/timestamp
        if !activeSignals.contains(where: { $0.pattern == signal.pattern && $0.entry == signal.entry }) {
            
            // Prioritize backend signals by putting them at the top
            if signal.isBackendValidated {
                activeSignals.insert(signal, at: 0)
            } else {
                activeSignals.append(signal)
            }
            
            // Limit to last 15 signals
            if activeSignals.count > 15 { activeSignals.removeLast() }
            
            // 🎯 NEW: Unified Haptic Intensity Logic
            let haptics = HapticManager.shared
            if signal.score >= 90 {
                haptics.triggerGodMode()
            } else if signal.score >= 80 {
                haptics.triggerHighConfidence()
            } else {
                haptics.triggerNormal()
            }
            
            // 🔔 NEW: Unified Notification Filtering
            if NotificationManager.shared.shouldNotify(for: signal) {
                NotificationManager.shared.sendTradeAlert(
                    symbol: signal.symbol,
                    direction: signal.direction.rawValue,
                    pattern: signal.pattern,
                    score: Int(signal.score)
                )
            }
        }
    }
    
    private func startBackendSignalSync() {
        let fastAPI = FastAPIService.shared
        fastAPI.connectWebSocket()
        
        // Sync Initial Auto-Trade State
        fastAPI.fetchRiskConfig()
            .sink(receiveCompletion: { _ in }, receiveValue: { [weak self] config in
                if let auto = config["auto_trade"] as? Bool {
                    self?.autoTrade = auto
                }
            })
            .store(in: &cancellables)

        fastAPI.$latestSignals
            .receive(on: DispatchQueue.main)
            .sink { [weak self] signals in
                for signal in signals {
                    self?.addSignalWithHaptics(signal)
                }
            }
            .store(in: &cancellables)
    }
    
    func toggleAutoTrade() {
        autoTrade.toggle()
        HapticManager.shared.triggerNormal()
        
        let fastAPI = FastAPIService.shared
        fastAPI.updateRiskSettings(data: ["auto_trade": autoTrade])
            .sink(receiveCompletion: { _ in }, receiveValue: { _ in })
            .store(in: &cancellables)
    }
}
