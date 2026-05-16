import SwiftUI

@main
struct DocSorterApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .windowStyle(.hiddenTitleBar)
        .defaultSize(width: 960, height: 620)
        .commands {
            CommandGroup(replacing: .newItem) {}
        }
    }
}
