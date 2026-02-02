# Audiobook Creator - UI Revamp Plan

## Executive Summary

The current Streamlit-based UI has fundamental architectural limitations that prevent smooth, real-time user experiences. This plan outlines a migration to a **hybrid architecture** combining a native SwiftUI frontend with the existing Python backend.

---

## 1. Current Pain Points Analysis

### 1.1 Streamlit Limitations
| Issue | Impact | Current Workaround |
|-------|--------|-------------------|
| Rerun-based updates | UI flickers, loses scroll position | `st.rerun()` with sleep delays |
| No real-time streaming | Terminal logs are batched, not live | Message queue with polling |
| Session state complexity | State sync issues across threads | Manual locking and copying |
| File upload limits | No drag-and-drop from Finder | Basic file uploader widget |
| No native audio controls | Custom HTML audio player | `st.audio()` with base64 encoding |

### 1.2 Specific UI Problems
```
❌ Progress bars don't update smoothly during parsing
❌ Model loading happens invisibly in background
❌ Terminal is just HTML text, not a real scrollback buffer
❌ No waveform visualization during playback
❌ Can't browse library like Finder
❌ Settings reset on every restart
```

---

## 2. Proposed Architecture

### 2.1 Hybrid Approach (Recommended)

```
┌─────────────────────────────────────────────────────────────────┐
│                      SWIFTUI FRONTEND                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Main View  │  │   Player    │  │      Library Browser    │  │
│  │  Controller │  │   Engine    │  │   (Finder-like grid)    │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
│         │                │                      │                │
│  ┌──────┴────────────────┴──────────────────────┴──────────┐   │
│  │              SwiftUI State Management                    │   │
│  │         (ObservableObject, @Published, @State)           │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │ gRPC / WebSocket                  │
└─────────────────────────────┼───────────────────────────────────┘
                              │
┌─────────────────────────────┼───────────────────────────────────┐
│                      PYTHON BACKEND                             │
│  ┌──────────────────────────┴───────────────────────────────┐   │
│  │              gRPC Server (grpcio + asyncio)               │   │
│  │  - ConversionService (streaming progress)                 │   │
│  │  - LibraryService (CRUD for audiobooks)                   │   │
│  │  - ModelService (model loading/management)                │   │
│  └───────────────────────────────────────────────────────────┘   │
│                             │                                    │
│  ┌──────────────────────────┴───────────────────────────────┐   │
│  │              Existing Pipeline Modules                    │   │
│  │  - modules/pipeline/orchestrator.py                       │   │
│  │  - modules/tts/ (Kokoro, Orpheus engines)                 │   │
│  │  - modules/audio/ (encoder, packager)                     │   │
│  │  - modules/ingestion/ (PDF/EPUB parsers)                  │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Alternative Approaches Considered

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| **Keep Streamlit** | Zero migration work | Can't fix fundamental issues | ❌ Rejected |
| **Electron + React** | Cross-platform, web tech | Heavy, not native feel | ⚠️ Secondary option |
| **Tauri + React** | Lightweight, Rust backend | Still web tech in native wrapper | ⚠️ Secondary option |
| **SwiftUI + Python** | Native macOS, keeps Python ML | macOS only, more complex | ✅ **Recommended** |
| **Full Swift Rewrite** | Fully native, best performance | Lose all Python ML code | ❌ Too much work |

---

## 3. Detailed Implementation Plan

### Phase 1: Foundation (Week 1-2)

#### 3.1.1 Backend gRPC Service
```protobuf
// proto/audiobook.proto
syntax = "proto3";

service ConversionService {
  // Server streaming for real-time progress
  rpc ConvertBook(ConversionRequest) returns (stream ConversionProgress);
  rpc CancelConversion(CancelRequest) returns (CancelResponse);
  rpc GetModelStatus(Empty) returns (ModelStatus);
  rpc LoadModel(LoadModelRequest) returns (stream LoadProgress);
}

service LibraryService {
  rpc ListBooks(ListBooksRequest) returns (ListBooksResponse);
  rpc GetBook(GetBookRequest) returns (Book);
  rpc DeleteBook(DeleteBookRequest) returns (Empty);
  rpc StreamWaveform(WaveformRequest) returns (stream AudioChunk);
}

message ConversionRequest {
  string source_path = 1;
  string voice = 2;
  float speed = 3;
  ConversionOptions options = 4;
}

