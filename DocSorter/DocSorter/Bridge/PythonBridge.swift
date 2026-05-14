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

    // MARK: - Python path resolution

    private func python3Path() throws -> String {
        let candidates = [
            "/usr/bin/python3",
            "/usr/local/bin/python3",
            "/opt/homebrew/bin/python3",
        ]
        for path in candidates {
            if FileManager.default.fileExists(atPath: path) { return path }
        }
        // Try `which python3`
        let which = Process()
        which.executableURL = URL(fileURLWithPath: "/usr/bin/which")
        which.arguments = ["python3"]
        let pipe = Pipe()
        which.standardOutput = pipe
        which.standardError = Pipe()
        try which.run()
        which.waitUntilExit()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let path = String(data: data, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        if !path.isEmpty { return path }
        throw BridgeError.pythonNotFound
    }

    // MARK: - suggest-taxonomy

    func suggestTaxonomy(
        inputPath: String,
        outputPath: String,
        model: String
    ) async throws -> [String: [String]] {
        let python = try python3Path()
        let process = Process()
        process.executableURL = URL(fileURLWithPath: python)
        process.arguments = [
            "-m", "doc_cleaner",
            "suggest-taxonomy",
            "--input", inputPath,
            "--output-root", outputPath,
            "--model", model,
        ]
        let stdout = Pipe()
        process.standardOutput = stdout
        process.standardError = Pipe()

        try process.run()
        process.waitUntilExit()

        let data = stdout.fileHandleForReading.readDataToEndOfFile()
        guard !data.isEmpty,
              let result = try? JSONDecoder().decode([String: [String]].self, from: data)
        else { return [:] }
        return result
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
            Task.detached { [weak self] in
                guard let self else { continuation.finish(); return }
                do {
                    let python = try self.python3Path()
                    let process = Process()
                    process.executableURL = URL(fileURLWithPath: python)
                    process.arguments = [
                        "-m", "doc_cleaner", "scan",
                        "--input", inputPath,
                        "--output-root", outputPath,
                        "--plan", planPath,
                        "--model", model,
                        "--confidence", String(confidenceThreshold),
                        "--ollama-host", ollamaHost,
                        "--output-format", "jsonl",
                    ]
                    let stdout = Pipe()
                    process.standardOutput = stdout
                    process.standardError = Pipe()

                    try process.run()

                    let handle = stdout.fileHandleForReading
                    var buffer = Data()
                    var finished = false

                    while !finished {
                        let chunk = handle.availableData
                        if chunk.isEmpty {
                            if !process.isRunning { finished = true }
                            try? await Task.sleep(nanoseconds: 50_000_000)
                            continue
                        }
                        buffer.append(chunk)
                        while let newlineIdx = buffer.firstIndex(of: UInt8(ascii: "\n")) {
                            let lineData = buffer[buffer.startIndex...newlineIdx]
                            buffer.removeSubrange(buffer.startIndex...newlineIdx)
                            if let event = Self.decodeEvent(lineData) {
                                continuation.yield(event)
                                if case .done = event { finished = true }
                                if case .error = event { finished = true }
                            }
                        }
                    }

                    // Drain remaining buffer
                    let remaining = handle.readDataToEndOfFile()
                    buffer.append(remaining)
                    for lineSlice in buffer.split(separator: UInt8(ascii: "\n")) {
                        if let event = Self.decodeEvent(Data(lineSlice)) {
                            continuation.yield(event)
                        }
                    }

                    process.waitUntilExit()
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }

    // MARK: - apply

    func apply(planPath: String, outputPath: String) async throws -> ApplyResult {
        let python = try python3Path()
        let process = Process()
        process.executableURL = URL(fileURLWithPath: python)
        process.arguments = [
            "-m", "doc_cleaner", "apply",
            "--plan", planPath,
            "--output-root", outputPath,
        ]
        let stdout = Pipe()
        let stderr = Pipe()
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

        let undoPath = out.components(separatedBy: "\n")
            .first { $0.contains("Undo manifest:") }
            .flatMap { line -> String? in
                let parts = line.components(separatedBy: "Undo manifest:")
                return parts.last?.trimmingCharacters(in: .whitespaces)
            }

        return ApplyResult(
            moved: Self.parseCount(out, keyword: "Moved:"),
            skipped: Self.parseCount(out, keyword: "Skipped:"),
            errors: Self.parseCount(out, keyword: "Errors:"),
            undoPath: undoPath
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
