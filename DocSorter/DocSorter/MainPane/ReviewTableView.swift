import SwiftUI
import AppKit

struct ReviewTableView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var settings: Settings

    @State private var selectedRowID: UUID?
    @State private var expandedRowID: UUID?
    @State private var isApplying = false
    @State private var applyError: String?

    private var selectedCount: Int { appState.rows.filter(\.isSelected).count }
    private var confidentCount: Int { appState.rows.filter { !$0.needsReview }.count }
    private var reviewCount: Int { appState.rows.filter(\.needsReview).count }

    var body: some View {
        VStack(spacing: 0) {
            toolbar

            if let error = applyError {
                Text(error)
                    .font(.custom("SF Mono", size: 11))
                    .foregroundColor(Color(hex: "#f85149"))
                    .padding(.horizontal, 16)
                    .padding(.vertical, 6)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color(hex: "#1a0a0a"))
            }

            ScrollView {
                LazyVStack(spacing: 0) {
                    ForEach($appState.rows) { $row in
                        VStack(spacing: 0) {
                            RowView(
                                row: $row,
                                isSelected: selectedRowID == row.id
                            )
                            .background(rowBackground(row: row))
                            .overlay(alignment: .leading) {
                                if row.needsReview {
                                    Rectangle()
                                        .fill(Color(hex: "#e3a02b"))
                                        .frame(width: 3)
                                }
                            }
                            .onTapGesture {
                                selectedRowID = row.id
                            }

                            if expandedRowID == row.id {
                                DetailPanelView(row: $row) {
                                    expandedRowID = nil
                                }
                                .padding(.horizontal, 16)
                                .padding(.vertical, 12)
                                .background(Color(hex: "#0a0a0a"))
                            }

                            Divider()
                                .background(Color(hex: "#1a1a1a"))
                        }
                    }
                }
            }
            .background(Color(hex: "#0d0d0d"))
        }
        .background(Color(hex: "#0d0d0d"))
        .focusable()
        .onKeyPress(.upArrow) { navigateRow(by: -1); return .handled }
        .onKeyPress(.downArrow) { navigateRow(by: 1); return .handled }
        .onKeyPress(.return) { toggleDetailPanel(); return .handled }
        .onKeyPress(.space) { openQuickLook(); return .handled }
        .onKeyPress(KeyEquivalent("x")) { excludeSelected(); return .handled }
    }

    // MARK: - Toolbar

    private var toolbar: some View {
        HStack {
            Button(action: selectAllConfident) {
                HStack(spacing: 6) {
                    Image(systemName: "checkmark.square")
                        .foregroundColor(Color(hex: "#3a8fff"))
                    Text("Select all confident")
                        .font(.custom("SF Mono", size: 11))
                        .foregroundColor(Color(hex: "#aaaaaa"))
                }
            }
            .buttonStyle(.plain)

            Spacer()

            Text("\(confidentCount) confident · \(reviewCount) need review")
                .font(.custom("SF Mono", size: 11))
                .foregroundColor(Color(hex: "#555555"))

            Spacer()

            Button(action: applySelected) {
                Text("Apply selected (\(selectedCount))")
                    .font(.custom("SF Mono", size: 12).bold())
                    .foregroundColor(.white)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 6)
                    .background(
                        selectedCount > 0
                            ? Color(hex: "#3a8fff")
                            : Color(hex: "#1a1a1a")
                    )
                    .cornerRadius(5)
            }
            .buttonStyle(.plain)
            .disabled(selectedCount == 0 || isApplying)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(Color(hex: "#111111"))
    }

    // MARK: - Row background

    private func rowBackground(row: ReviewRow) -> Color {
        if selectedRowID == row.id { return Color(hex: "#1a2a3a") }
        if !row.needsReview && row.isSelected { return Color(hex: "#0d1a0d") }
        return Color.clear
    }

    // MARK: - Keyboard actions

    private func navigateRow(by delta: Int) {
        guard !appState.rows.isEmpty else { return }
        if let id = selectedRowID,
           let idx = appState.rows.firstIndex(where: { $0.id == id }) {
            let newIdx = max(0, min(appState.rows.count - 1, idx + delta))
            selectedRowID = appState.rows[newIdx].id
        } else {
            selectedRowID = appState.rows.first?.id
        }
    }

    private func toggleDetailPanel() {
        guard let id = selectedRowID else { return }
        expandedRowID = expandedRowID == id ? nil : id
    }

    private func openQuickLook() {
        guard let id = selectedRowID,
              let row = appState.rows.first(where: { $0.id == id })
        else { return }
        let url = URL(fileURLWithPath: row.sourcePath)
        NSWorkspace.shared.open(url)
    }

    private func excludeSelected() {
        guard let id = selectedRowID,
              let idx = appState.rows.firstIndex(where: { $0.id == id })
        else { return }
        appState.rows[idx].isSelected = false
    }

    private func selectAllConfident() {
        for i in appState.rows.indices where !appState.rows[i].needsReview {
            appState.rows[i].isSelected = true
        }
    }

    // MARK: - Apply

    private func applySelected() {
        guard let planPath = appState.planPath,
              let outputURL = settings.outputURL
        else { return }
        isApplying = true
        applyError = nil
        Task {
            do {
                let result = try await PythonBridge.shared.apply(
                    planPath: planPath,
                    outputPath: outputURL.path
                )
                await MainActor.run {
                    appState.applyDone(
                        moved: result.moved,
                        skipped: result.skipped,
                        errors: result.errors,
                        undoPath: result.undoPath
                    )
                }
            } catch {
                await MainActor.run {
                    applyError = "Apply failed: \(error.localizedDescription)"
                    isApplying = false
                }
            }
        }
    }
}

// MARK: - RowView

struct RowView: View {
    @Binding var row: ReviewRow
    let isSelected: Bool

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: row.isSelected ? "checkmark.square.fill" : "square")
                .foregroundColor(
                    row.isSelected ? Color(hex: "#3a8fff") : Color(hex: "#555555")
                )
                .font(.system(size: 14))
                .onTapGesture { row.isSelected.toggle() }

            Text(row.filename)
                .font(.custom("SF Mono", size: 12))
                .foregroundColor(.white)
                .lineLimit(1)
                .truncationMode(.middle)
                .frame(maxWidth: .infinity, alignment: .leading)

            Text("\(row.category) / \(row.subcategory)")
                .font(.custom("SF Mono", size: 11))
                .foregroundColor(Color(hex: "#aaaaaa"))
                .lineLimit(1)
                .frame(width: 200, alignment: .leading)

            Text("\(row.confidence)%")
                .font(.custom("SF Mono", size: 11))
                .foregroundColor(confidenceColor(row.confidence))
                .frame(width: 45, alignment: .trailing)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
    }

    private func confidenceColor(_ c: Int) -> Color {
        if c >= 90 { return Color(hex: "#3fb950") }
        if c >= 70 { return Color(hex: "#e3a02b") }
        return Color(hex: "#f85149")
    }
}
