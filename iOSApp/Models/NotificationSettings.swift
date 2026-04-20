import Foundation
import SwiftUI

struct NotificationSettings: Codable {
    var minScore: Double = 70.0
    var filteredSymbols: [String] = []
    var notifyLocal: Bool = true
    var notifyValidated: Bool = true
}

class NotificationSettingsStore: ObservableObject {
    @AppStorage("notif_minScore") var minScore: Double = 70.0
    @AppStorage("notif_filteredSymbols") var filteredSymbolsRaw: String = "" // CSV
    @AppStorage("notif_notifyLocal") var notifyLocal: Bool = true
    @AppStorage("notif_notifyValidated") var notifyValidated: Bool = true
    
    var filteredSymbols: [String] {
        get { filteredSymbolsRaw.components(separatedBy: ",").filter { !$0.isEmpty } }
        set { filteredSymbolsRaw = newValue.joined(separator: ",") }
    }
}
