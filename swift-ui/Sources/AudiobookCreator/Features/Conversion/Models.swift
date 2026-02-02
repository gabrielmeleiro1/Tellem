import Foundation
import UniformTypeIdentifiers

// MARK: - UI Models

struct ChapterProgress: Identifiable {
    let id = UUID()
    let number: Int
    let title: String
    var progress: Double
    var isProcessing: Bool
    var isComplete: Bool = false
    var hasError: Bool = false
}

struct LogEntry: Identifiable {
    let id = UUID()
    let timestamp: Date
    let level: LogLevel
    let message: String
    let source: String
    
    var timestampFormatted: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss.SSS"
        return formatter.string(from: timestamp)
    }
}

enum LogLevel: String {
    case debug = "DEBUG"
    case info = "INFO"
    case process = "PROCESS"
    case warning = "WARNING"
    case error = "ERROR"
}

enum ConversionStage: String, CaseIterable {
    case idle = "IDLE"
    case parsing = "PARSING"
    case cleaning = "CLEANING"
    case synthesizing = "SYNTHESIZING"
    case encoding = "ENCODING"
    case packaging = "PACKAGING"
    case complete = "COMPLETE"
    case error = "ERROR"
    case cancelled = "CANCELLED"
    
    var displayName: String {
        switch self {
        case .idle: return "Idle"
        case .parsing: return "Parsing Document"
        case .cleaning: return "Cleaning Text"
        case .synthesizing: return "Synthesizing Speech"
        case .encoding: return "Encoding Audio"
        case .packaging: return "Packaging M4B"
        case .complete: return "Complete"
        case .error: return "Error"
        case .cancelled: return "Cancelled"
        }
    }
}

// MARK: - Selected File Model

struct SelectedFile {
    let url: URL
    
    var name: String {
        url.lastPathComponent
    }
    
    var formattedSize: String {
        let attributes = try? FileManager.default.attributesOfItem(atPath: url.path)
        let size = attributes?[.size] as? Int64 ?? 0
        return ByteCountFormatter.string(fromByteCount: size, countStyle: .file)
    }
    
    var iconName: String {
        switch url.pathExtension.lowercased() {
        case "pdf":
            return "doc.text"
        case "epub":
            return "book"
        default:
            return "doc"
        }
    }
}

// MARK: - Voice Options

enum VoiceOption: String, CaseIterable, Identifiable {
    case amAdam = "am_adam"
    case afBella = "af_bella"
    case amMichael = "am_michael"
    case afSarah = "af_sarah"
    case bfEmma = "bf_emma"
    case bmGeorge = "bm_george"
    
    var id: String { rawValue }
    
    var displayName: String {
        switch self {
        case .amAdam: return "Adam (American Male)"
        case .afBella: return "Bella (American Female)"
        case .amMichael: return "Michael (American Male)"
        case .afSarah: return "Sarah (American Female)"
        case .bfEmma: return "Emma (British Female)"
        case .bmGeorge: return "George (British Male)"
        }
    }
    
    var description: String {
        switch self {
        case .amAdam: return "deep, authoritative"
        case .afBella: return "warm, conversational"
        case .amMichael: return "friendly, casual"
        case .afSarah: return "professional, clear"
        case .bfEmma: return "refined, articulate"
        case .bmGeorge: return "classic, distinguished"
        }
    }
}

// MARK: - Networking Models

struct ConversionRequest {
    let sourcePath: String
    let voice: String
    let speed: Float
}

struct ConversionProgress {
    let stage: ConversionStage
    let stageName: String
    let currentChapterTitle: String
    let chunkIndex: Int
    let totalChunks: Int
    let overallProgress: Float
    let eta: String
    let logs: [LogEntry]
}

struct ModelStatus {
    let ttsModel: TTSModelStatus
    let cleanerModel: CleanerModelStatus
}

struct TTSModelStatus {
    let isLoaded: Bool
    let modelName: String
    let vramUsageBytes: Int64
    let device: String
}

struct CleanerModelStatus {
    let isLoaded: Bool
    let modelName: String
    let vramUsageBytes: Int64
}

// MARK: - UTType Extension

extension UTType {
    static var epub: UTType {
        UTType(importedAs: "org.idpf.epub-container")
    }
}
