import SwiftUI

struct Theme {
    // Midnight Sentinel Palette
    static let background = Color(red: 0.02, green: 0.03, blue: 0.08) // OLED Black/Midnight
    static let midnightBlue = Color(red: 0.05, green: 0.07, blue: 0.15)
    static let primaryPurple = Color(red: 0.37, green: 0.18, blue: 0.92) // Cyber Purple
    static let accentBlue = Color(red: 0.0, green: 0.9, blue: 1.0) // Neon Blue
    
    static let glassOpacity = 0.15
    static let shadowOpacity = 0.4
}

struct AmbientGlow: View {
    @State private var animate = false
    
    var body: some View {
        ZStack {
            Theme.background.edgesIgnoringSafeArea(.all)
            
            // Drifting Purple Glow
            Circle()
                .fill(Theme.primaryPurple.opacity(0.3))
                .frame(width: 400, height: 400)
                .blur(radius: 100)
                .offset(x: animate ? 50 : -50, y: animate ? -100 : 100)
            
            // Drifting Blue Glow
            Circle()
                .fill(Theme.accentBlue.opacity(0.15))
                .frame(width: 300, height: 300)
                .blur(radius: 80)
                .offset(x: animate ? -100 : 100, y: animate ? 50 : -50)
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 10).repeatForever(autoreverses: true)) {
                animate.toggle()
            }
        }
    }
}
