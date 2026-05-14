import SwiftUI

struct ScanningView: View {
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

                if total > 0 {
                    ProgressView(value: progress)
                        .accentColor(Color(hex: "#3a8fff"))
                } else {
                    ProgressView()
                        .progressViewStyle(.linear)
                        .accentColor(Color(hex: "#3a8fff"))
                }

                Text("↳ \(currentFile.isEmpty ? "—" : currentFile)")
                    .font(.custom("SF Mono", size: 10))
                    .foregroundColor(Color(hex: "#555555"))
                    .lineLimit(1)
                    .truncationMode(.middle)
            }

            HStack(spacing: 8) {
                counterCard(
                    value: classified,
                    label: "classified",
                    color: Color(hex: "#3fb950"),
                    borderColor: Color(hex: "#1a2a1a")
                )
                counterCard(
                    value: review,
                    label: "needs review",
                    color: Color(hex: "#e3a02b"),
                    borderColor: Color(hex: "#2a2010")
                )
                counterCard(
                    value: errors,
                    label: "errors",
                    color: errors > 0 ? Color(hex: "#f85149") : Color(hex: "#555555"),
                    borderColor: Color(hex: "#1a1a1a")
                )
            }

            Spacer()
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(hex: "#0d0d0d"))
    }

    private func counterCard(
        value: Int,
        label: String,
        color: Color,
        borderColor: Color
    ) -> some View {
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
        .overlay(
            RoundedRectangle(cornerRadius: 4)
                .stroke(borderColor, lineWidth: 1)
        )
        .cornerRadius(4)
    }

    private func sectionLabel(_ text: String) -> some View {
        Text(text)
            .font(.custom("SF Mono", size: 9))
            .foregroundColor(Color(hex: "#555555"))
    }
}
