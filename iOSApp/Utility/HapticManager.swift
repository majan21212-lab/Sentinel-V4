import UIKit

class HapticManager {
    static let shared = HapticManager()
    
    /// 💎 GodMode Pattern (90%+ Confluence)
    func triggerGodMode() {
        let generator = UIImpactFeedbackGenerator(style: .heavy)
        generator.prepare()
        generator.impactOccurred()
        
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) {
            let success = UINotificationFeedbackGenerator()
            success.notificationOccurred(.success)
        }
    }
    
    /// 🔥 High Confluence Pattern (80%+ )
    func triggerHighConfidence() {
        let generator = UIImpactFeedbackGenerator(style: .medium)
        generator.prepare()
        generator.impactOccurred()
    }
    
    /// ⚡ Normal / Local Pattern
    func triggerNormal() {
        let generator = UIImpactFeedbackGenerator(style: .light)
        generator.prepare()
        generator.impactOccurred()
    }
    
    @available(*, deprecated, message: "Use triggerGodMode, triggerHighConfidence, or triggerNormal instead")
    func triggerLong() { triggerHighConfidence() }
    
    @available(*, deprecated, message: "Use specific patterns")
    func triggerShort() { triggerNormal() }
}
