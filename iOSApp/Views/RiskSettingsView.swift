import SwiftUI

struct RiskSettingsView: View {
    @StateObject var vm = RiskSettingsViewModel()
    
    var body: some View {
    var body: some View {
        ZStack {
            AmbientGlow()
                .edgesIgnoringSafeArea(.all)
            
            ScrollView(showsIndicators: false) {
                VStack(spacing: 25) {
                    
                    // 1. Core Profile Control
                    VStack(alignment: .leading, spacing: 15) {
                        Text("ENVIRONMENT CONTROL")
                            .font(.system(size: 10, weight: .black))
                            .tracking(2)
                            .foregroundColor(.secondary)
                        
                        Picker("Risk Profile", selection: $vm.activeProfile) {
                            Text("Conservative").tag("CONSERVATIVE")
                            Text("Optimal").tag("OPTIMAL")
                            Text("Aggressive").tag("AGGRESSIVE")
                        }
                        .pickerStyle(SegmentedPickerStyle())
                        
                        Toggle(isOn: $vm.demoMode) {
                            Label(vm.demoMode ? "Demo Mode" : "Live Trading", systemImage: vm.demoMode ? "play.circle" : "flame.fill")
                                .font(.headline)
                        }
                        .toggleStyle(SwitchToggleStyle(tint: Theme.primaryPurple))
                    }
                    .glassCard(cornerRadius: 24)

                    // 2. Constraints
                    VStack(alignment: .leading, spacing: 20) {
                        Text("GLOBAL CONSTRAINTS")
                            .font(.system(size: 10, weight: .black))
                            .tracking(2)
                            .foregroundColor(.secondary)
                        
                        VStack(alignment: .leading, spacing: 10) {
                            HStack {
                                Text("Daily Loss Limit")
                                Spacer()
                                Text("\(String(format: "%.1f", vm.maxDailyLoss))%")
                                    .foregroundColor(Theme.accentBlue)
                                    .bold()
                            }
                            Slider(value: $vm.maxDailyLoss, in: 0.5...10.0, step: 0.5)
                        }
                        
                        Stepper(value: $vm.maxPositions, in: 1...10) {
                            HStack {
                                Text("Max Open Positions")
                                Spacer()
                                Text("\(vm.maxPositions)")
                                    .bold()
                            }
                        }
                    }
                    .glassCard(cornerRadius: 24)
            
            Section(header: Text("Asset Risk Allocation")) {
                ForEach(vm.riskPerAsset.keys.sorted(), id: \.self) { asset in
                    VStack {
                        HStack {
                            Text(asset)
                            Spacer()
                            Text("\(String(format: "%.1f", vm.riskPerAsset[asset] ?? 0))%")
                                .foregroundColor(.blue)
                        }
                        
                        // AI Scaling Toggle per asset
                        if asset != "DEFAULT" {
                            Toggle(isOn: Binding(
                                get: { vm.aiScalingSymbols.contains(asset) },
                                set: { _ in vm.toggleAIScaling(for: asset) }
                            )) {
                                Label("AI Auto-Sizing", systemImage: "brain.head.profile")
                                    .font(.caption2)
                                    .foregroundColor(.blue.opacity(0.8))
                            }
                            .padding(.top, 4)
                        }
                    }
                    .padding(.vertical, 4)
                }
            }
            
                    // 3. AI Aggression
                    VStack(alignment: .leading, spacing: 20) {
                        Text("AI SCALING AGGRESSION")
                            .font(.system(size: 10, weight: .black))
                            .tracking(2)
                            .foregroundColor(.secondary)
                        
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Scaling Intensity: \(String(format: "%.1f", vm.minMultiplier))x - \(String(format: "%.1f", vm.maxMultiplier))x")
                                .font(.caption2)
                            
                            HStack {
                                Text("MIN")
                                Slider(value: $vm.minMultiplier, in: 0.1...1.0, step: 0.1)
                                Text("\(String(format: "%.1f", vm.minMultiplier))x")
                            }
                            
                            HStack {
                                Text("MAX")
                                Slider(value: $vm.maxMultiplier, in: 1.0...3.0, step: 0.1)
                                Text("\(String(format: "%.1f", vm.maxMultiplier))x")
                            }
                        }
                    }
                    .glassCard(cornerRadius: 24)
                    
                    // 4. Sync Button
                    Button(action: { vm.prepareSave() }) {
                        HStack {
                            if vm.isLoading {
                                ProgressView().tint(.white)
                            } else {
                                Image(systemName: "arrow.triangle.2.circlepath")
                                Text("SYNC SETTINGS TO CLOUD")
                                    .font(.system(size: 14, weight: .black))
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 18)
                        .background(Theme.primaryPurple)
                        .foregroundColor(.white)
                        .clipShape(Capsule())
                        .shadow(color: Theme.primaryPurple.opacity(0.4), radius: 15, x: 0, y: 8)
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 10)
                    .disabled(vm.isLoading)
                    
                    if !vm.statusMessage.isEmpty {
                        Text(vm.statusMessage)
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(Theme.accentBlue)
                            .padding()
                    }
                }
                .padding()
            }
        }
        .navigationTitle("Risk Engine")
        .alert(isPresented: $vm.showConfirmation) {
            Alert(
                title: Text("Confirm Strategy Tune?"),
                message: Text("These changes will be applied IMMEDIATELY to all active bots on the FastAPI Core."),
                primaryButton: .destructive(Text("Sync Changes")) {
                    vm.confirmAndSave()
                },
                secondaryButton: .cancel()
            )
        }
    }
}
