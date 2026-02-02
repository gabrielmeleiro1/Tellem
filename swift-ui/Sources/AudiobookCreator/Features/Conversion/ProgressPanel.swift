import SwiftUI

// MARK: - Progress Panel

struct ProgressPanel: View {
    @ObservedObject var viewModel: ConversionViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header with stage indicator
            HStack {
                StageIndicator(stage: viewModel.currentStage, isActive: viewModel.isConverting)
                
                Spacer()
                
                if viewModel.isConverting {
                    Text("ETA: \(viewModel.eta)")
                        .font(.system(.caption, design: .monospaced))
                        .foregroundColor(.mossTextDim)
                }
            }
            
            // Overall progress
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("OVERALL PROGRESS")
                        .font(.system(.caption, design: .monospaced))
                        .foregroundColor(.mossTextDim)
                    
                    Spacer()
                    
                    Text("\(Int(viewModel.overallProgress * 100))%")
                        .font(.system(.caption, design: .monospaced))
                        .foregroundColor(.mossAccent)
                }
                
                // Progress bar
                GeometryReader { geometry in
                    ZStack(alignment: .leading) {
                        // Background
                        Rectangle()
                            .fill(Color.mossBorder)
                        
                        // Fill
                        Rectangle()
                            .fill(Color.mossAccent)
                            .frame(width: geometry.size.width * viewModel.overallProgress)
                    }
                }
                .frame(height: 12)
                
                // Chapter count
                Text("\(viewModel.chapters.filter(\.isComplete).count)/\(viewModel.chapters.count) chapters")
                    .font(.caption2)
                    .foregroundColor(.mossTextFaded)
            }
            
            Divider()
                .background(Color.mossBorder)
            
            // Per-chapter progress
            Text("CHAPTERS")
                .font(.system(.caption, design: .monospaced))
                .foregroundColor(.mossTextDim)
            
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 4) {
                    ForEach(viewModel.chapters) { chapter in
                        ChapterProgressRow(chapter: chapter)
                    }
                }
            }
            .frame(maxHeight: 200)
            
            Spacer()
        }
        .padding()
        .mossPanel()
    }
}

// MARK: - Stage Indicator

struct StageIndicator: View {
    let stage: ConversionStage
    let isActive: Bool
    
    private var icon: String {
        switch stage {
        case .idle: return "○"
        case .parsing, .cleaning, .synthesizing, .encoding, .packaging:
            return isActive ? "◐" : "○"
        case .complete: return "●"
        case .error: return "✕"
        case .cancelled: return "○"
        }
    }
    
    private var color: Color {
        switch stage {
        case .idle, .cancelled: return .mossTextFaded
        case .parsing, .cleaning, .synthesizing, .encoding, .packaging:
            return isActive ? .mossAccent : .mossTextDim
        case .complete: return .mossSuccess
        case .error: return .mossRust
        }
    }
    
    var body: some View {
        HStack(spacing: 8) {
            Text(icon)
                .foregroundColor(color)
                .font(.system(.body, design: .monospaced))
            
            Text(stage.displayName.uppercased())
                .font(.system(.caption, design: .monospaced))
                .foregroundColor(color)
        }
    }
}

// MARK: - Chapter Progress Row

struct ChapterProgressRow: View {
    let chapter: ChapterProgress
    
    private var statusIcon: String {
        if chapter.hasError { return "✕" }
        if chapter.isComplete { return "✓" }
        if chapter.isProcessing { return "▶" }
        return "○"
    }
    
    private var statusColor: Color {
        if chapter.hasError { return .mossRust }
        if chapter.isComplete { return .mossSuccess }
        if chapter.isProcessing { return .mossAccent }
        return .mossTextFaded
    }
    
    var body: some View {
        HStack(spacing: 8) {
            // Status icon
            Text(statusIcon)
                .foregroundColor(statusColor)
                .font(.system(.caption, design: .monospaced))
                .frame(width: 16)
            
            // Chapter number
            Text(String(format: "%02d", chapter.number))
                .font(.system(.caption, design: .monospaced))
                .foregroundColor(.mossTextDim)
            
            // Chapter title
            Text(chapter.title)
                .font(.system(.caption, design: .monospaced))
                .foregroundColor(.mossTextMain)
                .lineLimit(1)
            
            Spacer(minLength: 8)
            
            // Progress for active chapter
            if chapter.isProcessing {
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        Rectangle()
                            .fill(Color.mossBorder)
                        
                        Rectangle()
                            .fill(Color.mossAccent)
                            .frame(width: geo.size.width * chapter.progress)
                    }
                }
                .frame(width: 50, height: 4)
                
                Text("\(Int(chapter.progress * 100))%")
                    .font(.caption2)
                    .foregroundColor(.mossTextFaded)
                    .frame(width: 28, alignment: .trailing)
            }
        }
        .padding(.vertical, 2)
    }
}