message ConversionProgress {
  enum Stage {
    IDLE = 0;
    PARSING = 1;
    CLEANING = 2;
    SYNTHESIZING = 3;
    ENCODING = 4;
    PACKAGING = 5;
    COMPLETE = 6;
    ERROR = 7;
  }
  
  Stage stage = 1;
  int32 chapter_index = 2;
  int32 total_chapters = 3;
  int32 chunk_index = 4;
  int32 total_chunks = 5;
  string message = 6;
  float progress_percent = 7;
  string eta_seconds = 8;
  
  // Real-time logs
  repeated LogEntry logs = 9;
}

message LogEntry {
  int64 timestamp_unix = 1;
  string level = 2;  // DEBUG, INFO, PROCESS, WARNING, ERROR
  string message = 3;
  string source = 4;
}
```

#### 3.1.2 Backend Service Implementation
```python
# backend/server.py
import asyncio
import grpc
from concurrent import futures

from modules.pipeline.orchestrator import ConversionPipeline, PipelineConfig

class ConversionServicer(ConversionServiceServicer):
    def __init__(self):
        self.active_conversions = {}
    
    async def ConvertBook(self, request, context):
        """Stream conversion progress to client."""
        queue = asyncio.Queue()
        
        def progress_callback(stage, chapter_idx, total_chapters, 
                             chunk_idx, total_chunks, message, eta):
            asyncio.create_task(queue.put(ConversionProgress(
                stage=stage.value,
                chapter_index=chapter_idx,
                total_chapters=total_chapters,
                chunk_index=chunk_idx,
                total_chunks=total_chunks,
                message=message,
                eta_seconds=str(eta) if eta else "--:--"
            )))
        
        def log_callback(message, level):
            asyncio.create_task(queue.put(LogEntry(
                timestamp_unix=time.time(),
                level=level,
                message=message
            )))
        
        # Run conversion in thread pool
        loop = asyncio.get_event_loop()
        conversion_task = loop.run_in_executor(
            None,  # Default executor
            self._run_conversion,
            request,
            progress_callback,
            log_callback
        )
        
        # Stream updates until complete
        while not conversion_task.done():
            try:
                update = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield update
            except asyncio.TimeoutError:
                continue
    
    def _run_conversion(self, request, progress_cb, log_cb):
        config = PipelineConfig(
            voice=request.voice,
            speed=request.speed
        )
        pipeline = ConversionPipeline(
            config=config,
            progress_callback=progress_cb,
            verbose_callback=log_cb
        )
        return pipeline.convert(request.source_path)
```

#### 3.1.3 SwiftUI Project Structure
```
AudiobookCreatorApp/
├── AudiobookCreatorApp.swift          # App entry point
├── Info.plist
├── Assets.xcassets/
│
├── Core/                              # Shared infrastructure
│   ├── AppState.swift                 # Global @Observable state
│   ├── Constants.swift
│   └── Extensions/
│
├── Networking/                        # gRPC client
│   ├── GRPCClient.swift
│   ├── ConversionService.swift
│   ├── LibraryService.swift
│   └── Models/
│       ├── ConversionModels.swift
│       └── LibraryModels.swift
│
├── Features/                          # Feature modules
│   ├── Conversion/                    # Main conversion UI
│   │   ├── ConversionView.swift
│   │   ├── ConversionViewModel.swift
│   │   ├── ProgressPanel.swift
│   │   ├── TerminalView.swift         # Native scrollback terminal
│   │   └── FileDropView.swift         # Drag & drop target
│   │
│   ├── Library/                       # Audiobook library
│   │   ├── LibraryView.swift
│   │   ├── BookGridView.swift
│   │   ├── BookDetailView.swift
│   │   └── BookCard.swift
│   │
│   ├── Player/                        # Audio player
│   │   ├── PlayerView.swift
│   │   ├── WaveformView.swift         # Real waveform viz
│   │   ├── ChapterList.swift
│   │   └── PlaybackControls.swift
│   │
│   ├── Settings/                      # App settings
│   │   ├── SettingsView.swift
│   │   ├── VoiceSelection.swift
│   │   └── ModelManagement.swift
│   │
│   └── Models/                        # Model manager
│       ├── ModelsView.swift
│       ├── ModelStatusCard.swift
│       └── DownloadProgress.swift
│
└── DesignSystem/                      # Reusable UI components
    ├── Colors.swift                   # Industrial Moss palette
    ├── Typography.swift
    ├── Buttons/
    ├── Progress/
    └── Panels/
