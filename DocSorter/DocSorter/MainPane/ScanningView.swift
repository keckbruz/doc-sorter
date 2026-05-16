import SwiftUI

struct ScanningView: View {
    @EnvironmentObject var appState: AppState

    let classified: Int
    let review: Int
    let errors: Int
    let total: Int
    let currentFile: String

    private var processed: Int { classified + review + errors }
    private var progress: Double {
        guard total > 0 else { return 0 }
        return Double(processed) / Double(total)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            pipelineSection
            currentFileRow
            counterRow
            Spacer()
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(hex: "#0d0d0d"))
    }

    // MARK: - Pipeline

    private var pipelineSection: some View {
        VStack(spacing: 0) {
            pipelineRow(
                icon: "checkmark.circle.fill",
                iconColor: Color(hex: "#3fb950"),
                label: "COUNTED",
                detail: appState.preScanFileCount > 0 ? "\(appState.preScanFileCount) files" : "—",
                progress: 1.0,
                barColor: Color(hex: "#1e4620"),
                done: true
            )
            Divider().background(Color(hex: "#1e1e1e"))
            pipelineRow(
                icon: "checkmark.circle.fill",
                iconColor: Color(hex: "#3fb950"),
                label: "PEEKING",
                detail: appState.peekTotal > 0 ? "\(appState.peekTotal) files" : "done",
                progress: 1.0,
                barColor: Color(hex: "#1e4620"),
                done: true
            )
            Divider().background(Color(hex: "#1e1e1e"))
            pipelineRow(
                icon: "circle.fill",
                iconColor: Color(hex: "#3a8fff"),
                label: "CLASSIFYING",
                detail: total > 0 ? "\(processed) / \(total)" : processed > 0 ? "\(processed)" : "—",
                progress: progress,
                barColor: Color(hex: "#3a8fff"),
                done: false
            )
        }
        .background(Color(hex: "#111111"))
        .cornerRadius(6)
        .overlay(RoundedRectangle(cornerRadius: 6).stroke(Color(hex: "#1e1e1e"), lineWidth: 1))
    }

    private func pipelineRow(
        icon: String,
        iconColor: Color,
        label: String,
        detail: String,
        progress: Double,
        barColor: Color,
        done: Bool
    ) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 11))
                .foregroundColor(iconColor)
                .frame(width: 14)

            Text(label)
                .font(.custom("SF Mono", size: 10))
                .foregroundColor(done ? Color(hex: "#444444") : Color(hex: "#aaaaaa"))
                .frame(width: 84, alignment: .leading)

            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 2).fill(Color(hex: "#1a1a1a"))
                RoundedRectangle(cornerRadius: 2).fill(barColor)
                    .scaleEffect(x: max(0.001, progress), y: 1, anchor: .leading)
                    .animation(.linear(duration: 0.3), value: progress)
            }
            .frame(height: 4)

            Text(detail)
                .font(.custom("SF Mono", size: 10))
                .foregroundColor(done ? Color(hex: "#444444") : .white)
                .frame(width: 72, alignment: .trailing)
                .lineLimit(1)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 11)
    }

    // MARK: - Current file

    private var currentFileRow: some View {
        HStack(spacing: 6) {
            Image(systemName: "arrow.right")
                .font(.system(size: 9))
                .foregroundColor(Color(hex: "#3a8fff"))
            Text(currentFile.isEmpty ? "—" : currentFile)
                .font(.custom("SF Mono", size: 10))
                .foregroundColor(Color(hex: "#555555"))
                .lineLimit(1)
                .truncationMode(.middle)
        }
    }

    // MARK: - Counters

    private var counterRow: some View {
        HStack(spacing: 8) {
            counterCard(value: classified, label: "classified",
                        color: Color(hex: "#3fb950"), border: Color(hex: "#1a2a1a"))
            counterCard(value: review, label: "needs review",
                        color: Color(hex: "#e3a02b"), border: Color(hex: "#2a2010"))
            counterCard(value: errors, label: "errors",
                        color: errors > 0 ? Color(hex: "#f85149") : Color(hex: "#555555"),
                        border: Color(hex: "#1a1a1a"))
        }
    }

    private func counterCard(value: Int, label: String, color: Color, border: Color) -> some View {
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
        .overlay(RoundedRectangle(cornerRadius: 4).stroke(border, lineWidth: 1))
        .cornerRadius(4)
    }
}
