import Foundation

class PatternEngine {
    
    // MARK: - Core Logic
    
    /// Detects a 'Waterfall' pattern: 5 consecutive candles in same direction + volume spike.
    static func detectWaterfall(candles: [MarketCandle]) -> (type: String, direction: TradeDirection, score: Double)? {
        guard candles.count >= 20 else { return nil }
        
        let recent = Array(candles.suffix(5))
        let isBull = recent.allSatisfy { $0.close > $0.open }
        let isBear = recent.allSatisfy { $0.close < $0.open }
        
        guard isBull || isBear else { return nil }
        
        let avgVolume = candles.suffix(20).map { $0.volume }.reduce(0, +) / 20
        let recentVolume = recent.map { $0.volume }.reduce(0, +) / 5
        let volRatio = recentVolume / avgVolume
        
        if volRatio > 1.5 {
            let direction: TradeDirection = isBull ? .long : .short
            let score = min(100.0, 60.0 + (volRatio * 10))
            return ("Waterfall", direction, score)
        }
        return nil
    }
    
    /// Detects 'Head and Shoulders' (Reversal)
    static func detectHeadAndShoulders(candles: [MarketCandle]) -> (type: String, direction: TradeDirection, score: Double)? {
        let ph = findPivots(series: candles.map { $0.high }, left: 5, right: 5, isHigh: true)
        guard ph.count >= 3 else { return nil }
        
        let lastThree = Array(ph.suffix(3))
        let lSh = lastThree[0].value
        let head = lastThree[1].value
        let rSh = lastThree[2].value
        
        if head > lSh && head > rSh && abs(lSh - rSh) < (calculateATR(candles: candles) * 2) {
            let lastClose = candles.last?.close ?? 0
            let neckline = candles.suffix(lastThree[2].index - lastThree[0].index).map { $0.low }.min() ?? 0
            
            if lastClose < neckline {
                return ("Head & Shoulders", .short, 75.0)
            }
        }
        return nil
    }
    
    /// Detects 'Cup and Handle' (Continuation)
    static func detectCupAndHandle(candles: [MarketCandle]) -> (type: String, direction: TradeDirection, score: Double)? {
        let ph = findPivots(series: candles.map { $0.high }, left: 5, right: 5, isHigh: true)
        guard let lastMajorPH = ph.last else { return nil }
        
        let lastClose = candles.last?.close ?? 0
        let prevClose = candles.dropLast().last?.close ?? 0
        
        if prevClose <= lastMajorPH.value && lastClose > lastMajorPH.value {
            let cupDepth = candles.suffix(10).map { $0.low }.min() ?? 0
            if cupDepth < (lastMajorPH.value - calculateATR(candles: candles) * 3) {
                return ("Cup & Handle", .long, 80.0)
            }
        }
        return nil
    }
    
    // MARK: - Institutional Logic Extensions
    
    /// Detects Fair Value Gaps (FVG) in the last 3 candles
    static func detectFVG(candles: [MarketCandle]) -> (direction: TradeDirection, size: Double)? {
        guard candles.count >= 3 else { return nil }
        let c = Array(candles.suffix(3))
        
        if c[2].low > c[0].high {
            return (.long, c[2].low - c[0].high)
        }
        
        if c[2].high < c[0].low {
            return (.short, c[0].low - c[2].high)
        }
        
        return nil
    }
    
    /// Detects a simplified Order Block
    static func detectOrderBlock(candles: [MarketCandle]) -> (direction: TradeDirection, price: Double)? {
        guard candles.count >= 6 else { return nil }
        let recent = Array(candles.suffix(5))
        
        let isStrongBull = recent.suffix(4).allSatisfy { $0.close > $0.open }
        if isStrongBull {
            let obCandle = candles[candles.count - 5]
            if obCandle.close < obCandle.open {
                return (.long, obCandle.low)
            }
        }
        
        let isStrongBear = recent.suffix(4).allSatisfy { $0.close < $0.open }
        if isStrongBear {
            let obCandle = candles[candles.count - 5]
            if obCandle.close > obCandle.open {
                return (.short, obCandle.high)
            }
        }
        
        return nil
    }

    static func isAlignedWithTrend(candles: [MarketCandle], direction: TradeDirection) -> Bool {
        guard candles.count >= 50 else { return true }
        let avg = candles.suffix(50).map { $0.close }.reduce(0, +) / 50
        let lastClose = candles.last?.close ?? 0
        return direction == .long ? lastClose > avg : lastClose < avg
    }
    
    // MARK: - Utilities
    
    private struct Pivot {
        let index: Int
        let value: Double
    }
    
    private static func findPivots(series: [Double], left: Int, right: Int, isHigh: Bool) -> [Pivot] {
        var pivots: [Pivot] = []
        guard series.count > left + right else { return pivots }
        
        for i in left..<(series.count - right) {
            let window = Array(series[(i-left)...(i+right)])
            if isHigh {
                if series[i] == (window.max() ?? 0) {
                    pivots.append(Pivot(index: i, value: series[i]))
                }
            } else {
                if series[i] == (window.min() ?? 0) {
                    pivots.append(Pivot(index: i, value: series[i]))
                }
            }
        }
        return pivots
    }
    
    private static func calculateATR(candles: [MarketCandle], period: Int = 14) -> Double {
        let ranges = candles.suffix(period).map { abs($0.high - $0.low) }
        return Double(ranges.reduce(0, +)) / Double(max(1, ranges.count))
    }
    
    static func detectPatterns(candles: [MarketCandle]) -> (type: String, direction: TradeDirection, score: Double)? {
        var basePattern: (type: String, direction: TradeDirection, score: Double)?
        
        if let hns = detectHeadAndShoulders(candles: candles) { basePattern = hns }
        else if let cnh = detectCupAndHandle(candles: candles) { basePattern = cnh }
        else if let water = detectWaterfall(candles: candles) { basePattern = water }
        
        guard var pattern = basePattern else { return nil }
        
        var confluenceMultiplier = 1.0
        
        if let fvg = detectFVG(candles: candles), fvg.direction == pattern.direction {
            confluenceMultiplier += 0.15
            pattern.type += " + FVG"
        }
        
        if let ob = detectOrderBlock(candles: candles), ob.direction == pattern.direction {
            confluenceMultiplier += 0.20
            pattern.type += " + OB"
        }
        
        if isAlignedWithTrend(candles: candles, direction: pattern.direction) {
            confluenceMultiplier += 0.10
        } else {
            confluenceMultiplier -= 0.20
        }
        
        pattern.score = min(100.0, pattern.score * confluenceMultiplier)
        return pattern
    }
}