```

---

### Phase 2: Core UI Components (Week 3-4)

#### 3.2.1 Terminal View (Native Scrollback)
```swift
// Features/Conversion/TerminalView.swift
import SwiftUI

struct TerminalView: View {
    @ObservedObject var viewModel: ConversionViewModel
    @State private var autoScroll = true
    
    var body: some View {
        VStack(spacing: 0) {
            // Terminal header
            HStack {
                Text("TERMINAL")
                    .font(.system(.caption, design: .monospaced))
                    .foregroundColor(.mossTextDim)
                
                Spacer()
                
                Toggle("Auto-scroll", isOn: $autoScroll)
                    .toggleStyle(.checkbox)
                    .font(.caption)
                
                Button("Clear") {
                    viewModel.clearLogs()
                }
                .font(.caption)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(Color.mossSurface)
            
            // Log entries with native scroll view
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 2) {
                        ForEach(viewModel.logs) { entry in
                            LogEntryView(entry: entry)
                                .id(entry.id)
                        }
                    }
                    .padding(8)
                }
                .background(Color.mossCore)
                .font(.system(.caption, design: .monospaced))
                .onChange(of: viewModel.logs) { _ in
                    if autoScroll, let last = viewModel.logs.last {
                        withAnimation {
                            proxy.scrollTo(last.id, anchor: .bottom)
                        }
                    }
                }
            }
        }
        .border(Color.mossBorder, width: 1)
    }
}

struct LogEntryView: View {
    let entry: LogEntry
    
    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Text(entry.timestampFormatted)
                .foregroundColor(.mossTextFaded)
            
            Text("[\(entry.level)]")
                .foregroundColor(entry.levelColor)
                .frame(width: 70, alignment: .leading)
            
            Text(entry.message)
                .foregroundColor(entry.levelColor)
            
            Spacer()
        }
    }
}
```

#### 3.2.2 Real Progress Tracking
```swift
// Features/Conversion/ProgressPanel.swift
import SwiftUI

struct ProgressPanel: View {
    @ObservedObject var viewModel: ConversionViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Stage indicator
            HStack {
                StageIndicator(stage: viewModel.currentStage)
                Spacer()
                if let eta = viewModel.eta {
                    Text("ETA: \(eta)")
                        .font(.system(.caption, design: .monospaced))
                        .foregroundColor(.mossTextDim)
                }
            }
            
            // Overall progress
            VStack(alignment: .leading, spacing: 4) {
                Text("Overall Progress")
                    .font(.system(.caption, design: .monospaced))
                    .foregroundColor(.mossTextDim)
                
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        Rectangle()
                            .fill(Color.mossBorder)
                        
                        Rectangle()
                            .fill(Color.mossAccent)
                            .frame(width: geo.size.width * viewModel.overallProgress)
                    }
                }
                .frame(height: 8)
                
                Text("\(viewModel.completedChapters)/\(viewModel.totalChapters) chapters")
                    .font(.caption2)
                    .foregroundColor(.mossTextFaded)
            }
            
            // Per-chapter progress list
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 4) {
                    ForEach(viewModel.chapters) { chapter in
                        ChapterProgressRow(chapter: chapter)
                    }
                }
            }
            .frame(maxHeight: 200)
        }
        .padding()
        .background(Color.mossSurface)
        .border(Color.mossBorder, width: 1)
    }
}

struct ChapterProgressRow: View {
    let chapter: ChapterProgress
    
    var body: some View {
        HStack(spacing: 8) {
            // Status icon
            Image(systemName: chapter.statusIcon)
                .foregroundColor(chapter.statusColor)
                .frame(width: 16)
            
            // Chapter number
            Text(String(format: "%02d", chapter.number))
                .font(.system(.caption, design: .monospaced))
                .foregroundColor(.mossTextDim)
            
            // Chapter title
            Text(chapter.title)
                .font(.system(.caption, design: .monospaced))
                .lineLimit(1)
            
            Spacer()
            
            // Mini progress bar for active chapter
            if chapter.isProcessing {
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        Rectangle().fill(Color.mossBorder)
                        Rectangle()
                            .fill(Color.mossAccent)
                            .frame(width: geo.size.width * chapter.progress)
                    }
                }
                .frame(width: 60, height: 4)
                
                Text("\(Int(chapter.progress * 100))%")
                    .font(.caption2)
                    .foregroundColor(.mossTextFaded)
                    .frame(width: 30)
            }
        }
        .padding(.vertical, 2)
    }
}
```

#### 3.2.3 Native Drag & Drop
```swift
// Features/Conversion/FileDropView.swift
import SwiftUI
import UniformTypeIdentifiers

