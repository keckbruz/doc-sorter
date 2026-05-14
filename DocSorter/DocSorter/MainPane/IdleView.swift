import SwiftUI

struct IdleView: View {
    var body: some View {
        VStack {
            Text("Pick an input folder and press Scan.")
                .font(.custom("SF Mono", size: 14))
                .foregroundColor(Color(hex: "#555555"))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(hex: "#0d0d0d"))
    }
}
