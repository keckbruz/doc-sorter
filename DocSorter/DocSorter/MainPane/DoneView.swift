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
        VStack(spacing: 28) {
            VStack(spacing: 6) {
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 40))
                    .foregroundColor(Color(hex: "#3fb950"))
                Text("Done")
                    .font(.system(size: 22, weight: .semibold))
                    .foregroundColor(.primary)
            }

            VStack(spacing: 0) {
                resultRow(icon: "arrow.right.circle", label: "Moved", value: "\(moved)", color: .primary)
                Divider().background(Color(hex: "#1e1e1e"))
                resultRow(icon: "forward.circle", label: "Skipped", value: "\(skipped)", color: .secondary)
                if errors > 0 {
                    Divider().background(Color(hex: "#1e1e1e"))
                    resultRow(icon: "exclamationmark.circle", label: "Errors", value: "\(errors)", color: Color(hex: "#f85149"))
                }
            }
            .background(Color(hex: "#111111"))
            .cornerRadius(8)
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color(hex: "#222222"), lineWidth: 1))
            .frame(width: 280)

            if let error = undoError {
                Text(error)
                    .font(.system(size: 11))
                    .foregroundColor(Color(hex: "#f85149"))
                    .multilineTextAlignment(.center)
            }

            HStack(spacing: 10) {
                if let path = undoPath {
                    Button(isUndoing ? "Undoing…" : "Undo") {
                        performUndo(path: path)
                    }
                    .buttonStyle(SecondaryButtonStyle())
                    .disabled(isUndoing)
                }
                Button("Scan Again") { appState.reset() }
                    .buttonStyle(PrimaryButtonStyle())
                    .keyboardShortcut(.return, modifiers: .command)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(hex: "#0d0d0d"))
    }

    private func resultRow(icon: String, label: String, value: String, color: Color) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .font(.system(size: 13))
                .foregroundColor(color)
                .frame(width: 20)
            Text(label)
                .font(.system(size: 13))
                .foregroundColor(.secondary)
            Spacer()
            Text(value)
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(color)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 11)
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
