import Foundation
import Combine

class RiskSettingsViewModel: ObservableObject {
    @Published var maxDailyLoss: Double = 2.0
    @Published var maxPositions: Int = 3
    @Published var riskPerAsset: [String: Double] = ["DEFAULT": 1.0]
    @Published var aiScalingSymbols: [String] = []
    @Published var minMultiplier: Double = 0.5
    @Published var maxMultiplier: Double = 1.5
    @Published var activeProfile: String = "CONSERVATIVE"
    @Published var demoMode: Bool = true
    @Published var isLoading: Bool = false
    @Published var showConfirmation: Bool = false
    @Published var statusMessage: String = ""
    
    private let api = FastAPIService.shared
    private var cancellables = Set<AnyCancellable>()
    
    init() {
        fetchSettings()
    }
    
    func fetchSettings() {
        isLoading = true
        api.fetchRiskConfig()
            .sink(receiveCompletion: { [weak self] _ in
                self?.isLoading = false
            }, receiveValue: { [weak self] config in
                self?.parseConfig(config)
            })
            .store(in: &cancellables)
    }
    
    private func parseConfig(_ config: [String: Any]) {
        if let maxLoss = config["max_daily_loss_pct"] as? Double {
            self.maxDailyLoss = maxLoss
        }
        if let maxPos = config["max_open_positions"] as? Int {
            self.maxPositions = maxPos
        }
        if let riskAssets = config["risk_per_asset"] as? [String: Double] {
            self.riskPerAsset = riskAssets
        }
        if let aiSymbols = config["ai_scaling_symbols"] as? [String] {
            self.aiScalingSymbols = aiSymbols
        }
        if let minM = config["min_multiplier"] as? Double {
            self.minMultiplier = minM
        }
        if let maxM = config["max_multiplier"] as? Double {
            self.maxMultiplier = maxM
        }
        if let profile = config["active_profile"] as? String {
            self.activeProfile = profile
        }
        if let demo = config["demo_mode"] as? Bool {
            self.demoMode = demo
        }
    }
    
    func toggleAIScaling(for symbol: String) {
        if aiScalingSymbols.contains(symbol) {
            aiScalingSymbols.removeAll { $0 == symbol }
        } else {
            aiScalingSymbols.append(symbol)
        }
    }
    
    func prepareSave() {
        showConfirmation = true
    }
    
    func confirmAndSave() {
        isLoading = true
        let data: [String: Any] = [
            "max_daily_loss": maxDailyLoss,
            "max_positions": maxPositions,
            "risk_pct": riskPerAsset["DEFAULT"] ?? 1.0, 
            "asset": "DEFAULT",
            "ai_sizing_symbols": aiScalingSymbols,
            "min_multiplier": minMultiplier,
            "max_multiplier": maxMultiplier,
            "active_profile": activeProfile,
            "demo_mode": demoMode
        ]
        
        api.updateRiskSettings(data: data)
            .sink(receiveCompletion: { [weak self] completion in
                self?.isLoading = false
                if case .failure(let error) = completion {
                    self?.statusMessage = "Error: \(error.localizedDescription)"
                }
            }, receiveValue: { [weak self] success in
                if success {
                    self?.statusMessage = "Settings Synced Successfully ✅"
                    self?.fetchSettings() // Refresh
                }
            })
            .store(in: &cancellables)
    }
}
