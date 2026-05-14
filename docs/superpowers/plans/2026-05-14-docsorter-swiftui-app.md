# DocSorter macOS SwiftUI App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a native macOS SwiftUI app that wraps the Python doc-sorter CLI with folder pickers, real-time scan progress, keyboard-driven review table, and undo support — no terminal required.

**Architecture:** Single Xcode project `DocSorter`. Split pane: left sidebar (always-visible settings + scan trigger) + right pane (state machine: Idle → Preparing → TaxonomySuggestion → Scanning → Review → Done). `PythonBridge` launches subprocesses and parses JSONL. `AppState` is the single ObservableObject driving all UI transitions. The Python CLI additions plan (`2026-05-14-python-cli-additions.md`) must be executed first — the `scan --output-format jsonl` and `suggest-taxonomy` subcommands are prerequisites.

**Tech Stack:** Swift 5.9+, SwiftUI, macOS 14+, Xcode 15+. No third-party packages.

---

## File Structure

- **Create:** `DocSorter/DocSorterApp.swift` — app entry point, window setup, minimum size
- **Create:** `DocSorter/ContentView.swift` — root `NavigationSplitView` wiring sidebar + main pane
- **Create:** `DocSorter/Model/AppState.swift` — `ObservableObject` with workflow state enum + transition methods
- **Create:** `DocSorter/Model/ReviewRow.swift` — single file in the review table (id, filename, category, subcategory, confidence, needsReview, isSelected, suggestedFilename, aiReason)
- **Create:** `DocSorter/Model/Settings.swift` — `@AppStorage`-backed model, output folder security-scoped bookmark
- **Create:** `DocSorter/Bridge/ScanEvent.swift` — `Codable` structs for JSONL events (progress, done, error)
- **Create:** `DocSorter/Bridge/PythonBridge.swift` — subprocess launcher; `suggestTaxonomy()`, `scan()` as AsyncSequence of ScanEvent, `apply()`, `undo()`
- **Create:** `DocSorter/Sidebar/SidebarView.swift` — input/output folder pickers, model field, threshold stepper, Scan button
- **Create:** `DocSorter/Sidebar/SidebarViewModel.swift` — validates fields, persists settings via `Settings`
- **Create:** `DocSorter/MainPane/MainPaneView.swift` — routes to correct child based on `AppState.phase`
- **Create:** `DocSorter/MainPane/IdleView.swift` — "Pick an input folder and press Scan."
- **Create:** `DocSorter/MainPane/PreparingView.swift` — file count + indeterminate taxonomy bar
- **Create:** `DocSorter/MainPane/TaxonomySuggestionView.swift` — shows additions, Add/Skip buttons
- **Create:** `DocSorter/MainPane/ScanningView.swift` — progress bar + filename + live counters
- **Create:** `DocSorter/MainPane/ReviewTableView.swift` — `Table` with keyboard handling, detail panel expansion
- **Create:** `DocSorter/MainPane/DoneView.swift` — result summary + Undo + Scan again

---

### Task 1: Xcode Project Skeleton

**Files:**
- Create: `DocSorter/DocSorterApp.swift`
- Create: `DocSorter/ContentView.swift`
- Create: `DocSorter/Model/AppState.swift`

Prerequisites: Xcode 15+ installed. Create the project via File → New → Project → macOS App, name `DocSorter`, SwiftUI interface, minimum deployment macOS 14.0. Save inside the repo root at `DocSorter/`.

- [ ] **Step 1: Create Xcode project**

In Xcode: File → New → Project → macOS → App.
- Product Name: `DocSorter`
- Interface: SwiftUI
- Language: Swift
- Minimum Deployment: macOS 14.0
- Save to repo root: `/path/to/doc-sorter/DocSorter/`

Open `DocSorter.xcodeproj`. Delete the default `ContentView.swift` body — we'll replace it.

- [ ] **Step 2: Write `AppState.swift` with workflow enum**

Create `DocSorter/Model/AppState.swift`:

```swift
import Foundation
import Combine

enum AppPhase: Equatable {
    case idle
    case preparing(fileCount: Int?, isSuggestingTaxonomy: Bool)
    case taxonomySuggestion(additions: [String: [String]])
    case scanning(classified: Int, review: Int, errors: Int, total: Int, currentFile: String)
    case review
    case done(moved: Int, skipped: Int, errors: Int, undoPath: String?)
    case error(message: String)
}

@MainActor
final class AppState: ObservableObject {
    @Published var phase: AppPhase = .idle
    @Published var rows: [ReviewRow] = []
    @Published var planPath: String?
    @Published var undoPath: String?

    func startPreparing() {
        phase = .preparing(fileCount: nil, isSuggestingTaxonomy: false)
    }

    func updateFileCount(_ count: Int) {
        phase = .preparing(fileCount: count, isSuggestingTaxonomy: true)
    }

    func showTaxonomySuggestion(_ additions: [String: [String]]) {
        if additions.isEmpty {
            startScanning()
        } else {
            phase = .taxonomySuggestion(additions: additions)
        }
    }

    func startScanning() {
        phase = .scanning(classified: 0, review: 0, errors: 0, total: 0, currentFile: "")
    }

    func updateScan(event: ProgressEvent) {
        phase = .scanning(
            classified: event.classified,
            review: event.review,
            errors: event.errors,
            total: rows.count > 0 ? rows.count : 0,
            currentFile: event.file
        )
    }

    func finishScan(event: DoneEvent) {
        planPath = event.plan
        undoPath = event.undo
        phase = .review
    }

    func applyDone(moved: Int, skipped: Int, errors: Int, undoPath: String?) {
        self.undoPath = undoPath
        phase = .done(moved: moved, skipped: skipped, errors: errors, undoPath: undoPath)
    }

    func showError(_ message: String) {
        phase = .error(message: message)
    }

    func reset() {
        phase = .idle
        rows = []
        planPath = nil
        undoPath = nil
    }
}
```

- [ ] **Step 3: Write `ContentView.swift` skeleton**

```swift
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
```

- [ ] **Step 4: Write `DocSorterApp.swift`**

```swift
import SwiftUI

@main
struct DocSorterApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .windowStyle(.hiddenTitleBar)
        .defaultSize(width: 1100, height: 700)
    }
}
```

- [ ] **Step 5: Build and confirm no errors**

