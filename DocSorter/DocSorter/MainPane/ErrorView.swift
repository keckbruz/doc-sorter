import SwiftUI

struct ErrorView: View {
    @EnvironmentObject var appState: AppState
    let message: String

    @State private var showDetails = false

    private var headline: String {
        message
            .components(separatedBy: "\n")
            .first { !$0.trimmingCharacters(in: .whitespaces).isEmpty } ?? message
    }

    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 36))
                .foregroundColor(Color(hex: "#e3a02b"))

            Text(headline)
                .font(.system(size: 13))
                .foregroundColor(.primary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)

            if message != headline {
                DisclosureGroup("Show details", isExpanded: $showDetails) {
                    ScrollView {
                        Text(message)
                            .font(.custom("SF Mono", size: 10))
                            .foregroundColor(Color(hex: "#f85149"))
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(8)
                    }
                    .frame(maxHeight: 180)
                    .background(Color(hex: "#111111"))
                    .cornerRadius(6)
                }
                .font(.system(size: 12))
                .foregroundColor(.secondary)
                .padding(.horizontal, 32)
            }

            HStack(spacing: 10) {
                if message.lowercased().contains("connection refused") ||
                   message.lowercased().contains("ollama is not running") {
                    Button("Start Ollama") {
                        let p = Process()
                        p.executableURL = URL(fileURLWithPath: "/usr/bin/open")
                        p.arguments = ["-a", "Ollama"]
                        try? p.run()
                    }
                    .buttonStyle(SecondaryButtonStyle())
                }
                Button("New Scan") { appState.reset() }
                    .buttonStyle(PrimaryButtonStyle())
                    .keyboardShortcut(.return, modifiers: .command)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(hex: "#0d0d0d"))
    }
}
