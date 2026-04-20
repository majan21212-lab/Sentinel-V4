import SwiftUI

struct PNLChartView: View {
    let points: [EquityPoint]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if points.count < 2 {
                VStack {
                    ProgressView()
                    Text("Accumulating Data Snapshots...")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
                .frame(maxWidth: .infinity)
                .frame(height: 150)
            } else {
                GeometryReader { geo in
                    ZStack {
                        // Gradient Fill
                        Path { path in
                            drawPath(in: geo.size, path: &path, fill: true)
                        }
                        .fill(
                            LinearGradient(
                                colors: [.blue.opacity(0.3), .blue.opacity(0.0)],
                                startPoint: .top,
                                endPoint: .bottom
                            )
                        )
                        
                        // Main Line
                        Path { path in
                            drawPath(in: geo.size, path: &path, fill: false)
                        }
                        .stroke(Color.blue, lineWidth: 2)
                    }
                }
                .frame(height: 150)
            }
        }
        .padding()
        .glassCard(opacity: 0.1)
    }
    
    private func drawPath(in size: CGSize, path: inout Path, fill: Bool) {
        let values = points.map { $0.equity }
        guard let min = values.min(), let max = values.max() else { return }
        
        let range = max - min
        let width = size.width / CGFloat(values.count - 1)
        
        for index in points.indices {
            let x = CGFloat(index) * width
            // Normalize y: (value - min) / range * height
            // We flip coordinates: height - normalized_y
            let normY = range == 0 ? 0.5 : (values[index] - min) / range
            let y = size.height - (CGFloat(normY) * size.height)
            
            if index == 0 {
                path.move(to: CGPoint(x: x, y: y))
            } else {
                path.addLine(to: CGPoint(x: x, y: y))
            }
        }
        
        if fill {
            path.addLine(to: CGPoint(x: size.width, y: size.height))
            path.addLine(to: CGPoint(x: 0, y: size.height))
            path.closeSubpath()
        }
    }
}
