import SwiftUI
import Charts

struct CandlestickChartView: View {
    let candles: [MarketCandle]
    
    var body: some View {
        Chart {
            ForEach(candles) { candle in
                // High-Low Wick
                RuleMark(
                    x: .value("Time", candle.timestamp),
                    yStart: .value("Low", candle.low),
                    yEnd: .value("High", candle.high)
                )
                .foregroundStyle(candle.close >= candle.open ? .green : .red)
                
                // Open-Close Body
                BarMark(
                    x: .value("Time", candle.timestamp),
                    yStart: .value("Open", candle.open),
                    yEnd: .value("Close", candle.close),
                    width: 4
                )
                .foregroundStyle(candle.close >= candle.open ? .green : .red)
            }
        }
        .chartYScale(domain: .automatic(includesZero: false))
        .frame(height: 250)
        .padding(.horizontal)
    }
}

struct CandlestickChartView_Previews: PreviewProvider {
    static var previews: some View {
        CandlestickChartView(candles: [
            MarketCandle(timestamp: 1, open: 100, high: 105, low: 98, close: 102, volume: 1000),
            MarketCandle(timestamp: 2, open: 102, high: 104, low: 100, close: 101, volume: 1000)
        ])
        .preferredColorScheme(.dark)
    }
}
