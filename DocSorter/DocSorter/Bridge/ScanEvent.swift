import Foundation

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
