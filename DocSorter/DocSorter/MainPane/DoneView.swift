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
            VStack(spacing: 16) {
                Text("✓ Applied")
                    .font(.custom("SF Mono", size: 20).bold())
                    .foregroundColor(Color(hex: "#3fb950"))

                VStack(alignment: .leading, spacing: 8) {
                    resultRow(label: "Moved:", value: "\(moved)", color: .white)
                    resultRow(label: "Skipped:", value: "\(skipped)", color: Color(hex: "#aaaaaa"))
                    resultRow(
                        label: "Errors:",
                        value: "\(errors)",
                        color: errors > 0 ? Color(hex: "#f85149") : Color(hex: "#aaaaaa")
                    )
                }
                .padding(16)
                .background(Color(hex: "#111111"))
                .cornerRadius(6)
            }

            if let error = undoError {
                Text(error)
                    .font(.custom("SF Mono", size: 11))
                    .foregroundColor(Color(hex: "#f85149"))
                    .multilineTextAlignment(.center)
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
