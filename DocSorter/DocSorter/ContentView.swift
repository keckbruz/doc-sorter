import SwiftUI

struct ContentView: View {
    @StateObject private var appState = AppState()
    @StateObject private var settings = Settings()

    var body: some View {
        ZStack {
            if appState.phase == .idle {
                SetupView()
                    .environmentObject(appState)
                    .environmentObject(settings)
                    .transition(.opacity)
                    .zIndex(1)
            } else {
                MainPaneView()
                    .environmentObject(appState)
                    .environmentObject(settings)
                    .transition(.opacity)
                    .zIndex(0)
            }
        }
        .animation(.easeInOut(duration: 0.2), value: appState.phase == .idle)
        .frame(minWidth: 680, minHeight: 480)
        .preferredColorScheme(.dark)
    }
}
