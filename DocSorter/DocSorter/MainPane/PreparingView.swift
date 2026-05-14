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
                } else {
                    Text("Counting files…")
                        .font(.custom("SF Mono", size: 13))
                        .foregroundColor(Color(hex: "#aaaaaa"))
                    ProgressView()
                        .progressViewStyle(.linear)
                        .accentColor(Color(hex: "#3a8fff"))
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
