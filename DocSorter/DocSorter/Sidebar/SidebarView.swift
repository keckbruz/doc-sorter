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

// MARK: - Button styles (shared across views)

struct PrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.custom("SF Mono", size: 12).bold())
            .foregroundColor(.white)
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(Color.accentColor)
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

// MARK: - SetupView

struct SetupView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var settings: Settings
    @StateObject private var viewModel = SidebarViewModel()

    @State private var doctorChecks: [DoctorCheck] = []
    @State private var doctorDone = false

    private var requiredChecksFailed: Bool {
        doctorDone && doctorChecks.contains(where: { $0.required && $0.status == "fail" })
    }

    private var canScan: Bool {
        !settings.lastInputPath.isEmpty && settings.outputURL != nil && !requiredChecksFailed
    }

    private var visibleChecks: [DoctorCheck] {
        doctorChecks.filter { $0.status != "ok" }
    }

    var body: some View {
        ZStack {
            Color(hex: "#0d0d0d").ignoresSafeArea()

            VStack(alignment: .leading, spacing: 20) {
                Text("DOC SORTER")
                    .font(.custom("SF Mono", size: 18).bold())
                    .foregroundColor(.white)
                    .padding(.bottom, 8)

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

                HStack(alignment: .top, spacing: 12) {
                    VStack(alignment: .leading, spacing: 4) {
                        fieldLabel("CONFIDENCE")
                        Picker("", selection: $settings.confidenceThreshold) {
                            ForEach([50, 60, 70, 75, 80, 85, 90, 95], id: \.self) { value in
                                Text("\(value)%").tag(value)
                            }
                        }
                        .labelsHidden()
                        .pickerStyle(.menu)
                        .font(.custom("SF Mono", size: 12))
                    }

                    VStack(alignment: .leading, spacing: 4) {
                        fieldLabel("MODEL")
                        TextField("qwen3:8b", text: $settings.modelName)
                            .textFieldStyle(.plain)
                            .font(.custom("SF Mono", size: 11))
                            .foregroundColor(Color(hex: "#666666"))
                            .padding(.horizontal, 8)
                            .padding(.vertical, 6)
                            .background(Color(hex: "#0f0f0f"))
                            .cornerRadius(4)
                            .overlay(RoundedRectangle(cornerRadius: 4)
                                .stroke(Color(hex: "#222222"), lineWidth: 1))
                    }
                    .frame(maxWidth: .infinity)
                }

                if let error = viewModel.errorMessage {
                    Text(error)
                        .font(.custom("SF Mono", size: 11))
                        .foregroundColor(Color(hex: "#f85149"))
                        .fixedSize(horizontal: false, vertical: true)
                }

                Button(action: startScan) {
                    Text("SCAN")
                        .font(.custom("SF Mono", size: 13).bold())
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
                        .background(canScan ? Color.accentColor : Color(hex: "#1a1a1a"))
                        .foregroundColor(canScan ? .white : Color(hex: "#555555"))
                        .cornerRadius(6)
                }
                .buttonStyle(.plain)
                .disabled(!canScan)
                .keyboardShortcut(.return, modifiers: .command)
                .padding(.top, 4)

                if !doctorDone {
                    HStack(spacing: 6) {
                        ProgressView().scaleEffect(0.5).frame(width: 12, height: 12)
                        Text("Checking dependencies…")
                            .font(.custom("SF Mono", size: 10))
                            .foregroundColor(Color(hex: "#444444"))
                    }
                } else if !visibleChecks.isEmpty {
                    doctorStrip(visibleChecks)
                }
            }
            .frame(width: 360)
        }
        .onAppear {
            NSApp.keyWindow?.makeFirstResponder(nil)
        }
        .task {
            let checks = await PythonBridge.shared.doctor()
            doctorChecks = checks
            doctorDone = true
        }
    }

    // MARK: - Dependency strip

    private func doctorStrip(_ checks: [DoctorCheck]) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach(checks) { check in
                HStack(alignment: .top, spacing: 7) {
                    Image(systemName: check.status == "fail" ? "xmark.circle.fill" : "exclamationmark.triangle.fill")
                        .font(.system(size: 9))
                        .foregroundColor(check.status == "fail" ? Color(hex: "#f85149") : Color(hex: "#e3a84d"))
                        .frame(width: 12)
                        .padding(.top, 1)
                    VStack(alignment: .leading, spacing: 1) {
                        Text(check.name)
                            .font(.custom("SF Mono", size: 10).bold())
                            .foregroundColor(check.status == "fail" ? Color(hex: "#f85149") : Color(hex: "#e3a84d"))
                        Text(check.detail)
                            .font(.custom("SF Mono", size: 9))
                            .foregroundColor(Color(hex: "#666666"))
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .padding(.vertical, 5)
                .padding(.horizontal, 10)
                if check.id != checks.last?.id {
                    Divider().background(Color(hex: "#1e1e1e"))
                }
            }
        }
        .background(Color(hex: "#111111"))
        .cornerRadius(6)
        .overlay(RoundedRectangle(cornerRadius: 6).stroke(
            checks.contains(where: { $0.status == "fail" })
                ? Color(hex: "#f85149").opacity(0.3)
                : Color(hex: "#e3a84d").opacity(0.3),
            lineWidth: 1
        ))
    }

    // MARK: - Subviews

    private func folderRow(label: String, path: String, action: @escaping () -> Void) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            fieldLabel(label)
            Button(action: action) {
                HStack(spacing: 6) {
                    Image(systemName: path.isEmpty ? "folder.badge.plus" : "folder.fill")
                        .font(.system(size: 11))
                        .foregroundColor(path.isEmpty ? Color(hex: "#555555") : Color.accentColor)
                    Text(path.isEmpty
                         ? "Choose folder…"
                         : URL(fileURLWithPath: path).lastPathComponent)
                        .font(.custom("SF Mono", size: 12))
                        .foregroundColor(path.isEmpty ? Color(hex: "#666666") : .white)
                        .lineLimit(1)
                        .truncationMode(.middle)
                    Spacer()
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 9)
                .background(Color(hex: "#161616"))
                .cornerRadius(5)
                .overlay(
                    RoundedRectangle(cornerRadius: 5)
                        .stroke(
                            path.isEmpty ? Color(hex: "#2a2a2a") : Color.accentColor.opacity(0.4),
                            lineWidth: 1
                        )
                )
            }
            .buttonStyle(.plain)
        }
    }

    private func fieldLabel(_ text: String) -> some View {
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

        Task { await runScanWorkflow() }
    }

    private func runScanWorkflow() async {
        let inputPath = settings.lastInputPath
        guard let outputURL = settings.outputURL else { return }
        let outputPath = outputURL.path

        let count = viewModel.countFiles(at: URL(fileURLWithPath: inputPath))
        await MainActor.run { appState.updateFileCount(count) }

        do {
            var additions: [String: [String]] = [:]
            let stream = PythonBridge.shared.suggestTaxonomy(
                inputPath: inputPath,
                outputPath: outputPath,
                model: settings.modelName
            )
            for try await event in stream {
                switch event {
                case .embed(let e):
                    await MainActor.run { appState.updateEmbed(done: e.done, total: e.total) }
                case .peek(let e):
                    await MainActor.run { appState.updatePeek(done: e.done, total: e.total) }
                case .result(let e):
                    additions = e.additions
                }
            }
            await MainActor.run { appState.showTaxonomySuggestion(additions) }

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
        while !appState.taxonomyConfirmed {
            try? await Task.sleep(nanoseconds: 100_000_000)
        }
    }

    private func runScan() async {
        let inputPath = settings.lastInputPath
        guard let outputURL = settings.outputURL else { return }
        let outputPath = outputURL.path
        let planPath = outputURL.appendingPathComponent(".doc-sorter-plan.csv").path

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
                        withAnimation(.easeOut(duration: 0.2)) {
                            appState.updateScan(event: e)
                        }
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
}
