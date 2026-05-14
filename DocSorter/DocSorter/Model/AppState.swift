import Foundation

enum AppPhase: Equatable {
    case idle
    case preparing(fileCount: Int?, isSuggestingTaxonomy: Bool)
    case taxonomySuggestion(additions: [String: [String]])
    case scanning(classified: Int, review: Int, errors: Int, total: Int, currentFile: String)
    case review
    case done(moved: Int, skipped: Int, errors: Int, undoPath: String?)
    case error(message: String)
}

// AppPhase.taxonomySuggestion has a Dictionary which is not Equatable by default — provide conformance manually
extension AppPhase {
    static func == (lhs: AppPhase, rhs: AppPhase) -> Bool {
        switch (lhs, rhs) {
        case (.idle, .idle): return true
        case (.review, .review): return true
        case (.preparing(let a, let b), .preparing(let c, let d)): return a == c && b == d
        case (.taxonomySuggestion(let a), .taxonomySuggestion(let b)): return a == b
        case (.scanning(let a1, let a2, let a3, let a4, let a5),
              .scanning(let b1, let b2, let b3, let b4, let b5)):
            return a1 == b1 && a2 == b2 && a3 == b3 && a4 == b4 && a5 == b5
        case (.done(let a1, let a2, let a3, let a4), .done(let b1, let b2, let b3, let b4)):
            return a1 == b1 && a2 == b2 && a3 == b3 && a4 == b4
        case (.error(let a), .error(let b)): return a == b
        default: return false
        }
    }
}

@MainActor
final class AppState: ObservableObject {
    @Published var phase: AppPhase = .idle
    @Published var rows: [ReviewRow] = []
    @Published var planPath: String?
    @Published var undoPath: String?
    @Published var taxonomyConfirmed: Bool = false

    func startPreparing() {
        phase = .preparing(fileCount: nil, isSuggestingTaxonomy: false)
    }

    func updateFileCount(_ count: Int) {
        phase = .preparing(fileCount: count, isSuggestingTaxonomy: true)
    }

    func showTaxonomySuggestion(_ additions: [String: [String]]) {
        if additions.isEmpty {
            startScanning()
        } else {
            phase = .taxonomySuggestion(additions: additions)
        }
    }

    func confirmTaxonomy() {
        taxonomyConfirmed = true
        startScanning()
    }

    func startScanning() {
        phase = .scanning(classified: 0, review: 0, errors: 0, total: 0, currentFile: "")
    }

    func updateScan(event: ProgressEvent) {
        phase = .scanning(
            classified: event.classified,
            review: event.review,
            errors: event.errors,
            total: 0,
            currentFile: event.file
        )
    }

    func finishScan(event: DoneEvent) {
        planPath = event.plan
        undoPath = event.undo
        loadReviewRows(fromPlanCSV: event.plan)
        phase = .review
    }

    func applyDone(moved: Int, skipped: Int, errors: Int, undoPath: String?) {
        self.undoPath = undoPath
        phase = .done(moved: moved, skipped: skipped, errors: errors, undoPath: undoPath)
    }

    func showError(_ message: String) {
        phase = .error(message: message)
    }

    func reset() {
        phase = .idle
        rows = []
        planPath = nil
        undoPath = nil
        taxonomyConfirmed = false
    }

    // MARK: - CSV Loading

    func loadReviewRows(fromPlanCSV path: String) {
        guard let content = try? String(contentsOfFile: path, encoding: .utf8) else { return }
        let lines = content.components(separatedBy: "\n").filter { !$0.isEmpty }
        guard lines.count > 1 else { return }

        // CSV column order from doc_cleaner/planner.py CSV_COLUMNS:
        // 0:approved  1:status  2:original_path  3:target_path  4:category
        // 5:subcategory  6:document_date  7:sender  8:document_type
        // 9:suggested_filename  10:confidence  11:needs_review  12:reason  ...
        rows = lines.dropFirst().compactMap { line -> ReviewRow? in
            let cols = parseCSVLine(line)
            guard cols.count >= 13 else { return nil }
            let confidence = Int(cols[10]) ?? 0
            let needsReview = cols[11].lowercased() == "true"
            return ReviewRow(
                filename: URL(fileURLWithPath: cols[2]).lastPathComponent,
                category: cols[4],
                subcategory: cols[5],
                confidence: confidence,
                needsReview: needsReview,
                suggestedFilename: cols[9],
                aiReason: cols[12],
                sourcePath: cols[2]
            )
        }
    }

    private func parseCSVLine(_ line: String) -> [String] {
        var cols: [String] = []
        var current = ""
        var inQuotes = false
        for char in line {
            if char == "\"" {
                inQuotes.toggle()
            } else if char == "," && !inQuotes {
                cols.append(current)
                current = ""
            } else {
                current.append(char)
            }
        }
        cols.append(current)
        return cols
    }
}
