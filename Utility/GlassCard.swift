import SwiftUI

struct GlassCard: ViewModifier {
    var cornerRadius: CGFloat = 24
    var opacity: Double = 0.1
    
    func body(content: Content) -> some View {
        content
            .padding()
            .background(
                ZStack {
                    // Ultra Thin Material for actual glass effect
                    if #available(iOS 15.0, *) {
                        Rectangle()
                            .fill(.ultraThinMaterial)
                            .opacity(0.9)
                    } else {
                        Rectangle()
                            .fill(Color.white.opacity(opacity))
                    }
                    
                    // Subtle inner color tint
                    Theme.midnightBlue.opacity(0.2)
                    
                    // High-end stroke
                    RoundedRectangle(cornerRadius: cornerRadius)
                        .stroke(
                            LinearGradient(
                                colors: [
                                    Color.white.opacity(0.2),
                                    Color.white.opacity(0.05),
                                    Theme.primaryPurple.opacity(0.1)
                                ],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            ),
                            lineWidth: 1
                        )
                }
            )
            .clipShape(RoundedRectangle(cornerRadius: cornerRadius))
            .shadow(color: Color.black.opacity(Theme.shadowOpacity), radius: 20, x: 0, y: 10)
    }
}

extension View {
    func glassCard(cornerRadius: CGFloat = 24, opacity: Double = 0.1) -> some View {
        self.modifier(GlassCard(cornerRadius: cornerRadius, opacity: opacity))
    }
}
