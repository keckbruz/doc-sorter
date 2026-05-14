import Foundation
import AppKit

@MainActor
final class SidebarViewModel: ObservableObject {
    @Published var errorMessage: String?

    func pickFolder(completion: @escaping (URL) -> Void) {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.prompt = "Select"
        if panel.runModal() == .OK, let url = panel.url {
            completion(url)
        }
    }

    func validate(inputPath: String, outputURL: URL?) -> String? {
        if inputPath.isEmpty { return "Input folder is required." }
        if outputURL == nil { return "Output folder is required." }
        if !FileManager.default.fileExists(atPath: inputPath) { return "Input folder does not exist." }
        return nil
    }

    func countFiles(at url: URL) -> Int {
        let exts: Set<String> = [
            "pdf", "png", "jpg", "jpeg", "tiff", "txt",
            "docx", "doc", "xlsx", "csv", "heic",
        ]
        var count = 0
        guard let enumerator = FileManager.default.enumerator(
            at: url,
            includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles, .skipsPackageDescendants]
        ) else { return 0 }
        for case let fileURL as URL in enumerator {
            if exts.contains(fileURL.pathExtension.lowercased()) { count += 1 }
        }
        return count
    }
}
