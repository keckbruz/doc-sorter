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

    var preScanFileCount: Int = 0
    @Published var peekDone: Int = 0
    @Published var peekTotal: Int = 0

    func startPreparing() {
        phase = .preparing(fileCount: nil, isSuggestingTaxonomy: false)
    }

    func updateFileCount(_ count: Int) {
        preScanFileCount = count
        phase = .preparing(fileCount: count, isSuggestingTaxonomy: true)
    }

    func updatePeek(done: Int, total: Int) {
        peekDone = done
        peekTotal = total
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
        let total = event.total ?? (peekTotal > 0 ? peekTotal : preScanFileCount)
        phase = .scanning(
            classified: event.classified,
            review: event.review,
            errors: event.errors,
            total: total,
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
        peekDone = 0
        peekTotal = 0
        preScanFileCount = 0
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

    // MARK: - CSV Write-back

    func writePlanEdits(toPlanCSV path: String) {
        guard let content = try? String(contentsOfFile: path, encoding: .utf8) else { return }
        let lines = content.components(separatedBy: "\n")
        guard lines.count > 1 else { return }

        let header = lines[0]
        var updated = [header]

        // Build a lookup: sourcePath → ReviewRow
        let lookup = Dictionary(uniqueKeysWithValues: rows.map { ($0.sourcePath, $0) })

        for line in lines.dropFirst() {
            guard !line.isEmpty else { continue }
            var cols = parseCSVLine(line)
            guard cols.count >= 13 else { updated.append(line); continue }

            if let row = lookup[cols[2]] {
                cols[0] = row.isSelected ? "true" : "false"
                cols[4] = row.category
                cols[5] = row.subcategory
                cols[9] = row.suggestedFilename
            }
            updated.append(cols.map { csvEscape($0) }.joined(separator: ","))
        }

        try? updated.joined(separator: "\n").write(toFile: path, atomically: true, encoding: .utf8)
    }

    private func csvEscape(_ value: String) -> String {
        if value.contains(",") || value.contains("\"") || value.contains("\n") {
            return "\"" + value.replacingOccurrences(of: "\"", with: "\"\"") + "\""
        }
        return value
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