struct FileDropView: View {
    @ObservedObject var viewModel: ConversionViewModel
    @State private var isDropTarget = false
    
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 0)
                .fill(isDropTarget ? Color.mossAccent.opacity(0.1) : Color.mossSurface)
                .border(
                    isDropTarget ? Color.mossAccent : Color.mossBorder,
                    width: isDropTarget ? 2 : 1
                )
            
            if let file = viewModel.selectedFile {
                // Show selected file
                VStack(spacing: 12) {
                    Image(systemName: file.iconName)
                        .font(.system(size: 48))
                        .foregroundColor(.mossAccent)
                    
                    Text(file.name)
                        .font(.system(.body, design: .monospaced))
                        .foregroundColor(.mossTextMain)
                    
                    Text(file.formattedSize)
                        .font(.caption)
                        .foregroundColor(.mossTextDim)
                    
                    HStack(spacing: 16) {
                        Button("Change File") {
                            viewModel.showFilePicker()
                        }
                        
                        Button("Start Conversion") {
                            viewModel.startConversion()
                        }
                        .buttonStyle(.primary)
                    }
                }
            } else {
                // Drop target
                VStack(spacing: 16) {
                    Image(systemName: "arrow.down.document")
                        .font(.system(size: 48))
                        .foregroundColor(isDropTarget ? .mossAccent : .mossTextDim)
                    
                    Text("Drop PDF or EPUB here")
                        .font(.system(.body, design: .monospaced))
                        .foregroundColor(.mossTextMain)
                    
                    Text("or click to browse")
                        .font(.caption)
                        .foregroundColor(.mossTextDim)
                    
                    Button("Select File") {
                        viewModel.showFilePicker()
                    }
                    .padding(.top, 8)
                }
            }
        }
        .frame(height: 200)
        .onDrop(of: [.pdf, .epub], isTargeted: $isDropTarget) { providers in
            handleDrop(providers)
        }
    }
    
    private func handleDrop(_ providers: [NSItemProvider]) -> Bool {
        // Handle file drop from Finder
        for provider in providers {
            provider.loadFileRepresentation(forTypeIdentifier: UTType.pdf.identifier) { url, _ in
                if let url = url {
                    DispatchQueue.main.async {
                        viewModel.selectFile(url)
                    }
                }
            }
        }
        return true
    }
}
```

---

### Phase 3: Advanced Features (Week 5-6)

#### 3.3.1 Waveform Visualization
```swift
// Features/Player/WaveformView.swift
import SwiftUI
import Accelerate

struct WaveformView: View {
    let audioURL: URL
    @State private var samples: [Float] = []
    @State private var progress: Double = 0
    
    var body: some View {
        GeometryReader { geometry in
            Canvas { context, size in
                guard !samples.isEmpty else { return }
                
                let width = size.width
                let height = size.height
                let midY = height / 2
                
                // Calculate bar parameters
                let barWidth: CGFloat = 2
                let barSpacing: CGFloat = 1
                let totalBars = Int(width / (barWidth + barSpacing))
                let samplesPerBar = samples.count / totalBars
                
                // Draw waveform bars
                for i in 0..<totalBars {
                    let startSample = i * samplesPerBar
                    let endSample = min(startSample + samplesPerBar, samples.count)
                    let slice = Array(samples[startSample..<endSample])
                    
                    // RMS for this segment
                    let rms = calculateRMS(slice)
                    let barHeight = CGFloat(rms) * height
                    
                    let x = CGFloat(i) * (barWidth + barSpacing)
                    let y = midY - barHeight / 2
                    
                    var barPath = Path()
                    barPath.addRect(CGRect(x: x, y: y, width: barWidth, height: barHeight))
                    
                    // Color based on playback position
                    let isPlayed = Double(i) / Double(totalBars) < progress
                    context.fill(barPath, with: .color(isPlayed ? .mossAccent : .mossBorder))
                }
                
                // Playhead line
                let playheadX = width * CGFloat(progress)
                var playheadPath = Path()
                playheadPath.move(to: CGPoint(x: playheadX, y: 0))
                playheadPath.addLine(to: CGPoint(x: playheadX, y: height))
                context.stroke(playheadPath, with: .color(.mossAccent), lineWidth: 2)
            }
        }
        .task {
            await loadAudioSamples()
        }
    }
    
