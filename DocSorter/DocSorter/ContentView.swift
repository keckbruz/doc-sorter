import SwiftUI

struct ContentView: View {
    @StateObject private var appState = AppState()
    @StateObject private var settings = Settings()

    var body: some View {
        NavigationSplitView(columnVisibility: .constant(.all)) {
            SidebarView()
                .environmentObject(appState)
                .environmentObject(settings)
                .navigationSplitViewColumnWidth(220)
        } detail: {
            MainPaneView()
                .environmentObject(appState)
                .environmentObject(settings)
        }
        .frame(minWidth: 900, minHeight: 600)
    }
}
