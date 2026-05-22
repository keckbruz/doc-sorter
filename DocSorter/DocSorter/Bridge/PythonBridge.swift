import Foundation

enum BridgeError: Error, LocalizedError {
    case pythonNotFound
    case processError(String)

    var errorDescription: String? {
        switch self {
        case .pythonNotFound:
            return "python3 not found. Install Python 3 from python.org."
        case .processError(let msg):
            return msg
        }
    }
}

struct ApplyResult {
    let moved: Int
    let skipped: Int
    let errors: Int
    let undoPath: String?
}

final class PythonBridge {

    static let shared = PythonBridge()
    private init() {}

    // MARK: - Environment

    private func enrichedEnvironment() -> [String: String] {
        var env = ProcessInfo.processInfo.environment
        let extras = "/opt/homebrew/bin:/usr/local/bin"
        if let existing = env["PATH"] {
            env["PATH"] = "\(extras):\(existing)"
        } else {
            env["PATH"] = extras
        }
        return env
    }

    // MARK: - Python path resolution

    private func python3Path() throws -> String {
        let candidates = [
            "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",
            "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3",
            "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3",
            "/Library/Frameworks/Python.framework/Versions/3.10/bin/python3",
            "/opt/homebrew/bin/python3",
            "/usr/local/bin/python3",
            "/usr/bin/python3",
        ]
        for path in candidates {
            if FileManager.default.fileExists(atPath: path) { return path }
        }
        // Try resolving via login shell so user's PATH is honoured
        let shell = ProcessInfo.processInfo.environment["SHELL"] ?? "/bin/zsh"
        let which = Process()
        which.executableURL = URL(fileURLWithPath: shell)
        which.arguments = ["-lc", "which python3"]
        let pipe = Pipe()
        which.standardOutput = pipe
        which.standardError = Pipe()
        try? which.run()
        which.waitUntilExit()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let path = String(data: data, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        if !path.isEmpty && FileManager.default.fileExists(atPath: path) { return path }
        throw BridgeError.pythonNotFound
    }

    // MARK: - suggest-taxonomy (streaming)

    func suggestTaxonomy(
        inputPath: String,
        outputPath: String,
        model: String
    ) -> AsyncThrowingStream<TaxonomySuggestionEvent, Error> {
        AsyncThrowingStream { continuation in
            DispatchQueue(label: "com.docsorter.taxonomy").async {
                do {
                    let python = try self.python3Path()
                    let process = Process()
                    process.executableURL = URL(fileURLWithPath: python)
                    process.arguments = [
                        "-u", "-m", "doc_cleaner",
                        "suggest-taxonomy",
                        "--input", inputPath,
                        "--output-root", outputPath,
                        "--model", model,
                        "--output-format", "jsonl",
                        "--embed-sparse",
                        "--ocr-language", "deu+eng",
                    ]
                    let stdout = Pipe()
                    let stderr = Pipe()
                    process.environment = self.enrichedEnvironment()
                    process.standardOutput = stdout
                    process.standardError = stderr
                    try process.run()

                    let handle = stdout.fileHandleForReading
                    var buffer = Data()
                    while true {
                        let chunk = handle.availableData
                        if chunk.isEmpty { break }
                        buffer.append(chunk)
                        while let nlIdx = buffer.firstIndex(of: UInt8(ascii: "\n")) {
                            let lineData = Data(buffer[buffer.startIndex..<nlIdx])
                            buffer.removeSubrange(buffer.startIndex...nlIdx)
                            guard let event = Self.decodeTaxonomyEvent(lineData) else { continue }
                            continuation.yield(event)
                        }
                    }

                    process.waitUntilExit()
                    if process.terminationStatus != 0 {
                        let errData = stderr.fileHandleForReading.readDataToEndOfFile()
                        let msg = String(data: errData, encoding: .utf8)?
                            .trimmingCharacters(in: .whitespacesAndNewlines)
                            ?? "exit code \(process.terminationStatus)"
                        continuation.finish(throwing: BridgeError.processError("Taxonomy failed: \(msg)"))
                    } else {
                        continuation.finish()
                    }
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }

    // MARK: - scan (JSONL stream)

    func scan(
        inputPath: String,
        outputPath: String,
        planPath: String,
        model: String,
        confidenceThreshold: Int,
        ollamaHost: String = "http://127.0.0.1:11434"
    ) -> AsyncThrowingStream<ScanEvent, Error> {
        AsyncThrowingStream { continuation in
            DispatchQueue(label: "com.docsorter.scan").async {
                do {
                    let python = try self.python3Path()
                    let process = Process()
                    process.executableURL = URL(fileURLWithPath: python)
                    let jsonlPath = planPath.replacingOccurrences(of: ".csv", with: ".jsonl")
                    process.arguments = [
                        "-u", "-m", "doc_cleaner", "scan",
                        "--input", inputPath,
                        "--output-root", outputPath,
                        "--plan", planPath,
                        "--jsonl", jsonlPath,
                        "--model", model,
                        "--confidence-threshold", String(confidenceThreshold),
                        "--ollama-host", ollamaHost,
                        "--output-format", "jsonl",
                        "--ocr",
                        "--ocr-language", "deu+eng",
                    ]
                    let stdout = Pipe()
                    let stderr = Pipe()
                    process.environment = self.enrichedEnvironment()
                    process.standardOutput = stdout
                    process.standardError = stderr

                    let log = URL(fileURLWithPath: "/tmp/docsorter-scan.log")
                    func logLine(_ s: String) {
                        let line = s + "\n"
                        if let data = line.data(using: .utf8) {
                            if let handle = try? FileHandle(forWritingTo: log) {
                                handle.seekToEndOfFile(); handle.write(data); handle.closeFile()
                            } else {
                                try? data.write(to: log)
                            }
                        }
                    }
                    try? "".write(to: log, atomically: true, encoding: .utf8)  // reset log
                    logLine("python: \(python)")
                    logLine("args: \(process.arguments ?? [])")

                    try process.run()
                    logLine("process started, pid=\(process.processIdentifier)")

                    // availableData blocks until data arrives or EOF — safe on a background thread
                    let handle = stdout.fileHandleForReading
                    var buffer = Data()
                    var lineCount = 0
                    while true {
                        let chunk = handle.availableData
                        if chunk.isEmpty { break }  // EOF: process closed its stdout
                        buffer.append(chunk)
                        while let nlIdx = buffer.firstIndex(of: UInt8(ascii: "\n")) {
                            let lineData = Data(buffer[buffer.startIndex..<nlIdx])
                            buffer.removeSubrange(buffer.startIndex...nlIdx)
                            lineCount += 1
                            logLine("line \(lineCount): \(String(data: lineData, encoding: .utf8) ?? "<binary>")")
                            guard let event = Self.decodeEvent(lineData) else { continue }
                            continuation.yield(event)
                        }
                    }

                    process.waitUntilExit()
                    logLine("exit code: \(process.terminationStatus), lines received: \(lineCount)")

                    if process.terminationStatus != 0 {
                        let errData = stderr.fileHandleForReading.readDataToEndOfFile()
                        let msg = String(data: errData, encoding: .utf8)?
                            .trimmingCharacters(in: .whitespacesAndNewlines)
                            ?? "exit code \(process.terminationStatus)"
                        logLine("stderr: \(msg)")
                        continuation.finish(throwing: BridgeError.processError("Scan failed: \(msg)"))
                    } else {
                        continuation.finish()
                    }
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }

    // MARK: - apply

    func apply(planPath: String) async throws -> ApplyResult {
        let python = try python3Path()

        let undoPath = planPath
            .replacingOccurrences(of: ".csv", with: "")
            + "-undo-\(Int(Date().timeIntervalSince1970)).json"

        let process = Process()
        process.executableURL = URL(fileURLWithPath: python)
        process.arguments = [
            "-m", "doc_cleaner", "apply",
            "--plan", planPath,
            "--undo", undoPath,
            "--yes",
        ]
        let stdout = Pipe()
        let stderr = Pipe()
        process.environment = self.enrichedEnvironment()
        process.standardOutput = stdout
        process.standardError = stderr
        try process.run()
        process.waitUntilExit()

        if process.terminationStatus != 0 {
            let errMsg = String(
                data: stderr.fileHandleForReading.readDataToEndOfFile(),
                encoding: .utf8
            ) ?? "Unknown error"
            throw BridgeError.processError(errMsg)
        }

        let out = String(
            data: stdout.fileHandleForReading.readDataToEndOfFile(),
            encoding: .utf8
        ) ?? ""

        return ApplyResult(
            moved: Self.parseCount(out, keyword: "Moved:"),
            skipped: Self.parseCount(out, keyword: "Skipped:"),
            errors: Self.parseCount(out, keyword: "Errors:"),
            undoPath: FileManager.default.fileExists(atPath: undoPath) ? undoPath : nil
        )
    }

    // MARK: - undo

    func undo(undoManifestPath: String) async throws {
        let python = try python3Path()
        let process = Process()
        process.executableURL = URL(fileURLWithPath: python)
        process.arguments = [
            "-m", "doc_cleaner", "undo",
            "--undo-manifest", undoManifestPath,
        ]
        let stderr = Pipe()
        process.environment = self.enrichedEnvironment()
        process.standardError = stderr
        process.standardOutput = Pipe()
        try process.run()
        process.waitUntilExit()

        if process.terminationStatus != 0 {
            let errMsg = String(
                data: stderr.fileHandleForReading.readDataToEndOfFile(),
                encoding: .utf8
            ) ?? "Unknown error"
            throw BridgeError.processError(errMsg)
        }
    }

    // MARK: - Helpers

    private static func decodeTaxonomyEvent(_ data: Data) -> TaxonomySuggestionEvent? {
        let trimmed = data.trimmingNewlines()
        guard !trimmed.isEmpty else { return nil }
        if let e = try? JSONDecoder().decode(EmbedEvent.self, from: trimmed), e.event == "embed" {
            return .embed(e)
        }
        if let e = try? JSONDecoder().decode(PeekEvent.self, from: trimmed), e.event == "peek" {
            return .peek(e)
        }
        if let e = try? JSONDecoder().decode(TaxonomyResultEvent.self, from: trimmed), e.event == "taxonomy" {
            return .result(e)
        }
        return nil
    }

    private static func decodeEvent(_ data: Data) -> ScanEvent? {
        let trimmed = data.trimmingNewlines()
        guard !trimmed.isEmpty else { return nil }
        if let e = try? JSONDecoder().decode(ProgressEvent.self, from: trimmed), e.event == "progress" {
            return .progress(e)
        }
        if let e = try? JSONDecoder().decode(DoneEvent.self, from: trimmed), e.event == "done" {
            return .done(e)
        }
        if let e = try? JSONDecoder().decode(ErrorEvent.self, from: trimmed), e.event == "error" {
            return .error(e)
        }
        return nil
    }

    private static func parseCount(_ text: String, keyword: String) -> Int {
        guard let range = text.range(of: keyword) else { return 0 }
        let after = text[range.upperBound...].trimmingCharacters(in: .whitespaces)
        return Int(after.prefix(while: { $0.isNumber })) ?? 0
    }
}

private extension Data {
    func trimmingNewlines() -> Data {
        var result = self
        while result.last == UInt8(ascii: "\n") || result.last == UInt8(ascii: "\r") {
            result = result.dropLast()
        }
        return result
    }
}
