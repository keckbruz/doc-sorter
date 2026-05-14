import Foundation

struct ReviewRow: Identifiable {
    let id: UUID
    var filename: String
    var category: String
    var subcategory: String
    var confidence: Int
    var needsReview: Bool
    var isSelected: Bool
    var suggestedFilename: String
    var aiReason: String
    var sourcePath: String

    init(
        filename: String,
        category: String,
        subcategory: String,
        confidence: Int,
        needsReview: Bool,
        suggestedFilename: String,
        aiReason: String,
        sourcePath: String
    ) {
        self.id = UUID()
        self.filename = filename
        self.category = category
        self.subcategory = subcategory
        self.confidence = confidence
        self.needsReview = needsReview
        self.isSelected = !needsReview
        self.suggestedFilename = suggestedFilename
        self.aiReason = aiReason
        self.sourcePath = sourcePath
    }
}
