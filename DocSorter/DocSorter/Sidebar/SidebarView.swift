import SwiftUI

// MARK: - Hex color helper (used across all views)

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

// MARK: - Button styles (shared across MainPane views)

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

// MARK: - SidebarView

struct SidebarView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var settings: Settings
    @StateObject private var viewModel = SidebarViewModel()

    private var isScanning: Bool {
        switch appState.phase {
        case .preparing, .scanning: return true
        default: return false
        }
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

            folderRow(
                label: "OUTPUT",
                path: settings.outputURL?.path ?? ""
            ) {
                viewModel.pickFolder { url in
                    settings.setOutputURL(url)
                }
            }

            VStack(alignment: .leading, spacing: 4) {
                sidebarLabel("MODEL")
                TextField("qwen3.5:9b", text: $settings.modelName)
                    .textFieldStyle(.plain)
                    .font(.custom("SF Mono", size: 12))
                    .foregroundColor(.white)
                    .padding(6)
                    .background(Color(hex: "#111111"))
                    .cornerRadius(4)
            }

            VStack(alignment: .leading, spacing: 4) {
                sidebarLabel("CONFIDENCE")
                HStack {
                    Text("\(settings.confidenceThreshold)%")
                        .font(.custom("SF Mono", size: 12))
                        .foregroundColor(.white)
                        .frame(width: 42, alignment: .leading)
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

    // MARK: - Subviews

    private func folderRow(label: String, path: String, action: @escaping () -> Void) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            sidebarLabel(label)
            Button(action: action) {
                HStack {
                    Text(path.isEmpty
                         ? "Choose…"
                         : URL(fileURLWithPath: path).lastPathComponent)
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

    private func sidebarLabel(_ text: String) -> some View {
        Text(text)
            .font(.custom("SF Mono", size: 9))
            .foregroundColor(Color(hex: "#555555"))
    }

    // MARK: - Scan workflow

    private func startScan() {
        let error = viewModel.validate(
            inputPath: settings.lastInputPath,
            outputURL: settings.outputURL
        )
        viewModel.errorMessage = error
        guard error == nil else { return }

        appState.reset()
        appState.startPreparing()

        Task {
            await runScanWorkflow()
        }
    }

    private func runScanWorkflow() async {
        let inputPath = settings.lastInputPath
        guard let outputURL = settings.outputURL else { return }
        let outputPath = outputURL.path

        // Step 1: count files (fast, local I/O)
        let count = viewModel.countFiles(at: URL(fileURLWithPath: inputPath))
        await MainActor.run { appState.updateFileCount(count) }

        // Step 2: suggest taxonomy (LLM call)
        do {
            let additions = try await PythonBridge.shared.suggestTaxonomy(
                inputPath: inputPath,
                outputPath: outputPath,
                model: settings.modelName
            )
            await MainActor.run { appState.showTaxonomySuggestion(additions) }

            // If non-empty suggestions: wait for user to confirm in TaxonomySuggestionView
            if !additions.isEmpty {
                await waitForTaxonomyConfirmation()
            }
        } catch {
            await MainActor.run {
                appState.showError("Taxonomy suggestion failed: \(error.localizedDescription)")
            }
            return
        }

        await runScan()
    }

    private func waitForTaxonomyConfirmation() async {
        // Poll until TaxonomySuggestionView sets appState.taxonomyConfirmed via confirmTaxonomy()
        while await !appState.taxonomyConfirmed {
            try? await Task.sleep(nanoseconds: 100_000_000)
        }
    }

    private func runScan() async {
        let inputPath = settings.lastInputPath
        guard let outputURL = settings.outputURL else { return }
        let outputPath = outputURL.path
        let planPath = outputURL
            .appendingPathComponent(".doc-sorter-plan.csv").path

        let stream = PythonBridge.shared.scan(
            inputPath: inputPath,
            outputPath: outputPath,
            planPath: planPath,
            model: settings.modelName,
            confidenceThreshold: settings.confidenceThreshold
        )

        do {
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
            await MainActor.run {
                appState.showError(error.localizedDescription)
            }
        }
    }
}
