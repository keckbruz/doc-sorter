import SwiftUI

struct DetailPanelView: View {
    @Binding var row: ReviewRow
    let onApprove: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(row.aiReason.isEmpty ? "No reasoning provided." : row.aiReason)
                .font(.system(size: 12).italic())
                .foregroundColor(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 4) {
                    fieldLabel("CATEGORY")
                    TextField("Category", text: $row.category)
                        .textFieldStyle(.plain)
                        .font(.custom("SF Mono", size: 12))
                        .foregroundColor(.white)
                        .padding(6)
                        .background(Color(hex: "#1a1a1a"))
                        .cornerRadius(4)
                }

                VStack(alignment: .leading, spacing: 4) {
                    fieldLabel("SUBCATEGORY")
                    TextField("Subcategory", text: $row.subcategory)
                        .textFieldStyle(.plain)
                        .font(.custom("SF Mono", size: 12))
                        .foregroundColor(.white)
                        .padding(6)
                        .background(Color(hex: "#1a1a1a"))
                        .cornerRadius(4)
                }
            }

            VStack(alignment: .leading, spacing: 4) {
                fieldLabel("FILENAME")
                TextField("Suggested filename", text: $row.suggestedFilename)
                    .textFieldStyle(.plain)
                    .font(.custom("SF Mono", size: 12))
                    .foregroundColor(.white)
                    .padding(6)
                    .background(Color(hex: "#1a1a1a"))
                    .cornerRadius(4)
            }

            Button("Approve") {
                row.isSelected = true
                row.needsReview = false
                onApprove()
            }
            .buttonStyle(PrimaryButtonStyle())
        }
    }

    private func fieldLabel(_ text: String) -> some View {
        Text(text)
            .font(.custom("SF Mono", size: 9))
            .foregroundColor(Color(hex: "#555555"))
    }
}
