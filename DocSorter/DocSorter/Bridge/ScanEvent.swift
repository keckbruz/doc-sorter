import Foundation

// MARK: - Taxonomy streaming events

struct PeekEvent: Codable {
    let event: String
    let file: String
    let done: Int
    let total: Int
}

struct EmbedEvent: Codable {
    let event: String
    let file: String
    let status: String  // "embedded" | "skipped" | "error"
    let done: Int
    let total: Int
}

struct TaxonomyResultEvent: Codable {
    let event: String
    let additions: [String: [String]]
}

enum TaxonomySuggestionEvent {
    case embed(EmbedEvent)
    case peek(PeekEvent)
    case result(TaxonomyResultEvent)
}

// MARK: - Scan streaming events

struct ProgressEvent: Codable {
    let event: String
    let file: String
    let status: String
    let classified: Int
    let review: Int
    let errors: Int
    let total: Int?
}

struct DoneEvent: Codable {
    let event: String
    let plan: String
    let undo: String?
    let classified: Int
    let review: Int
    let errors: Int
}

struct ErrorEvent: Codable {
    let event: String
    let message: String
}

enum ScanEvent {
    case progress(ProgressEvent)
    case done(DoneEvent)
    case error(ErrorEvent)
}
