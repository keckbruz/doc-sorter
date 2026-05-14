import SwiftUI

struct DoneView: View {
    @EnvironmentObject var appState: AppState
    let moved: Int
    let skipped: Int
    let errors: Int
    let undoPath: String?

    var body: some View {
        Text("Done — moved \(moved) files")
            .font(.custom("SF Mono", size: 14))
            .foregroundColor(Color(hex: "#3fb950"))
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(hex: "#0d0d0d"))
    }
}
