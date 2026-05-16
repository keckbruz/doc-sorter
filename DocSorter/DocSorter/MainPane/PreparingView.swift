import SwiftUI

struct PreparingView: View {
    @EnvironmentObject var appState: AppState
    let fileCount: Int?
    let isSuggestingTaxonomy: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            pipelineRow(
                icon: fileCount != nil ? "checkmark.circle.fill" : "circle.fill",
                iconColor: fileCount != nil ? Color(hex: "#3fb950") : Color(hex: "#3a8fff"),
                label: "COUNTED",
                detail: fileCount.map { "\($0) files" } ?? "—",
                progress: fileCount != nil ? 1.0 : 0.0,
                barColor: fileCount != nil ? Color(hex: "#1e4620") : Color(hex: "#3a8fff"),
                done: fileCount != nil
            )
            Divider().background(Color(hex: "#1e1e1e"))
            pipelineRow(
                icon: isSuggestingTaxonomy ? "circle.fill" : "circle",
                iconColor: isSuggestingTaxonomy ? Color(hex: "#3a8fff") : Color(hex: "#333333"),
                label: "PEEKING",
                detail: peekDetail,
                progress: peekProgress,
                barColor: Color(hex: "#3a8fff"),
                done: false
            )
            Divider().background(Color(hex: "#1e1e1e"))
            pipelineRow(
                icon: "circle",
                iconColor: Color(hex: "#333333"),
                label: "CLASSIFYING",
                detail: "—",
                progress: 0.0,
                barColor: Color(hex: "#3a8fff"),
                done: false
            )
        }
        .background(Color(hex: "#111111"))
        .cornerRadius(6)
        .overlay(RoundedRectangle(cornerRadius: 6).stroke(Color(hex: "#1e1e1e"), lineWidth: 1))
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(Color(hex: "#0d0d0d"))
    }

    private var peekDetail: String {
        guard appState.peekTotal > 0 else { return isSuggestingTaxonomy ? "starting…" : "—" }
        return "\(appState.peekDone) / \(appState.peekTotal)"
    }

    private var peekProgress: Double {
        guard appState.peekTotal > 0 else { return 0 }
        return Double(appState.peekDone) / Double(appState.peekTotal)
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
}
