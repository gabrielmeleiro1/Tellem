import SwiftUI
import Combine

// MARK: - View Model

@MainActor
class ConversionViewModel: ObservableObject {
    // File selection
    @Published var selectedFile: SelectedFile?
    
    // Voice settings
    @Published var selectedVoice: VoiceOption = .amAdam
    @Published var speed: Double = 1.0
    
    // Conversion state
    @Published var isConverting = false
    @Published var currentStage: ConversionStage = .idle
    @Published var overallProgress: Double = 0
    @Published var eta: String = "--:--"
    @Published var chapters: [ChapterProgress] = []
    
    // Terminal logs
    @Published var logs: [LogEntry] = []
    @Published var autoScrollTerminal = true
    
    // Model status
    @Published var ttsModelLoaded = false
    @Published var cleanerModelLoaded = false
    @Published var activeModel: String?
    
    // Connection status
    @Published var isConnected = false
    @Published var connectionError: String?
    
    // Services
    private let grpcClient: GRPCClient
    private var conversionTask: Task<Void, Never>?
    private var modelStatusTask: Task<Void, Never>?
    
    init(grpcClient: GRPCClient = .shared) {
        self.grpcClient = grpcClient
        
        // Start monitoring model status
        startModelStatusMonitoring()
    }
    
    deinit {
        modelStatusTask?.cancel()
        conversionTask?.cancel()
    }
    
    // MARK: - Connection
    
    func checkConnection() async {
        do {
            try await grpcClient.connect()
            isConnected = true
            connectionError = nil
        } catch {
            isConnected = false
            connectionError = error.localizedDescription
        }
    }
    
    // MARK: - Model Status Monitoring
    
    private func startModelStatusMonitoring() {
        modelStatusTask = Task {
            do {
                // Initial status check
                try await checkConnection()
                
                // Stream updates
                for try await status in grpcClient.streamModelStatus() {
                    await updateModelStatus(status)
                }
            } catch {
                print("Model status monitoring error: \(error)")
            }
        }
    }
    
    private func updateModelStatus(_ status: ModelStatus) {
        ttsModelLoaded = status.ttsModel.isLoaded
        cleanerModelLoaded = status.cleanerModel.isLoaded
        
        // Update active model based on current stage
        switch currentStage {
        case .cleaning:
            activeModel = "cleaner"
        case .synthesizing:
            activeModel = "tts"
        default:
            activeModel = nil
        }
    }
    
    // MARK: - File Selection
    
    func selectFile(_ url: URL) {
        selectedFile = SelectedFile(url: url)
    }
    
    func showFilePicker() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.pdf, .epub]
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        
        if panel.runModal() == .OK, let url = panel.url {
            selectFile(url)
        }
    }
    
    // MARK: - Conversion
    
    func startConversion() {
        guard let file = selectedFile else { return }
        
        isConverting = true
        currentStage = .parsing
        overallProgress = 0
        eta = "--:--"
        logs.removeAll()
        chapters.removeAll()
        
        conversionTask = Task {
            do {
                let request = ConversionRequest(
                    sourcePath: file.url.path,
                    voice: selectedVoice.rawValue,
                    speed: Float(speed)
                )
                
                for try await update in grpcClient.convertBook(request: request) {
                    handleProgressUpdate(update)
                }
                
                isConverting = false
                currentStage = .complete
                
            } catch is CancellationError {
                isConverting = false
                currentStage = .cancelled
                addLog(level: .warning, message: "Conversion cancelled")
            } catch {
                isConverting = false
                currentStage = .error
                addLog(level: .error, message: "Conversion failed: \(error.localizedDescription)")
            }
        }
    }
    
    func cancelConversion() {
        conversionTask?.cancel()
        
        // Also send cancel request to backend
        Task {
            do {
                // TODO: Implement cancel request with proper ID
                // _ = try await grpcClient.conversionService.cancelConversion(...)
            } catch {
                print("Cancel request failed: \(error)")
            }
        }
        
        isConverting = false
        currentStage = .cancelled
        addLog(level: .warning, message: "Conversion cancelled by user")
    }
    
    private func handleProgressUpdate(_ update: ConversionProgress) {
        currentStage = update.stage
        overallProgress = Double(update.overallProgress)
        eta = update.eta
        
        // Update chapter progress
        if !update.currentChapterTitle.isEmpty {
            if let existingIdx = chapters.firstIndex(where: { $0.title == update.currentChapterTitle }) {
                chapters[existingIdx].progress = Double(update.chunkIndex) / Double(max(update.totalChunks, 1))
                chapters[existingIdx].isProcessing = true
            } else {
                // Mark previous chapter as complete if we moved to a new one
                if let lastIdx = chapters.indices.last {
                    chapters[lastIdx].isProcessing = false
                    chapters[lastIdx].isComplete = true
                }
                
                let chapter = ChapterProgress(
                    number: chapters.count + 1,
                    title: update.currentChapterTitle,
                    progress: Double(update.chunkIndex) / Double(max(update.totalChunks, 1)),
                    isProcessing: true
                )
                chapters.append(chapter)
            }
        }
        
        // Add logs
        for log in update.logs {
            addLog(level: log.level, message: log.message, source: log.source)
        }
        
        // Update model status from stage
        switch update.stage {
        case .cleaning:
            activeModel = "cleaner"
            cleanerModelLoaded = true
        case .synthesizing:
            activeModel = "tts"
            ttsModelLoaded = true
        default:
            activeModel = nil
        }
    }
    
    // MARK: - Terminal
    
    func addLog(level: LogLevel, message: String, source: String = "pipeline") {
        let entry = LogEntry(
            timestamp: Date(),
            level: level,
            message: message,
            source: source
        )
        logs.append(entry)
        
        // Limit log buffer
        if logs.count > 10000 {
            logs.removeFirst(logs.count - 10000)
        }
    }
    
    func clearLogs() {
        logs.removeAll()
    }
    
    // MARK: - Preview
    
    func previewVoice() {
        Task {
            do {
                addLog(level: .info, message: "Generating voice preview...")
                
                // TODO: Implement preview request
                // let request = ABPreviewRequest(voice: selectedVoice.rawValue, speed: Float(speed), text: "")
                // for try await chunk in grpcClient.conversionService.previewVoice(request) {
                //     // Play audio chunk
                // }
                
                addLog(level: .info, message: "Preview ready")
            } catch {
                addLog(level: .error, message: "Preview failed: \(error.localizedDescription)")
            }
        }
    }
}