    private func calculateRMS(_ samples: [Float]) -> Float {
        var meanSquare: Float = 0
        vDSP_measqv(samples, 1, &meanSquare, vDSP_Length(samples.count))
        return sqrt(meanSquare)
    }
}
```

#### 3.3.2 Library Browser (Finder-like)
```swift
// Features/Library/LibraryView.swift
import SwiftUI

struct LibraryView: View {
    @StateObject private var viewModel = LibraryViewModel()
    @State private var selectedView: LibraryViewMode = .grid
    @State private var searchText = ""
    
    var body: some View {
        VStack(spacing: 0) {
            // Toolbar
            HStack {
                Picker("View", selection: $selectedView) {
                    Image(systemName: "square.grid.2x2").tag(LibraryViewMode.grid)
                    Image(systemName: "list.bullet").tag(LibraryViewMode.list)
                }
                .pickerStyle(.segmented)
                .frame(width: 100)
                
                SearchField(text: $searchText)
                    .frame(maxWidth: 300)
                
                Spacer()
                
                Text("\(viewModel.books.count) audiobooks")
                    .font(.caption)
                    .foregroundColor(.mossTextDim)
            }
            .padding()
            
            // Content
            Group {
                switch selectedView {
                case .grid:
                    BookGridView(books: filteredBooks)
                case .list:
                    BookListView(books: filteredBooks)
                }
            }
        }
        .background(Color.mossCore)
    }
    
    private var filteredBooks: [Audiobook] {
        if searchText.isEmpty { return viewModel.books }
        return viewModel.books.filter {
            $0.title.localizedCaseInsensitiveContains(searchText) ||
            $0.author.localizedCaseInsensitiveContains(searchText)
        }
    }
}
```

---

### Phase 4: Polish & Distribution (Week 7-8)

#### 3.4.1 Menu Bar Integration
```swift
// Core/MenuBarController.swift
import SwiftUI

class MenuBarController: ObservableObject {
    var statusItem: NSStatusItem?
    
