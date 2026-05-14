import SwiftUI

struct ScanningView: View {
    let classified: Int
    let review: Int
    let errors: Int
    let total: Int
    let currentFile: String

    var body: some View {
        Text("Scanning… \(classified) classified")
            .font(.custom("SF Mono", size: 14))
            .foregroundColor(Color(hex: "#aaaaaa"))
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(hex: "#0d0d0d"))
    }
}
