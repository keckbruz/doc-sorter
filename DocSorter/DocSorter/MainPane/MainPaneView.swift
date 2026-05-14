import SwiftUI

struct MainPaneView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var settings: Settings

    var body: some View {
        Group {
            switch appState.phase {
            case .idle:
                IdleView()
            case .preparing(let count, let isSuggesting):
                PreparingView(fileCount: count, isSuggestingTaxonomy: isSuggesting)
            case .taxonomySuggestion(let additions):
                TaxonomySuggestionView(additions: additions)
                    .environmentObject(appState)
            case .scanning(let classified, let review, let errors, let total, let currentFile):
                ScanningView(
                    classified: classified,
                    review: review,
                    errors: errors,
                    total: total,
                    currentFile: currentFile
                )
            case .review:
                ReviewTableView()
                    .environmentObject(appState)
                    .environmentObject(settings)
            case .done(let moved, let skipped, let errors, let undoPath):
                DoneView(moved: moved, skipped: skipped, errors: errors, undoPath: undoPath)
                    .environmentObject(appState)
            case .error(let message):
                ErrorView(message: message)
                    .environmentObject(appState)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(hex: "#0d0d0d"))
    }
}
