import Foundation
import Combine

class PortfolioViewModel: ObservableObject {
    @Published var brokerAccounts: [BrokerAccount] = []
    @Published var totalEquity: Double = 0.0
    @Published var pnlHistory: [EquityPoint] = []
    @Published var leaderboard: [LeaderboardStat] = []
    @Published var isLoading: Bool = false
    
    private var cancellables = Set<AnyCancellable>()
    private let api = FastAPIService.shared
    private let timer = Timer.publish(every: 10, on: .main, in: .common).autoconnect()
    
    init() {
        refresh()
        setupAutoRefresh()
    }
    
    func setupAutoRefresh() {
        timer.sink { [weak self] _ in
            self?.refresh()
        }
        .store(in: &cancellables)
    }
    
    func refresh() {
        guard !isLoading else { return }
        isLoading = true
        
        Publishers.Zip4(
            api.fetchAccountSummary(),
            api.fetchPositions(),
            api.fetchPNLHistory(days: 1),
            api.fetchLeaderboard()
        )
        .sink(receiveCompletion: { [weak self] completion in
            self?.isLoading = false
        }, receiveValue: { [weak self] (summaries, allPositions, pnlPoints, stats) in
            self?.processBrokerData(summaries: summaries, allPositions: allPositions)
            self?.pnlHistory = pnlPoints
            self?.leaderboard = stats
        })
        .store(in: &cancellables)
    }
    
    private func processBrokerData(summaries: [String: AccountSummary], allPositions: [Position]) {
        var newBrokerAccounts: [BrokerAccount] = []
        var runningEquity = 0.0
        
        for (brokerName, summary) in summaries {
            let brokerPositions = allPositions.filter { $0.broker?.lowercased() == brokerName.lowercased() }
            newBrokerAccounts.append(BrokerAccount(id: brokerName.uppercased(), summary: summary, positions: brokerPositions))
            runningEquity += summary.equity
        }
        
        self.brokerAccounts = newBrokerAccounts
        self.totalEquity = runningEquity
    }
    
    func closeAllPositions() {
        isLoading = true
        let data: [String: Any] = ["action": "close_all"]
        
        let url = URL(string: "http://localhost:8000/api/trade")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        // No token needed for local trade endpoint or using shared key logic if implemented
        
        if let jsonData = try? JSONSerialization.data(withJSONObject: data) {
            request.httpBody = jsonData
        }
        
        URLSession.shared.dataTask(with: request) { [weak self] _, _, _ in
            DispatchQueue.main.async {
                self?.refresh()
            }
        }.resume()
    }
}
