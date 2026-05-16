import SwiftUI
import AppKit
import QuickLookUI

struct ReviewTableView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var settings: Settings

    @State private var selectedRowID: UUID?
    @State private var expandedRowID: UUID?
    @State private var hoveredRowID: UUID?
    @State private var isApplying = false
    @State private var applyError: String?

    private var selectedCount: Int { appState.rows.filter(\.isSelected).count }
    private var confidentCount: Int { appState.rows.filter { !$0.needsReview }.count }
    private var reviewCount: Int { appState.rows.filter(\.needsReview).count }

    var body: some View {
        VStack(spacing: 0) {
            columnHeader

            ScrollView {
                VStack(spacing: 0) {
                    ForEach($appState.rows) { $row in
                        VStack(spacing: 0) {
                            RowView(
                                row: $row,
                                isSelected: selectedRowID == row.id,
                                isHovered: hoveredRowID == row.id
                            )
                            .overlay(alignment: .leading) {
                                if row.needsReview {
                                    Rectangle()
                                        .fill(Color(hex: "#e3a02b"))
                                        .frame(width: 2)
                                }
                            }
                            .onTapGesture { selectedRowID = row.id }
                            .onHover { hoveredRowID = $0 ? row.id : nil }

                            if expandedRowID == row.id {
                                DetailPanelView(row: $row) { expandedRowID = nil }
                                    .padding(.horizontal, 16)
                                    .padding(.vertical, 12)
                                    .background(Color(hex: "#0a0a0a"))
                            }

                            Divider().background(Color(hex: "#1a1a1a"))
                        }
                    }
                }
                .frame(maxWidth: .infinity)
            }

            bottomBar
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .background(Color(hex: "#0d0d0d"))
        .focusable()
        .onKeyPress(.upArrow)   { navigateRow(by: -1); return .handled }
        .onKeyPress(.downArrow) { navigateRow(by:  1); return .handled }
        .onKeyPress(.return)    { toggleDetailPanel();  return .handled }
        .onKeyPress(.space)     { toggleQuickLook();      return .handled }
        .onKeyPress(KeyEquivalent("x")) { excludeSelected(); return .handled }
    }

    // MARK: - Column header

    private var columnHeader: some View {
        Divider().background(Color(hex: "#1e1e1e"))
    }

    // MARK: - Bottom bar

    private var bottomBar: some View {
        VStack(spacing: 0) {
            Divider().background(Color(hex: "#1e1e1e"))

            if let error = applyError {
                Text(error)
                    .font(.system(size: 11))
                    .foregroundColor(Color(hex: "#f85149"))
                    .padding(.horizontal, 16)
                    .padding(.vertical, 6)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color(hex: "#1a0a0a"))
            }

            HStack(spacing: 12) {
                Text("\(confidentCount) confident · \(reviewCount) need review")
                    .font(.custom("SF Mono", size: 11))
                    .foregroundColor(.secondary)

                Spacer()

                Button("New Scan") { appState.reset() }
                    .buttonStyle(SecondaryButtonStyle())

                Button(action: selectAllConfident) {
                    Text("Select Confident")
                }
                .buttonStyle(SecondaryButtonStyle())

                Button(action: applySelected) {
                    Text(isApplying ? "Applying…" : "Apply (\(selectedCount))")
                }
                .buttonStyle(PrimaryButtonStyle())
                .disabled(selectedCount == 0 || isApplying)
                .keyboardShortcut(.return, modifiers: .command)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(Color(hex: "#111111"))
        }
    }

    // MARK: - Keyboard actions

    private func navigateRow(by delta: Int) {
        guard !appState.rows.isEmpty else { return }
        if let id = selectedRowID,
           let idx = appState.rows.firstIndex(where: { $0.id == id }) {
            selectedRowID = appState.rows[max(0, min(appState.rows.count - 1, idx + delta))].id
        } else {
            selectedRowID = appState.rows.first?.id
        }
    }

    private func toggleDetailPanel() {
        guard let id = selectedRowID else { return }
        expandedRowID = expandedRowID == id ? nil : id
    }

    private func toggleQuickLook() {
        guard let panel = QLPreviewPanel.shared() else { return }
        if panel.isVisible {
            panel.close()
            return
        }
        guard let id = selectedRowID,
              let row = appState.rows.first(where: { $0.id == id })
        else { return }
        QuickLookCoordinator.shared.url = URL(fileURLWithPath: row.sourcePath)
        panel.dataSource = QuickLookCoordinator.shared
        panel.reloadData()
        panel.makeKeyAndOrderFront(nil)
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
        guard let planPath = appState.planPath else { return }
        isApplying = true
        applyError = nil
        appState.writePlanEdits(toPlanCSV: planPath)
        Task {
            do {
                let result = try await PythonBridge.shared.apply(planPath: planPath)
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
    let isHovered: Bool

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: row.isSelected ? "checkmark.square.fill" : "square")
                .foregroundColor(row.isSelected ? .accentColor : Color(hex: "#555555"))
                .font(.system(size: 14))
                .onTapGesture { row.isSelected.toggle() }

            VStack(alignment: .leading, spacing: 2) {
                Text(row.filename)
                    .font(.custom("SF Mono", size: 10))
                    .foregroundColor(Color(hex: "#555555"))
                    .lineLimit(1)
                    .truncationMode(.middle)
                if !row.suggestedFilename.isEmpty {
                    HStack(spacing: 4) {
                        Image(systemName: "arrow.right")
                            .font(.system(size: 8))
                            .foregroundColor(.accentColor)
                        Text(row.suggestedFilename)
                            .font(.custom("SF Mono", size: 11))
                            .foregroundColor(.primary)
                            .lineLimit(1)
                            .truncationMode(.middle)
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            Text("\(row.category) / \(row.subcategory)")
                .font(.custom("SF Mono", size: 11))
                .foregroundColor(.secondary)
                .lineLimit(1)
                .frame(width: 200, alignment: .leading)

            Text("\(row.confidence)%")
                .font(.custom("SF Mono", size: 11))
                .foregroundColor(confidenceColor(row.confidence))
                .frame(width: 45, alignment: .trailing)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(rowBackground)
        .contentShape(Rectangle())
    }

    private var rowBackground: Color {
        if isSelected { return Color.accentColor.opacity(0.15) }
        if isHovered  { return Color(hex: "#161616") }
        return Color.clear
    }

    private func confidenceColor(_ c: Int) -> Color {
        if c >= 90 { return Color(hex: "#3fb950") }
        if c >= 70 { return Color(hex: "#e3a02b") }
        return Color(hex: "#f85149")
    }
}

// MARK: - QuickLook coordinator

final class QuickLookCoordinator: NSObject, QLPreviewPanelDataSource {
    static let shared = QuickLookCoordinator()
    var url: URL?

    func numberOfPreviewItems(in panel: QLPreviewPanel!) -> Int { url != nil ? 1 : 0 }
    func previewPanel(_ panel: QLPreviewPanel!, previewItemAt index: Int) -> (any QLPreviewItem)! {
        url as NSURL?
    }
}
