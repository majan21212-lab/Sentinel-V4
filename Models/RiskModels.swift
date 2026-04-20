import Foundation
import SwiftUI

struct AppRiskConfig: Codable {
    var riskPerTradePct: Double = 1.0
    var maxDailyLossPct: Double = 2.0
    var maxOpenPositions: Int = 3
    var trailingStopEnabled: Bool = true
}

// In a real app, you might use a more robust persistence layer,
// but for an MVP, UserDefaults via @AppStorage in views is efficient.
