import SwiftUI

struct ErrorView: View {
    @EnvironmentObject var appState: AppState
    let message: String

    var body: some View {
        VStack(spacing: 16) {
            Text(message)
                .font(.custom("SF Mono", size: 13))
                .foregroundColor(Color(hex: "#f85149"))
                .multilineTextAlignment(.center)
                .padding()

            if message.lowercased().contains("ollama") {
                Button("Start Ollama") {
                    if let url = URL(string: "ollama://") {
                        NSWorkspace.shared.open(url)
                    }
                }
                .buttonStyle(PrimaryButtonStyle())
            }

            Button("Reset") {
                appState.reset()
            }
            .buttonStyle(SecondaryButtonStyle())
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(hex: "#0d0d0d"))
    }
}
