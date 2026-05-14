import Foundation
import SwiftUI

@MainActor
final class Settings: ObservableObject {
    @AppStorage("modelName") var modelName: String = "qwen3.5:9b"
    @AppStorage("confidenceThreshold") var confidenceThreshold: Int = 90
    @AppStorage("lastInputPath") var lastInputPath: String = ""

    @Published var outputURL: URL?

    private let bookmarkKey = "outputFolderBookmark"

    init() {
        restoreOutputFolder()
    }

    func setOutputURL(_ url: URL) {
        outputURL = url
        do {
            let bookmark = try url.bookmarkData(
                options: .withSecurityScope,
                includingResourceValuesForKeys: nil,
                relativeTo: nil
            )
            UserDefaults.standard.set(bookmark, forKey: bookmarkKey)
        } catch {
            UserDefaults.standard.set(url.path, forKey: "outputFolderPath")
        }
    }

    private func restoreOutputFolder() {
        if let data = UserDefaults.standard.data(forKey: bookmarkKey) {
            var isStale = false
            do {
                let url = try URL(
                    resolvingBookmarkData: data,
                    options: .withSecurityScope,
                    relativeTo: nil,
                    bookmarkDataIsStale: &isStale
                )
                _ = url.startAccessingSecurityScopedResource()
                outputURL = url
                if isStale { setOutputURL(url) }
            } catch {
                outputURL = nil
            }
        } else if let path = UserDefaults.standard.string(forKey: "outputFolderPath") {
            outputURL = URL(fileURLWithPath: path)
        }
    }
}
