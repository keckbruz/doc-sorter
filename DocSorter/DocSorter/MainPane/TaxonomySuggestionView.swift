import SwiftUI

struct TaxonomySuggestionView: View {
    @EnvironmentObject var appState: AppState
    let additions: [String: [String]]

    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            Text("Suggested additions to taxonomy:")
                .font(.custom("SF Mono", size: 13))
                .foregroundColor(Color(hex: "#aaaaaa"))

            VStack(alignment: .leading, spacing: 6) {
                ForEach(additions.sorted(by: { $0.key < $1.key }), id: \.key) { cat, subs in
                    if subs.isEmpty {
                        additionRow("+ \(cat)")
                    } else {
                        ForEach(subs, id: \.self) { sub in
                            additionRow("+ \(cat) / \(sub)")
                        }
                    }
                }
            }
            .padding(16)
            .background(Color(hex: "#111111"))
            .cornerRadius(6)

            HStack(spacing: 12) {
                Button("Add to taxonomy") {
                    appState.confirmTaxonomy()
                }
                .buttonStyle(PrimaryButtonStyle())

                Button("Skip") {
                    appState.confirmTaxonomy()
                }
                .buttonStyle(SecondaryButtonStyle())
            }

            Spacer()
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(hex: "#0d0d0d"))
    }

    private func additionRow(_ text: String) -> some View {
        Text(text)
            .font(.custom("SF Mono", size: 12))
            .foregroundColor(Color(hex: "#3fb950"))
    }
}
