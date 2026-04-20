import SwiftUI

struct AnalystBreakdownView: View {
    let signal: TradeSignal
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        ZStack {
            // Background
            Color.black.edgesIgnoringSafeArea(.all)
            
            VStack(alignment: .leading, spacing: 20) {
                // Header
                HStack {
                    VStack(alignment: .leading) {
                        Text("INSTITUTIONAL ANALYSIS")
                            .font(.caption.bold())
                            .tracking(2)
                            .foregroundColor(.blue)
                        
                        Text("\(signal.symbol) Breakdown")
                            .font(.title2.bold())
                            .foregroundColor(.white)
                    }
                    Spacer()
                    Button(action: { dismiss() }) {
                        Image(systemName: "xmark.circle.fill")
                            .font(.title2)
                            .foregroundColor(.white.opacity(0.5))
                    }
                }
                .padding(.top, 25)
                
                // Confluence Metrics (Visual)
                HStack(spacing: 15) {
                    MetricBox(title: "SCORE", value: "\(Int(signal.score))%", color: .blue)
                    MetricBox(title: "DIRECTION", value: signal.direction.rawValue, color: signal.direction == .long ? .green : .red)
                    MetricBox(title: "PATTERN", value: signal.pattern, color: .orange)
                }
                
                Divider().background(Color.white.opacity(0.1))
                
                // AI Analyst Findings
                ScrollView {
                    VStack(alignment: .leading, spacing: 15) {
                        HStack {
                            Image(systemName: "brain.head.profile")
                            Text("Senior Analyst Perspective")
                                .font(.headline)
                        }
                        .foregroundColor(.blue.opacity(0.8))
                        
                        if let rationale = signal.aiRationale {
                            // Split by newline and handle bullets
                            let lines = rationale.components(separatedBy: "\n").filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }
                            
                            VStack(alignment: .leading, spacing: 12) {
                                ForEach(lines, id: \.self) { line in
                                    HStack(alignment: .top, spacing: 10) {
                                        Text("•")
                                            .foregroundColor(.blue)
                                            .font(.headline)
                                        
                                        Text(line.replacingOccurrences(of: "•", with: "").trimmingCharacters(in: .whitespaces))
                                            .font(.body)
                                            .foregroundColor(.white.opacity(0.9))
                                            .lineSpacing(4)
                                    }
                                }
                            }
                        } else {
                            Text("Processing institutional data flow...")
                                .foregroundColor(.secondary)
                                .italic()
                        }
                    }
                }
                
                Spacer()
                
                // Disclaimer
                Text("Smart Money analysis provided by Sentinel Core. Use for confluence only.")
                    .font(.system(size: 8))
                    .foregroundColor(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.bottom, 10)
            }
            .padding(.horizontal)
        }
    }
}

struct MetricBox: View {
    let title: String
    let value: String
    let color: Color
    
    var body: some View {
        VStack(spacing: 4) {
            Text(title)
                .font(.system(size: 8, weight: .bold))
                .foregroundColor(.secondary)
            Text(value)
                .font(.system(size: 14, weight: .black))
                .foregroundColor(color)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
        .background(Color.white.opacity(0.05))
        .cornerRadius(10)
    }
}