In Xcode, press `Cmd+B`. Expected: build succeeds (with "cannot find type" errors for `SidebarView`, `MainPaneView`, `ReviewRow`, `Settings`, `ProgressEvent`, `DoneEvent` — these are stubs we'll add in later tasks).

---

### Task 2: Data Models

**Files:**
- Create: `DocSorter/Model/ReviewRow.swift`
- Create: `DocSorter/Model/Settings.swift`
- Create: `DocSorter/Bridge/ScanEvent.swift`

- [ ] **Step 1: Create `ReviewRow.swift`**

```swift
import Foundation

struct ReviewRow: Identifiable {
    let id: UUID
    var filename: String
    var category: String
    var subcategory: String
    var confidence: Int
    var needsReview: Bool
    var isSelected: Bool
    var suggestedFilename: String
    var aiReason: String
    var sourcePath: String

    init(
        filename: String,
        category: String,
        subcategory: String,
        confidence: Int,
        needsReview: Bool,
        suggestedFilename: String,
        aiReason: String,
        sourcePath: String
    ) {
        self.id = UUID()
        self.filename = filename
        self.category = category
        self.subcategory = subcategory
        self.confidence = confidence
        self.needsReview = needsReview
        self.isSelected = !needsReview
        self.suggestedFilename = suggestedFilename
        self.aiReason = aiReason
        self.sourcePath = sourcePath
    }
}
```

- [ ] **Step 2: Create `Settings.swift`**

```swift
import Foundation
import SwiftUI

@MainActor
final class Settings: ObservableObject {
    @AppStorage("modelName") var modelName: String = "qwen3.5:9b"
    @AppStorage("confidenceThreshold") var confidenceThreshold: Int = 90
    @AppStorage("lastInputPath") var lastInputPath: String = ""

    // Output folder stored as a security-scoped bookmark
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
            // If bookmark creation fails, store plain path as fallback
            UserDefaults.standard.set(url.path, forKey: "outputFolderPath")
        }
    }

    private func restoreOutputFolder() {
        guard let data = UserDefaults.standard.data(forKey: bookmarkKey) else {
            // Fallback: plain path stored when bookmark failed
            if let path = UserDefaults.standard.string(forKey: "outputFolderPath") {
                outputURL = URL(fileURLWithPath: path)
            }
            return
        }
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
            if isStale {
                setOutputURL(url)
            }
        } catch {
            outputURL = nil
        }
    }
}
```

- [ ] **Step 3: Create `ScanEvent.swift`**

```swift
import Foundation

struct ProgressEvent: Codable {
    let event: String  // "progress"
    let file: String
    let status: String
    let classified: Int
    let review: Int
    let errors: Int
    let total: Int?
}

struct DoneEvent: Codable {
    let event: String  // "done"
    let plan: String
    let undo: String?
    let classified: Int
    let review: Int
    let errors: Int
}

struct ErrorEvent: Codable {
    let event: String  // "error"
    let message: String
}

enum ScanEvent {
    case progress(ProgressEvent)
    case done(DoneEvent)
    case error(ErrorEvent)
}
```

- [ ] **Step 4: Build and confirm**

`Cmd+B`. Expected: builds clean (no more "cannot find type ReviewRow/Settings/ScanEvent" errors for those types).

---

### Task 3: PythonBridge

**Files:**
- Create: `DocSorter/Bridge/PythonBridge.swift`

`PythonBridge` is the only place that touches `Process`. Each method creates a subprocess with the correct arguments and decodes stdout.

- [ ] **Step 1: Create `PythonBridge.swift`**

```swift
import Foundation

enum BridgeError: Error {
    case pythonNotFound
    case processError(String)
    case decodingError(String)
}

struct ApplyResult {
    let moved: Int
    let skipped: Int
    let errors: Int
    let undoPath: String?
}

final class PythonBridge {

    static let shared = PythonBridge()

    private func python3Path() throws -> String {
        let candidates = ["/usr/bin/python3", "/usr/local/bin/python3", "/opt/homebrew/bin/python3"]
        for path in candidates {
            if FileManager.default.fileExists(atPath: path) { return path }
        }
        // Fall back to PATH lookup
        let which = Process()
        which.executableURL = URL(fileURLWithPath: "/usr/bin/which")
        which.arguments = ["python3"]
        let pipe = Pipe()
        which.standardOutput = pipe
        try which.run()
        which.waitUntilExit()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let path = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        if !path.isEmpty { return path }
        throw BridgeError.pythonNotFound
    }

    // Returns taxonomy addition suggestions as a dictionary, or empty on any failure.
    func suggestTaxonomy(inputPath: String, outputPath: String, model: String) async throws -> [String: [String]] {
        let python = try python3Path()
        let process = Process()
        process.executableURL = URL(fileURLWithPath: python)
        process.arguments = [
            "-m", "doc_cleaner",
            "suggest-taxonomy",
            "--input", inputPath,
            "--output-root", outputPath,
            "--model", model,
        ]
        let stdout = Pipe()
        process.standardOutput = stdout
        process.standardError = Pipe()  // discard stderr (Rich output)

        try process.run()
        process.waitUntilExit()

        let data = stdout.fileHandleForReading.readDataToEndOfFile()
        guard !data.isEmpty,
              let result = try? JSONDecoder().decode([String: [String]].self, from: data)
        else { return [:] }
        return result
    }

    // AsyncThrowingStream of ScanEvent lines. Caller iterates with `for await`.
    func scan(
        inputPath: String,
        outputPath: String,
        planPath: String,
        model: String,
        confidenceThreshold: Int,
        ollamaHost: String = "http://127.0.0.1:11434"
    ) -> AsyncThrowingStream<ScanEvent, Error> {
        AsyncThrowingStream { continuation in
            Task.detached {
                do {
                    let python = try self.python3Path()
                    let process = Process()
                    process.executableURL = URL(fileURLWithPath: python)
                    process.arguments = [
                        "-m", "doc_cleaner", "scan",
                        "--input", inputPath,
                        "--output-root", outputPath,
                        "--plan", planPath,
                        "--model", model,
                        "--confidence", String(confidenceThreshold),
                        "--ollama-host", ollamaHost,
                        "--output-format", "jsonl",
                    ]
                    let stdout = Pipe()
                    process.standardOutput = stdout
                    process.standardError = Pipe()

                    try process.run()

                    // Read line by line from stdout
                    let handle = stdout.fileHandleForReading
                    var buffer = Data()

                    while process.isRunning || handle.availableData.count > 0 {
                        let chunk = handle.availableData
                        if chunk.isEmpty {
                            try await Task.sleep(nanoseconds: 50_000_000)
                            continue
                        }
                        buffer.append(chunk)
                        while let newline = buffer.firstIndex(of: UInt8(ascii: "\n")) {
                            let lineData = buffer[buffer.startIndex...newline]
                            buffer.removeSubrange(buffer.startIndex...newline)
                            guard let line = String(data: lineData, encoding: .utf8)?
                                    .trimmingCharacters(in: .whitespacesAndNewlines),
                                  !line.isEmpty,
                                  let jsonData = line.data(using: .utf8)
                            else { continue }

                            if let event = Self.decode(jsonData) {
                                continuation.yield(event)
                                if case .done = event { break }
                                if case .error = event { break }
                            }
                        }
                    }
                    // Drain any remaining buffered lines
                    let remaining = handle.readDataToEndOfFile()
                    buffer.append(remaining)
                    for lineData in buffer.split(separator: UInt8(ascii: "\n")) {
                        if let line = String(data: lineData, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines),
                           !line.isEmpty,
                           let jsonData = line.data(using: .utf8),
                           let event = Self.decode(jsonData) {
                            continuation.yield(event)
                        }
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }

    func apply(planPath: String, outputPath: String) async throws -> ApplyResult {
        let python = try python3Path()
        let process = Process()
        process.executableURL = URL(fileURLWithPath: python)
        process.arguments = ["-m", "doc_cleaner", "apply", "--plan", planPath, "--output-root", outputPath]
        let stdout = Pipe()
        let stderr = Pipe()
        process.standardOutput = stdout
        process.standardError = stderr
        try process.run()
        process.waitUntilExit()

        // Parse stdout for undo path (apply prints "Undo manifest: <path>")
        let out = String(data: stdout.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
        let undoPath = out.components(separatedBy: "\n")
            .first { $0.contains("Undo manifest:") }
            .flatMap { $0.components(separatedBy: "Undo manifest:").last?.trimmingCharacters(in: .whitespaces) }

        if process.terminationStatus != 0 {
            let err = String(data: stderr.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? "Unknown error"
            throw BridgeError.processError(err)
        }
        // Parse "Moved: N  Skipped: N  Errors: N" from stdout
        let moved = Self.parseLine(out, keyword: "Moved:")
        let skipped = Self.parseLine(out, keyword: "Skipped:")
        let errors = Self.parseLine(out, keyword: "Errors:")
        return ApplyResult(moved: moved, skipped: skipped, errors: errors, undoPath: undoPath)
    }

    func undo(undoManifestPath: String) async throws {
        let python = try python3Path()
        let process = Process()
        process.executableURL = URL(fileURLWithPath: python)
        process.arguments = ["-m", "doc_cleaner", "undo", "--undo-manifest", undoManifestPath]
        let stderr = Pipe()
        process.standardError = stderr
        try process.run()
        process.waitUntilExit()
        if process.terminationStatus != 0 {
            let err = String(data: stderr.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? "Unknown error"
            throw BridgeError.processError(err)
        }
    }

    private static func decode(_ data: Data) -> ScanEvent? {
        if let e = try? JSONDecoder().decode(ProgressEvent.self, from: data), e.event == "progress" {
            return .progress(e)
        }
        if let e = try? JSONDecoder().decode(DoneEvent.self, from: data), e.event == "done" {
            return .done(e)
        }
        if let e = try? JSONDecoder().decode(ErrorEvent.self, from: data), e.event == "error" {
            return .error(e)
        }
        return nil
    }

    private static func parseLine(_ text: String, keyword: String) -> Int {
        guard let range = text.range(of: keyword) else { return 0 }
        let after = text[range.upperBound...].trimmingCharacters(in: .whitespaces)
        return Int(after.prefix(while: { $0.isNumber })) ?? 0
    }
}
```

- [ ] **Step 2: Build and confirm**

`Cmd+B`. Expected: builds clean.

---

### Task 4: SidebarView

**Files:**
- Create: `DocSorter/Sidebar/SidebarView.swift`
- Create: `DocSorter/Sidebar/SidebarViewModel.swift`

- [ ] **Step 1: Create `SidebarViewModel.swift`**

```swift
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
        let inputURL = URL(fileURLWithPath: inputPath)
        if !FileManager.default.fileExists(atPath: inputURL.path) { return "Input folder does not exist." }
        return nil
    }
}
```

- [ ] **Step 2: Create `SidebarView.swift`**

```swift
import SwiftUI

struct SidebarView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var settings: Settings
    @StateObject private var viewModel = SidebarViewModel()

    private var isScanning: Bool {
        if case .scanning = appState.phase { return true }
        if case .preparing = appState.phase { return true }
        return false
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("DOC SORTER")
                .font(.custom("SF Mono", size: 10))
                .foregroundColor(Color(hex: "#555555"))
                .padding(.top, 16)

            folderRow(label: "INPUT", path: settings.lastInputPath) {
                viewModel.pickFolder { url in
                    settings.lastInputPath = url.path
                }
            }

            folderRow(label: "OUTPUT", path: settings.outputURL?.path ?? "") {
                viewModel.pickFolder { url in
                    settings.setOutputURL(url)
                }
            }

            VStack(alignment: .leading, spacing: 4) {
                label("MODEL")
                TextField("qwen3.5:9b", text: $settings.modelName)
                    .textFieldStyle(.plain)
                    .font(.custom("SF Mono", size: 12))
                    .foregroundColor(.white)
                    .padding(6)
                    .background(Color(hex: "#111111"))
                    .cornerRadius(4)
            }

            VStack(alignment: .leading, spacing: 4) {
                label("CONFIDENCE")
                HStack {
                    Text("\(settings.confidenceThreshold)%")
                        .font(.custom("SF Mono", size: 12))
                        .foregroundColor(.white)
                        .frame(width: 40, alignment: .leading)
                    Stepper("", value: $settings.confidenceThreshold, in: 0...100)
                        .labelsHidden()
                }
            }

            Spacer()

            if let error = viewModel.errorMessage {
                Text(error)
                    .font(.custom("SF Mono", size: 10))
                    .foregroundColor(Color(hex: "#f85149"))
                    .fixedSize(horizontal: false, vertical: true)
            }

            Button(action: startScan) {
                Text("SCAN")
                    .font(.custom("SF Mono", size: 13).bold())
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
                    .background(isScanning ? Color(hex: "#1a1a1a") : Color(hex: "#3a8fff"))
                    .foregroundColor(isScanning ? Color(hex: "#555555") : .white)
                    .cornerRadius(6)
            }
            .buttonStyle(.plain)
            .disabled(isScanning)
            .padding(.bottom, 16)
        }
        .padding(.horizontal, 12)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(hex: "#0d0d0d"))
    }

    private func folderRow(label labelText: String, path: String, action: @escaping () -> Void) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            label(labelText)
            Button(action: action) {
                HStack {
                    Text(path.isEmpty ? "Choose…" : URL(fileURLWithPath: path).lastPathComponent)
                        .font(.custom("SF Mono", size: 11))
                        .foregroundColor(path.isEmpty ? Color(hex: "#555555") : .white)
                        .lineLimit(1)
                        .truncationMode(.middle)
                    Spacer()
                    Image(systemName: "folder")
                        .font(.system(size: 11))
                        .foregroundColor(Color(hex: "#3a8fff"))
                }
                .padding(6)
                .background(Color(hex: "#111111"))
                .cornerRadius(4)
            }
            .buttonStyle(.plain)
        }
    }

    private func label(_ text: String) -> some View {
        Text(text)
            .font(.custom("SF Mono", size: 9))
            .foregroundColor(Color(hex: "#555555"))
    }

    private func startScan() {
        let validationError = viewModel.validate(inputPath: settings.lastInputPath, outputURL: settings.outputURL)
        viewModel.errorMessage = validationError
        guard validationError == nil else { return }

        appState.startPreparing()
        Task {
            await runScanWorkflow()
        }
    }

    private func runScanWorkflow() async {
        let inputPath = settings.lastInputPath
        guard let outputURL = settings.outputURL else { return }
        let outputPath = outputURL.path
        let model = settings.modelName

        // Step 1: count files
        let count = countFiles(at: URL(fileURLWithPath: inputPath))
        await MainActor.run { appState.updateFileCount(count) }

        // Step 2: suggest taxonomy
        do {
            let additions = try await PythonBridge.shared.suggestTaxonomy(
                inputPath: inputPath,
                outputPath: outputPath,
                model: model
            )
            await MainActor.run { appState.showTaxonomySuggestion(additions) }

            // If taxonomy suggestion was shown, wait for user confirmation
            // (handled by TaxonomySuggestionView which calls appState.startScanning())
            if !additions.isEmpty { return }
        } catch {
            await MainActor.run { appState.showError("Taxonomy suggestion failed: \(error.localizedDescription)") }
            return
        }

        await runScan()
    }

    private func runScan() async {
        let inputPath = settings.lastInputPath
        guard let outputURL = settings.outputURL else { return }
        let outputPath = outputURL.path
        let planPath = outputURL.appendingPathComponent(".doc-sorter-plan.csv").path

        do {
            let stream = PythonBridge.shared.scan(
                inputPath: inputPath,
                outputPath: outputPath,
                planPath: planPath,
                model: settings.modelName,
                confidenceThreshold: settings.confidenceThreshold
            )
            for try await event in stream {
                await MainActor.run {
                    switch event {
                    case .progress(let e):
                        appState.updateScan(event: e)
                    case .done(let e):
                        appState.finishScan(event: e)
                    case .error(let e):
                        appState.showError(e.message)
                    }
                }
            }
        } catch {
            await MainActor.run { appState.showError(error.localizedDescription) }
        }
    }

    private func countFiles(at url: URL) -> Int {
        let exts: Set<String> = ["pdf", "png", "jpg", "jpeg", "tiff", "txt", "docx", "doc", "xlsx", "csv", "heic"]
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

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let r = Double((int >> 16) & 0xFF) / 255
        let g = Double((int >> 8) & 0xFF) / 255
        let b = Double(int & 0xFF) / 255
        self.init(red: r, green: g, blue: b)
    }
}
```

- [ ] **Step 3: Build and confirm**

`Cmd+B`. Expected: builds (unresolved `SidebarView` references in `ContentView` will now resolve; `MainPaneView` still missing).

---

### Task 5: Main Pane — Idle, Preparing, TaxonomySuggestion

**Files:**
- Create: `DocSorter/MainPane/IdleView.swift`
- Create: `DocSorter/MainPane/PreparingView.swift`
- Create: `DocSorter/MainPane/TaxonomySuggestionView.swift`
- Create: `DocSorter/MainPane/MainPaneView.swift`

- [ ] **Step 1: Create `IdleView.swift`**

```swift
import SwiftUI

struct IdleView: View {
    var body: some View {
        VStack(spacing: 8) {
            Text("Pick an input folder and press Scan.")
                .font(.custom("SF Mono", size: 14))
                .foregroundColor(Color(hex: "#555555"))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(hex: "#0d0d0d"))
    }
}
```

- [ ] **Step 2: Create `PreparingView.swift`**

```swift
import SwiftUI

struct PreparingView: View {
    let fileCount: Int?
    let isSuggestingTaxonomy: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            sectionLabel("PREPARING SCAN")

            VStack(alignment: .leading, spacing: 6) {
                if let count = fileCount {
                    Text("Found \(count) documents")
                        .font(.custom("SF Mono", size: 13))
                        .foregroundColor(.white)
                    ProgressView(value: 1.0)
                        .accentColor(Color(hex: "#3a8fff"))
                        .frame(height: 3)
                } else {
                    Text("Counting files…")
                        .font(.custom("SF Mono", size: 13))
                        .foregroundColor(Color(hex: "#aaaaaa"))
                    ProgressView()
                        .progressViewStyle(.linear)
                        .accentColor(Color(hex: "#3a8fff"))
                        .frame(height: 3)
                }
            }

            if isSuggestingTaxonomy {
                VStack(alignment: .leading, spacing: 6) {
                    sectionLabel("SUGGESTING TAXONOMY")
                    Text("Peeking at file contents…")
                        .font(.custom("SF Mono", size: 12))
                        .foregroundColor(Color(hex: "#aaaaaa"))
                    ProgressView()
                        .progressViewStyle(.linear)
                        .accentColor(Color(hex: "#3a8fff"))
                        .frame(height: 3)
                }
            }

            Spacer()
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(hex: "#0d0d0d"))
    }

    private func sectionLabel(_ text: String) -> some View {
        Text(text)
            .font(.custom("SF Mono", size: 9))
            .foregroundColor(Color(hex: "#555555"))
    }
}
```

- [ ] **Step 3: Create `TaxonomySuggestionView.swift`**

```swift
import SwiftUI

struct TaxonomySuggestionView: View {
    @EnvironmentObject var appState: AppState
    let additions: [String: [String]]

    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            Text("Suggested additions to taxonomy:")
                .font(.custom("SF Mono", size: 13))
                .foregroundColor(Color(hex: "#aaaaaa"))

            VStack(alignment: .leading, spacing: 6) {
                ForEach(Array(additions.sorted(by: { $0.key < $1.key })), id: \.key) { cat, subs in
                    if subs.isEmpty {
                        Text("+ \(cat)")
                            .font(.custom("SF Mono", size: 12))
                            .foregroundColor(Color(hex: "#3fb950"))
                    } else {
                        ForEach(subs, id: \.self) { sub in
                            Text("+ \(cat) / \(sub)")
                                .font(.custom("SF Mono", size: 12))
                                .foregroundColor(Color(hex: "#3fb950"))
                        }
                    }
                }
            }
            .padding(16)
            .background(Color(hex: "#111111"))
            .cornerRadius(6)

            HStack(spacing: 12) {
                Button("Add to taxonomy") {
                    appState.startScanning()
                    // Note: taxonomy additions are passed to scan via CLI flags in a future enhancement.
                    // For v1, the suggestions are informational — the scan uses the existing output folder taxonomy.
                }
                .buttonStyle(PrimaryButtonStyle())

                Button("Skip") {
                    appState.startScanning()
                }
                .buttonStyle(SecondaryButtonStyle())
            }

            Spacer()
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(hex: "#0d0d0d"))
    }
}

struct PrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.custom("SF Mono", size: 12).bold())
            .foregroundColor(.white)
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(Color(hex: "#3a8fff"))
            .cornerRadius(6)
            .opacity(configuration.isPressed ? 0.8 : 1)
    }
}

struct SecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.custom("SF Mono", size: 12))
            .foregroundColor(Color(hex: "#aaaaaa"))
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(Color(hex: "#1a1a1a"))
            .cornerRadius(6)
            .opacity(configuration.isPressed ? 0.8 : 1)
    }
}
```

- [ ] **Step 4: Create `MainPaneView.swift`**

```swift
import SwiftUI

struct MainPaneView: View {
    @EnvironmentObject var appState: AppState

    var body: some View {
        Group {
            switch appState.phase {
            case .idle:
                IdleView()
            case .preparing(let count, let isSuggesting):
                PreparingView(fileCount: count, isSuggestingTaxonomy: isSuggesting)
            case .taxonomySuggestion(let additions):
                TaxonomySuggestionView(additions: additions)
            case .scanning(let classified, let review, let errors, let total, let currentFile):
                ScanningView(classified: classified, review: review, errors: errors, total: total, currentFile: currentFile)
            case .review:
                ReviewTableView()
            case .done(let moved, let skipped, let errors, let undoPath):
                DoneView(moved: moved, skipped: skipped, errors: errors, undoPath: undoPath)
            case .error(let message):
                ErrorView(message: message)
            }
        }
    }
}

struct ErrorView: View {
    let message: String
    @EnvironmentObject var appState: AppState

    var body: some View {
        VStack(spacing: 16) {
            Text(message)
                .font(.custom("SF Mono", size: 13))
                .foregroundColor(Color(hex: "#f85149"))
                .multilineTextAlignment(.center)
                .padding()

            if message.lowercased().contains("ollama") {
                Button("Start Ollama") {
                    NSWorkspace.shared.open(URL(string: "ollama://")!)
                }
                .buttonStyle(PrimaryButtonStyle())
            }

            Button("Reset") { appState.reset() }
                .buttonStyle(SecondaryButtonStyle())
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(hex: "#0d0d0d"))
    }
}
```

- [ ] **Step 5: Build and confirm**

`Cmd+B`. Expected: builds clean. `ScanningView`, `ReviewTableView`, `DoneView` still missing — add stubs in `MainPaneView.swift` temporarily if needed:

```swift
struct ScanningView_Placeholder: View { var body: some View { Text("Scanning…") } }
```

---

### Task 6: ScanningView

**Files:**
- Create: `DocSorter/MainPane/ScanningView.swift`

- [ ] **Step 1: Create `ScanningView.swift`**

```swift
import SwiftUI

struct ScanningView: View {
    let classified: Int
    let review: Int
    let errors: Int
    let total: Int
    let currentFile: String

    private var progress: Double {
        guard total > 0 else { return 0 }
        return Double(classified + review + errors) / Double(total)
    }

    private var processed: Int { classified + review + errors }

    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            sectionLabel("CLASSIFYING")

            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("Progress")
                        .font(.custom("SF Mono", size: 12))
                        .foregroundColor(Color(hex: "#aaaaaa"))
                    Spacer()
                    Text(total > 0 ? "\(processed) / \(total)" : "\(processed)")
                        .font(.custom("SF Mono", size: 12).bold())
                        .foregroundColor(.white)
                }

                ProgressView(value: total > 0 ? progress : nil)
                    .accentColor(Color(hex: "#3a8fff"))
                    .frame(height: 6)

                Text("↳ \(currentFile)")
                    .font(.custom("SF Mono", size: 10))
                    .foregroundColor(Color(hex: "#555555"))
                    .lineLimit(1)
                    .truncationMode(.middle)
            }

            HStack(spacing: 8) {
                counterCard(value: classified, label: "classified", color: Color(hex: "#3fb950"), borderColor: Color(hex: "#1a2a1a"))
                counterCard(value: review, label: "needs review", color: Color(hex: "#e3a02b"), borderColor: Color(hex: "#2a2010"))
                counterCard(value: errors, label: "errors", color: errors > 0 ? Color(hex: "#f85149") : Color(hex: "#555555"), borderColor: Color(hex: "#1a1a1a"))
            }

            Spacer()
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(hex: "#0d0d0d"))
    }

    private func counterCard(value: Int, label: String, color: Color, borderColor: Color) -> some View {
        VStack(spacing: 4) {
            Text("\(value)")
                .font(.custom("SF Mono", size: 22).bold())
                .foregroundColor(color)
            Text(label)
                .font(.custom("SF Mono", size: 10))
                .foregroundColor(Color(hex: "#555555"))
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background(Color(hex: "#111111"))
        .overlay(RoundedRectangle(cornerRadius: 4).stroke(borderColor, lineWidth: 1))
        .cornerRadius(4)
    }

    private func sectionLabel(_ text: String) -> some View {
        Text(text)
            .font(.custom("SF Mono", size: 9))
            .foregroundColor(Color(hex: "#555555"))
    }
}
```

- [ ] **Step 2: Build and confirm**

`Cmd+B`. Remove the `ScanningView` placeholder stub from `MainPaneView.swift` if you added one.

---

### Task 7: ReviewTableView

**Files:**
- Create: `DocSorter/MainPane/ReviewTableView.swift`

The review table shows all classified files. Each row has: checkbox, filename, category/subcategory, confidence %. Keyboard: `↑`/`↓` navigate, `Space` opens Quick Look, `Enter` toggles detail panel, `X` excludes row. Confident rows (needsReview=false) have green tint and start checked. Review rows (needsReview=true) have amber left border and start unchecked.

- [ ] **Step 1: Create `ReviewTableView.swift`**

```swift
import SwiftUI
import Quartz

struct ReviewTableView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var settings: Settings
    @State private var selectedRowID: UUID?
    @State private var expandedRowID: UUID?
    @State private var isApplying = false
    @State private var applyError: String?

    private var selectedCount: Int { appState.rows.filter(\.isSelected).count }
    private var confidentCount: Int { appState.rows.filter { !$0.needsReview }.count }
    private var reviewCount: Int { appState.rows.filter(\.needsReview).count }

    var body: some View {
        VStack(spacing: 0) {
            // Toolbar
            HStack {
                Button(action: selectAllConfident) {
                    HStack(spacing: 6) {
                        Image(systemName: "checkmark.square")
                            .foregroundColor(Color(hex: "#3a8fff"))
                        Text("Select all confident")
                            .font(.custom("SF Mono", size: 11))
                            .foregroundColor(Color(hex: "#aaaaaa"))
                    }
                }
                .buttonStyle(.plain)

                Spacer()

                Text("\(confidentCount) confident · \(reviewCount) need review")
                    .font(.custom("SF Mono", size: 11))
                    .foregroundColor(Color(hex: "#555555"))

                Spacer()

                Button(action: applySelected) {
                    Text("Apply selected (\(selectedCount))")
                        .font(.custom("SF Mono", size: 12).bold())
                        .foregroundColor(.white)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 6)
                        .background(selectedCount > 0 ? Color(hex: "#3a8fff") : Color(hex: "#1a1a1a"))
                        .cornerRadius(5)
                }
                .buttonStyle(.plain)
                .disabled(selectedCount == 0 || isApplying)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
            .background(Color(hex: "#111111"))

            if let error = applyError {
                Text(error)
                    .font(.custom("SF Mono", size: 11))
                    .foregroundColor(Color(hex: "#f85149"))
                    .padding(.horizontal, 16)
                    .padding(.vertical, 6)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color(hex: "#1a0a0a"))
            }

            // Table
            ScrollView {
                LazyVStack(spacing: 0) {
                    ForEach($appState.rows) { $row in
                        RowView(
                            row: $row,
                            isSelected: selectedRowID == row.id,
                            isExpanded: expandedRowID == row.id
                        )
                        .onTapGesture { selectedRowID = row.id }
                        .background(rowBackground(row: row))
                        .overlay(alignment: .leading) {
                            if row.needsReview {
                                Rectangle()
                                    .fill(Color(hex: "#e3a02b"))
                                    .frame(width: 3)
                            }
                        }

                        if expandedRowID == row.id {
                            DetailPanelView(row: $row) {
                                expandedRowID = nil
                            }
                            .padding(.horizontal, 16)
                            .padding(.vertical, 12)
                            .background(Color(hex: "#0a0a0a"))
                        }

                        Divider().background(Color(hex: "#1a1a1a"))
                    }
                }
            }
            .background(Color(hex: "#0d0d0d"))
        }
        .background(Color(hex: "#0d0d0d"))
        .focusable()
        .onKeyPress(.space) {
            if let id = selectedRowID,
               let row = appState.rows.first(where: { $0.id == id }) {
                quickLook(path: row.sourcePath)
            }
            return .handled
        }
        .onKeyPress(.return) {
            if let id = selectedRowID {
                expandedRowID = expandedRowID == id ? nil : id
            }
            return .handled
        }
        .onKeyPress(KeyEquivalent("x")) {
            if let id = selectedRowID,
               let idx = appState.rows.firstIndex(where: { $0.id == id }) {
                appState.rows[idx].isSelected = false
            }
            return .handled
        }
        .onKeyPress(.upArrow) {
            navigateRow(by: -1)
            return .handled
        }
        .onKeyPress(.downArrow) {
            navigateRow(by: 1)
            return .handled
        }
    }

    private func rowBackground(row: ReviewRow) -> Color {
        if selectedRowID == row.id {
            return Color(hex: "#1a2a3a")
        }
        if !row.needsReview && row.isSelected {
            return Color(hex: "#0d1a0d")
        }
        return Color.clear
    }

    private func selectAllConfident() {
        for i in appState.rows.indices {
            if !appState.rows[i].needsReview {
                appState.rows[i].isSelected = true
            }
        }
    }

    private func navigateRow(by delta: Int) {
        guard !appState.rows.isEmpty else { return }
        if let id = selectedRowID,
           let idx = appState.rows.firstIndex(where: { $0.id == id }) {
            let newIdx = max(0, min(appState.rows.count - 1, idx + delta))
            selectedRowID = appState.rows[newIdx].id
        } else {
            selectedRowID = appState.rows.first?.id
        }
    }

    private func quickLook(path: String) {
        let url = URL(fileURLWithPath: path)
        QLPreviewPanel.shared().makeKeyAndOrderFront(nil)
    }

    private func applySelected() {
        guard let planPath = appState.planPath,
              let outputURL = settings.outputURL else { return }
        isApplying = true
        applyError = nil
        Task {
            do {
                let result = try await PythonBridge.shared.apply(
                    planPath: planPath,
                    outputPath: outputURL.path
                )
                await MainActor.run {
                    appState.applyDone(
                        moved: result.moved,
                        skipped: result.skipped,
                        errors: result.errors,
                        undoPath: result.undoPath
                    )
                }
            } catch {
                await MainActor.run {
                    applyError = "Apply failed: \(error.localizedDescription)"
                    isApplying = false
                }
            }
        }
    }
}

struct RowView: View {
    @Binding var row: ReviewRow
    let isSelected: Bool
    let isExpanded: Bool

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: row.isSelected ? "checkmark.square.fill" : "square")
                .foregroundColor(row.isSelected ? Color(hex: "#3a8fff") : Color(hex: "#555555"))
                .font(.system(size: 14))
                .onTapGesture { row.isSelected.toggle() }

            Text(row.filename)
                .font(.custom("SF Mono", size: 12))
                .foregroundColor(.white)
                .lineLimit(1)
                .truncationMode(.middle)
                .frame(maxWidth: .infinity, alignment: .leading)

            Text("\(row.category) / \(row.subcategory)")
                .font(.custom("SF Mono", size: 11))
                .foregroundColor(Color(hex: "#aaaaaa"))
                .lineLimit(1)
                .frame(width: 200, alignment: .leading)

            Text("\(row.confidence)%")
                .font(.custom("SF Mono", size: 11))
                .foregroundColor(confidenceColor(row.confidence))
                .frame(width: 45, alignment: .trailing)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
    }

    private func confidenceColor(_ c: Int) -> Color {
        if c >= 90 { return Color(hex: "#3fb950") }
        if c >= 70 { return Color(hex: "#e3a02b") }
        return Color(hex: "#f85149")
    }
}
```

- [ ] **Step 2: Create `DetailPanelView.swift`**

Create `DocSorter/MainPane/DetailPanelView.swift`:

```swift
import SwiftUI

struct DetailPanelView: View {
    @Binding var row: ReviewRow
    let onApprove: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(row.aiReason)
                .font(.custom("SF Mono", size: 11).italic())
                .foregroundColor(Color(hex: "#555555"))
                .fixedSize(horizontal: false, vertical: true)

            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 4) {
                    fieldLabel("CATEGORY")
                    TextField("Category", text: $row.category)
                        .textFieldStyle(.plain)
                        .font(.custom("SF Mono", size: 12))
                        .foregroundColor(.white)
                        .padding(6)
                        .background(Color(hex: "#1a1a1a"))
                        .cornerRadius(4)
                }

                VStack(alignment: .leading, spacing: 4) {
                    fieldLabel("SUBCATEGORY")
                    TextField("Subcategory", text: $row.subcategory)
                        .textFieldStyle(.plain)
                        .font(.custom("SF Mono", size: 12))
                        .foregroundColor(.white)
                        .padding(6)
                        .background(Color(hex: "#1a1a1a"))
                        .cornerRadius(4)
                }
            }

            VStack(alignment: .leading, spacing: 4) {
                fieldLabel("FILENAME")
                TextField("Suggested filename", text: $row.suggestedFilename)
                    .textFieldStyle(.plain)
                    .font(.custom("SF Mono", size: 12))
                    .foregroundColor(.white)
                    .padding(6)
                    .background(Color(hex: "#1a1a1a"))
                    .cornerRadius(4)
            }

            Button("Approve") {
                row.isSelected = true
                row.needsReview = false
                onApprove()
            }
            .buttonStyle(PrimaryButtonStyle())
        }
    }

    private func fieldLabel(_ text: String) -> some View {
        Text(text)
            .font(.custom("SF Mono", size: 9))
            .foregroundColor(Color(hex: "#555555"))
    }
}
```

- [ ] **Step 3: Build and confirm**

`Cmd+B`. Remove any `ReviewTableView` placeholder stub from `MainPaneView.swift`.

---

### Task 8: DoneView + AppState CSV Loading

**Files:**
- Create: `DocSorter/MainPane/DoneView.swift`
- Modify: `DocSorter/Model/AppState.swift` — add `loadReviewRows(fromPlanCSV:)` method

When scan finishes, the `done` event carries the plan CSV path. `AppState` loads that CSV and populates `rows`. The review table then shows all classified files.

- [ ] **Step 1: Add CSV loading to `AppState.swift`**

Add this method to `AppState`:

```swift
func loadReviewRows(fromPlanCSV path: String) {
    guard let content = try? String(contentsOfFile: path, encoding: .utf8) else { return }
    let lines = content.components(separatedBy: "\n").filter { !$0.isEmpty }
    guard lines.count > 1 else { return }  // first line is header

    // CSV header (from doc_cleaner/planner.py CSV_COLUMNS):
    // approved,status,original_path,target_path,category,subcategory,
    // document_date,sender,document_type,suggested_filename,confidence,
    // needs_review,reason,file_size,file_hash,modified_time,extractor,model,error
    // Index:  0       1     2             3           4         5
    //         6              7       8              9                  10
    //         11           12
    rows = lines.dropFirst().compactMap { line -> ReviewRow? in
        let cols = parseCSVLine(line)
        guard cols.count >= 13 else { return nil }
        let confidence = Int(cols[10]) ?? 0
        let needsReview = cols[11].lowercased() == "true"
        return ReviewRow(
            filename: URL(fileURLWithPath: cols[2]).lastPathComponent,
            category: cols[4],
            subcategory: cols[5],
            confidence: confidence,
            needsReview: needsReview,
            suggestedFilename: cols[9],
            aiReason: cols[12],
            sourcePath: cols[2]
        )
    }
}

private func parseCSVLine(_ line: String) -> [String] {
    var cols: [String] = []
    var current = ""
    var inQuotes = false
    for char in line {
        if char == "\"" {
            inQuotes.toggle()
        } else if char == "," && !inQuotes {
            cols.append(current)
            current = ""
        } else {
            current.append(char)
        }
    }
    cols.append(current)
    return cols
}
```

- [ ] **Step 2: Call `loadReviewRows` in `finishScan`**

Update `finishScan` in `AppState.swift`:

```swift
func finishScan(event: DoneEvent) {
    planPath = event.plan
    undoPath = event.undo
    loadReviewRows(fromPlanCSV: event.plan)
    phase = .review
}
```

- [ ] **Step 3: Create `DoneView.swift`**

```swift
import SwiftUI

struct DoneView: View {
    @EnvironmentObject var appState: AppState
    let moved: Int
    let skipped: Int
    let errors: Int
    let undoPath: String?
    @State private var isUndoing = false
    @State private var undoError: String?

    var body: some View {
        VStack(spacing: 24) {
            VStack(spacing: 4) {
                Text("✓ Applied")
                    .font(.custom("SF Mono", size: 18).bold())
                    .foregroundColor(Color(hex: "#3fb950"))

                VStack(alignment: .leading, spacing: 6) {
                    resultRow(label: "Moved:", value: "\(moved)", color: .white)
                    resultRow(label: "Skipped:", value: "\(skipped)", color: Color(hex: "#aaaaaa"))
                    resultRow(label: "Errors:", value: "\(errors)", color: errors > 0 ? Color(hex: "#f85149") : Color(hex: "#aaaaaa"))
                }
                .padding(16)
                .background(Color(hex: "#111111"))
                .cornerRadius(6)
            }

            if let error = undoError {
                Text(error)
                    .font(.custom("SF Mono", size: 11))
                    .foregroundColor(Color(hex: "#f85149"))
            }

            HStack(spacing: 12) {
                if let path = undoPath {
                    Button(isUndoing ? "Undoing…" : "Undo") {
                        performUndo(path: path)
                    }
                    .buttonStyle(SecondaryButtonStyle())
                    .disabled(isUndoing)
                }

                Button("Scan again") {
                    appState.reset()
                }
                .buttonStyle(PrimaryButtonStyle())
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(hex: "#0d0d0d"))
    }

    private func resultRow(label: String, value: String, color: Color) -> some View {
        HStack {
            Text(label)
                .font(.custom("SF Mono", size: 12))
                .foregroundColor(Color(hex: "#555555"))
                .frame(width: 70, alignment: .leading)
            Text(value)
                .font(.custom("SF Mono", size: 12).bold())
                .foregroundColor(color)
        }
    }

    private func performUndo(path: String) {
        isUndoing = true
        undoError = nil
        Task {
            do {
                try await PythonBridge.shared.undo(undoManifestPath: path)
                await MainActor.run { appState.reset() }
            } catch {
                await MainActor.run {
                    undoError = "Undo failed: \(error.localizedDescription)"
                    isUndoing = false
                }
            }
        }
    }
}
```

- [ ] **Step 4: Build and confirm**

`Cmd+B`. Expected: builds clean. Remove `DoneView` placeholder stub from `MainPaneView.swift`.

---

### Task 9: Wire Scan Workflow to PythonBridge

**Files:**
- Modify: `DocSorter/Sidebar/SidebarView.swift` — move `runScan()` to trigger `AppState` loading from plan CSV after scan completes

This task verifies the complete flow: scan emits JSONL → SidebarView drives AppState → AppState loads CSV → ReviewTableView shows rows.

- [ ] **Step 1: Verify `runScan` updates AppState correctly**

In `SidebarView.swift`, the `runScan()` method (written in Task 4) already calls `appState.finishScan(event: e)` when the `done` event arrives. `AppState.finishScan` now calls `loadReviewRows`. Check that the `runScan` function passes the `.done` event correctly:

```swift
case .done(let e):
    appState.finishScan(event: e)
```

This is already in place from Task 4. No change needed — this step is verification only.

- [ ] **Step 2: Verify TaxonomySuggestionView triggers scan**

When the user clicks "Add to taxonomy" or "Skip", `TaxonomySuggestionView` calls `appState.startScanning()`. But `runScan()` was started asynchronously and is waiting for this signal. Currently there is a gap: after `showTaxonomySuggestion` returns (when additions are non-empty), `runScanWorkflow()` returns early with `return`. The scan never starts.

Fix `SidebarView.swift` by adding a notification mechanism. Replace the taxonomy-waiting pattern with `AppState`:

Add to `AppState`:
```swift
var taxonomyConfirmed = false

func confirmTaxonomy() {
    taxonomyConfirmed = true
    startScanning()
}
```

Update `TaxonomySuggestionView` to call `appState.confirmTaxonomy()` instead of `appState.startScanning()`.

Update `runScanWorkflow()` in `SidebarView.swift`:
```swift
if !additions.isEmpty {
    // Wait until user confirms
    while appState.phase != .scanning(classified:0, review:0, errors:0, total:0, currentFile:"") {
        // Can't pattern-match scanning directly; use a helper
        if case .scanning = appState.phase { break }
        try? await Task.sleep(nanoseconds: 100_000_000)
    }
}
await runScan()
```

- [ ] **Step 3: Build and confirm**

`Cmd+B`. Expected: builds clean.

---

### Task 10: End-to-End Manual Smoke Test

**Prerequisites:** Python CLI additions plan executed (scan `--output-format jsonl` and `suggest-taxonomy` working). Ollama running with `qwen3.5:9b` model pulled.

- [ ] **Step 1: Run the app**

In Xcode: `Cmd+R`. The app window opens. Expected: Idle state, "Pick an input folder and press Scan."

- [ ] **Step 2: Configure sidebar**

- Input: pick `test_docs/generated` (the 18 test documents)
- Output: pick `sorted/` (create if needed)
- Model: `qwen3.5:9b`
- Confidence: 90

- [ ] **Step 3: Press Scan and watch Preparing state**

Expected: "Found N documents" bar fills instantly, then "Suggesting taxonomy…" bar animates indeterminately.

- [ ] **Step 4: Taxonomy suggestion or skip**

If suggestions appear: click "Add to taxonomy" or "Skip". Expected: transitions to Scanning state.

- [ ] **Step 5: Watch Scanning state**

Expected: progress bar fills file-by-file, current filename updates, counters tick up.

- [ ] **Step 6: Review table**

Expected: review table shows all files, confident rows green-tinted and checked, review rows with amber left border and unchecked.

- [ ] **Step 7: Keyboard navigation**

- Press `↑`/`↓` to navigate rows
- Press `Enter` to open detail panel — shows AI reasoning, editable category/subcategory/filename, Approve button
- Press `Space` on a selected row — Quick Look opens
- Press `X` on a selected row — unchecks it

- [ ] **Step 8: Apply**

Click "Apply selected". Expected: transitions to Done state with moved/skipped/errors summary.

- [ ] **Step 9: Undo**

Click "Undo". Expected: transitions back to Idle (files moved back).

- [ ] **Step 10: Commit**

```bash
git add DocSorter/
git commit -m "feat: DocSorter SwiftUI app initial implementation"
```

---

### Task 11: Verify Plan CSV Loading

**Note:** The column indices in `AppState.loadReviewRows` were derived from `doc_cleaner/planner.py` `CSV_COLUMNS`. This task confirms they are correct with a live plan file.

The column order from `doc_cleaner/planner.py`:
```
0: approved, 1: status, 2: original_path, 3: target_path, 4: category,
5: subcategory, 6: document_date, 7: sender, 8: document_type,
9: suggested_filename, 10: confidence, 11: needs_review, 12: reason, ...
```

- [ ] **Step 1: Run a scan to produce a plan CSV**

```bash
python3 -m doc_cleaner scan \
  --input test_docs/generated \
  --output-root sorted \
  --plan /tmp/test-plan.csv
```

Expected: plan CSV written to `/tmp/test-plan.csv`.

- [ ] **Step 2: Check column order matches**

```bash
head -2 /tmp/test-plan.csv
```

Verify columns 2, 4, 5, 9, 10, 11, 12 match `original_path`, `category`, `subcategory`, `suggested_filename`, `confidence`, `needs_review`, `reason`.

- [ ] **Step 3: Build and re-run smoke test**

`Cmd+B` then `Cmd+R`. Verify review table rows populate and match the plan CSV contents.
