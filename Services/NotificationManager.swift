import Foundation
import UserNotifications

class NotificationManager {
    static let shared = NotificationManager()
    private let settings = NotificationSettingsStore()
    
    func requestPermissions() {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound]) { granted, error in
            if granted {
                print("✅ Notification permissions granted")
            } else if let error = error {
                print("❌ Notification permission error: \(error)")
            }
        }
    }
    
    func shouldNotify(for signal: TradeSignal) -> Bool {
        // 1. Check Source Toggles
        if signal.isBackendValidated && !settings.notifyValidated { return false }
        if !signal.isBackendValidated && !settings.notifyLocal { return false }
        
        // 2. Check Score Threshold
        if signal.score < settings.minScore { return false }
        
        // 3. Check Symbol Filter (If any symbols are in the whitelist)
        let whitelist = settings.filteredSymbols
        if !whitelist.isEmpty && !whitelist.contains(signal.symbol.uppercased()) {
            return false
        }
        
        return true
    }
    
    func sendTradeAlert(symbol: String, direction: String, pattern: String, score: Int) {
        // Note: For full filtering, callers should use shouldNotify(for:) before calling this
        // or we pass the whole TradeSignal here. For backward compatibility, we'll keep the signature
        // but recommendation is to pass Signal.
        
        let content = UNMutableNotificationContent()
        content.title = score >= 90 ? "💎 JEWEL ELITE: \(pattern)" : "🔥 Jewel Alert: \(pattern)"
        content.body = "\(direction) Signal detected for \(symbol) | Confluence: \(score)%"
        content.sound = score >= 90 ? .defaultCritical : .default
        
        let request = UNNotificationRequest(
            identifier: UUID().uuidString,
            content: content,
            trigger: nil
        )
        
        UNUserNotificationCenter.current().add(request)
    }
}
