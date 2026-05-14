import SwiftUI

struct ReviewTableView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var settings: Settings

    var body: some View {
        Text("Review table — \(appState.rows.count) files")
            .font(.custom("SF Mono", size: 14))
            .foregroundColor(Color(hex: "#aaaaaa"))
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(hex: "#0d0d0d"))
    }
}
