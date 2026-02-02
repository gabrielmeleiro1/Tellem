import SwiftUI

// MARK: - Terminal View

struct TerminalView: View {
    @ObservedObject var viewModel: ConversionViewModel
    
    var body: some View {
        VStack(spacing: 0) {
            // Terminal header
            HStack {
                Text("TERMINAL")
                    .font(.system(.caption, design: .monospaced))
                    .foregroundColor(.mossTextDim)
                
                Spacer()
                
                HStack(spacing: 12) {
                    Toggle("Auto-scroll", isOn: $viewModel.autoScrollTerminal)
                        .toggleStyle(.checkbox)
                        .font(.caption)
                        .foregroundColor(.mossTextDim)
                    
                    Button("Clear") {
                        viewModel.clearLogs()
                    }
                    .font(.caption)
                    .foregroundColor(.mossTextDim)
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .background(Color.mossSurface)
            
            // Log entries with native scroll view
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 0) {
                        ForEach(viewModel.logs) { entry in
                            LogEntryRow(entry: entry)
                                .id(entry.id)
                        }
                    }
                    .padding(8)
                }
                .background(Color.mossCore)
                .font(.system(.caption, design: .monospaced))
                .onChange(of: viewModel.logs.count) { _ in
                    if viewModel.autoScrollTerminal, let last = viewModel.logs.last {
                        withAnimation(.easeOut(duration: 0.1)) {
                            proxy.scrollTo(last.id, anchor: .bottom)
                        }
                    }
                }
            }
            
            // Blinking cursor line
            HStack(spacing: 0) {
                BlinkingCursor()
                Spacer()
            }
            .padding(.horizontal, 8)
            .padding(.bottom, 4)
            .background(Color.mossCore)
        }
        .border(Color.mossBorder, width: 1)
    }
}

// MARK: - Log Entry Row

struct LogEntryRow: View {
    let entry: LogEntry
    
    private var levelColor: Color {
        switch entry.level {
        case .debug: return .mossTextFaded
        case .info: return .mossTextDim
        case .process: return .mossAccent
        case .warning: return .mossGold
        case .error: return .mossRust
        }
    }
    
    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            // Timestamp
            Text(entry.timestampFormatted)
                .foregroundColor(.mossTextFaded)
                .frame(width: 80, alignment: .leading)
            
            // Level indicator
            Text("[\(entry.level.rawValue)]")
                .foregroundColor(levelColor)
                .frame(width: 70, alignment: .leading)
            
            // Message
            Text(entry.message)
                .foregroundColor(entry.level == .process ? levelColor : .mossTextMain)
                .lineLimit(nil)
                .fixedSize(horizontal: false, vertical: true)
            
            Spacer(minLength: 0)
        }
        .padding(.vertical, 1)
    }
}

// MARK: - Blinking Cursor

struct BlinkingCursor: View {
    @State private var isVisible = true
    
    var body: some View {
        Rectangle()
            .fill(Color.mossTextMain)
            .frame(width: 6, height: 12)
            .opacity(isVisible ? 1 : 0)
            .onAppear {
                withAnimation(.easeInOut(duration: 0.5).repeatForever(autoreverses: true)) {
                    isVisible = false
                }
            }
    }
}
