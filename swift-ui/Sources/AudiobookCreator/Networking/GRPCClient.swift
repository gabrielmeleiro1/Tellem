import Foundation

// MARK: - Simplified gRPC Client

@MainActor
final class GRPCClient: ObservableObject {
    static let shared = GRPCClient()
    
    @Published var connectionState: ConnectionState = .disconnected
    @Published var lastError: Error?
    
    enum ConnectionState {
        case disconnected
        case connecting
        case connected
        case failed(Error)
    }
    
    enum ConnectionTarget {
        case host(String, port: Int)
    }
    
    private let target: ConnectionTarget
    private var isConnected = false
    
    nonisolated init(target: ConnectionTarget = .host("localhost", port: 50051)) {
        self.target = target
    }
    
    func connect() async throws {
        guard !isConnected else { return }
        
        connectionState = .connecting
        
        // Simulate connection for now
        // In production, this would create a real gRPC channel
        try await Task.sleep(nanoseconds: 100_000_000) // 100ms
        
        isConnected = true
        connectionState = .connected
    }
    
    func disconnect() {
        isConnected = false
        connectionState = .disconnected
    }
    
    // MARK: - Conversion
    
    func convertBook(request: ConversionRequest) -> AsyncThrowingStream<ConversionProgress, Error> {
        AsyncThrowingStream { continuation in
            Task {
                do {
                    try await connect()
                    
                    // Simulate conversion progress
                    // In production, this would make a real gRPC streaming call
                    
                    let stages: [ConversionStage] = [.parsing, .cleaning, .synthesizing, .encoding, .packaging, .complete]
                    
                    for (index, stage) in stages.enumerated() {
                        // Check for cancellation
                        try Task.checkCancellation()
                        
                        try await Task.sleep(nanoseconds: 500_000_000) // 500ms per stage
                        
                        let progress = ConversionProgress(
                            stage: stage,
                            stageName: stage.displayName,
                            currentChapterTitle: "Chapter \(index + 1)",
                            chunkIndex: index * 10,
                            totalChunks: 50,
                            overallProgress: Float(index + 1) / Float(stages.count),
                            eta: "00:\(60 - index * 10)",
                            logs: [
                                LogEntry(
                                    timestamp: Date(),
                                    level: .info,
                                    message: "Processing \(stage.displayName)...",
                                    source: "pipeline"
                                ),
                                LogEntry(
                                    timestamp: Date(),
                                    level: .process,
                                    message: "Chapter \(index + 1): Working on chunk \(index * 10)/50",
                                    source: "pipeline"
                                )
                            ]
                        )
                        
                        continuation.yield(progress)
                    }
                    
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }
    
    // MARK: - Model Status
    
    func getModelStatus() async throws -> ModelStatus {
        try await connect()
        
        return ModelStatus(
            ttsModel: TTSModelStatus(
                isLoaded: false,
                modelName: "mlx-community/Kokoro-82M-bf16",
                vramUsageBytes: 0,
                device: "metal"
            ),
            cleanerModel: CleanerModelStatus(
                isLoaded: false,
                modelName: "mlx-community/Llama-3.2-3B-Instruct-4bit",
                vramUsageBytes: 0
            )
        )
    }
    
    func streamModelStatus() -> AsyncThrowingStream<ModelStatus, Error> {
        AsyncThrowingStream { continuation in
            Task {
                do {
                    try await connect()
                    
                    // Stream model status every second
                    while !Task.isCancelled {
                        let status = try await getModelStatus()
                        continuation.yield(status)
                        try await Task.sleep(nanoseconds: 1_000_000_000)
                    }
                    
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }
}