    func setup() {
        statusItem = NSStatusBar.shared.statusItem(withLength: NSStatusItem.variableLength)
        statusItem?.button?.image = NSImage(systemSymbolName: "book.closed", accessibilityDescription: "Audiobook Creator")
        
        let menu = NSMenu()
        menu.addItem(withTitle: "Open", action: #selector(openApp), keyEquivalent: "o")
        menu.addItem(NSMenuItem.separator())
        menu.addItem(withTitle: "Convert File...", action: #selector(convertFile), keyEquivalent: "n")
        menu.addItem(NSMenuItem.separator())
        menu.addItem(withTitle: "Quit", action: #selector(NSApp.terminate), keyEquivalent: "q")
        
        statusItem?.menu = menu
    }
    
    @objc private func openApp() {
        NSApp.activate(ignoringOtherApps: true)
    }
}
```

#### 3.4.2 App Bundle Structure
```
Audiobook Creator.app/
└── Contents/
    ├── Info.plist
    ├── MacOS/
    │   ├── Audiobook Creator      # SwiftUI binary
    │   └── python_backend/        # Embedded Python
    │       ├── bin/python3.11
    │       ├── lib/
    │       ├── backend_server.py
    │       └── modules/           # Your existing modules
    └── Resources/
        ├── Assets.car
        └── models/                # Pre-downloaded models (optional)
```

---

## 4. Communication Protocol

### 4.1 Real-time Streaming Flow
```
┌──────────┐                    ┌──────────┐
│  SwiftUI │ ──ConvertBook()──► │  gRPC    │
│  Client  │                    │  Server  │
│          │ ◄────Stream────── │          │
│          │   ProgressUpdate   │          │
│          │ ◄────Stream────── │          │
│          │   LogEntry         │          │
│          │ ◄────Stream────── │          │
│          │   Completion       │          │
└──────────┘                    └──────────┘
         │                            │
         │                            ▼
         │                    ┌──────────┐
         │                    │ Pipeline │
         │                    │ Thread   │
         │                    └──────────┘
```

### 4.2 State Synchronization
```swift
// Networking/GRPCClient.swift
class GRPCClient: ObservableObject {
    @Published var connectionState: ConnectionState = .disconnected
    @Published var modelStatus: ModelStatus = .unknown
    
    private var conversionStream: GRPCAsyncServerStreamingCall<ConversionRequest, ConversionProgress>?
    
    func startConversion(request: ConversionRequest) async throws {
        conversionStream = conversionService.convertBook(request)
        
        for try await update in conversionStream!.responses {
            await MainActor.run {
                handleUpdate(update)
            }
        }
    }
    
    private func handleUpdate(_ update: ConversionProgress) {
        // Update published properties - SwiftUI auto-refreshes
        currentStage = update.stage
        overallProgress = update.progressPercent
        
        // Append logs
        for log in update.logs {
            logs.append(LogEntry(from: log))
        }
    }
}
```

---

## 5. Migration Strategy

### 5.1 Gradual Migration Path
```
Week 1-2:  Backend gRPC service + SwiftUI shell
Week 3-4:  File drop + Progress panel + Terminal
Week 5-6:  Library + Player + Waveform
Week 7-8:  Settings + Menu bar + App packaging
Week 9+:   Polish, beta testing, release
```

### 5.2 Risk Mitigation
| Risk | Mitigation |
|------|------------|
| Python backend complexity | Keep existing modules, only add thin gRPC wrapper |
| SwiftUI learning curve | Start with simple views, iterate |
| gRPC performance issues | Use streaming, compress audio for waveform |
| App size (embedded Python) | Make Python backend optional download |
| macOS version compatibility | Target macOS 13+ (Ventura) |

---

## 6. Design System: Industrial Moss for SwiftUI

```swift
// DesignSystem/Colors.swift
import SwiftUI

extension Color {
    // Core
    static let mossCore = Color(hex: "#1a1b1a")
    static let mossSurface = Color(hex: "#282828")
    static let mossElevated = Color(hex: "#32302f")
    
    // Borders
    static let mossBorder = Color(hex: "#3c3836")
    static let mossBorderFocus = Color(hex: "#504945")
    
    // Text
    static let mossTextMain = Color(hex: "#d5c4a1")
    static let mossTextDim = Color(hex: "#a89984")
    static let mossTextFaded = Color(hex: "#7c6f64")
    
    // Accents
    static let mossAccent = Color(hex: "#859900")      // Olive
    static let mossGold = Color(hex: "#b57614")       // Warning
    static let mossRust = Color(hex: "#af3a03")       // Error
}
```

---

## 7. Development Setup

### 7.1 Prerequisites
```bash
# macOS development
xcode-select --install  # Xcode command line tools
brew install swift-protobuf grpc-swift  # gRPC for Swift

# Python backend (existing)
cd /Users/main/Developer/Audiobook
python -m venv venv
source venv/bin/activate
pip install grpcio grpcio-tools  # Add to requirements.txt
```

### 7.2 Project Initialization
```bash
# Create SwiftUI project
mkdir -p /Users/main/Developer/Audiobook/swift-ui

cd /Users/main/Developer/Audiobook/swift-ui
swift package init --type executable --name AudiobookCreator

# Add dependencies to Package.swift
# - SwiftUI (built-in)
# - grpc-swift
# - SwiftProtobuf
```

---

## 8. Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| UI frame rate during conversion | ~5 FPS | 60 FPS |
| Terminal scrollback | ~100 lines | 10,000+ lines |
| Progress update latency | 1-2s | <100ms |
| File selection | Click + browse | Drag & drop |
| Audio player | Basic HTML | Native with waveform |
| App launch time | 3-5s (Python startup) | <1s |

---

## Appendix A: Alternative Lightweight Approach

If the full SwiftUI migration is too ambitious, consider **improving the Streamlit UI first**:

1. **Use `st.experimental_fragment`** for partial rerenders
2. **WebSocket-based** real-time updates via `streamlit-webrtc`
3. **Custom React components** with `streamlit-component-lib`
4. **PyQt6/PySide6** as a middle ground (native widgets, Python code)

However, these are band-aids. The hybrid SwiftUI approach is the long-term solution.
