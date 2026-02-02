# Audiobook Creator - SwiftUI Frontend

Native macOS frontend for Audiobook Creator with real-time gRPC streaming.

## 🚀 Quick Start

### Prerequisites

- **macOS 13.0+** (Ventura)
- **Xcode 15.0+** or Command Line Tools
- **Python 3.11+** with your existing audiobook environment

### 1. Start the Backend Server

```bash
# From the project root
cd /Users/main/Developer/Audiobook

# Activate your Python environment
source venv/bin/activate

# Install gRPC if not already installed
pip install grpcio grpcio-tools

# Start the gRPC server
python swift-ui/BackendGRPC/server.py
```

You should see:
```
============================================================
🚀 Audiobook Creator gRPC Server
📡 Listening on port 50051
🔧 Pipeline available: True
============================================================
```

### 2. Build and Run the SwiftUI App

```bash
# In another terminal
cd /Users/main/Developer/Audiobook/swift-ui

# Build
swift build

# Run
swift run
```

The app will open with the native macOS interface.

## 📁 Project Structure

```
swift-ui/
├── Package.swift                    # Swift Package Manager config
├── proto/
│   └── audiobook.proto             # gRPC service definitions
├── BackendGRPC/
│   ├── generated/                  # Generated Python protobuf code
│   │   ├── audiobook_pb2.py
│   │   └── audiobook_pb2_grpc.py
│   └── server.py                   # Python gRPC server
└── Sources/AudiobookCreator/
    ├── AudiobookCreatorApp.swift   # App entry point
    ├── ContentView.swift           # Main layout
    ├── Protobuf/
    │   └── audiobook.pb.swift      # Swift protobuf types
    ├── DesignSystem/
    │   └── Colors.swift            # Industrial Moss theme
    ├── Features/Conversion/
    │   ├── ConversionView.swift    # Main UI
    │   ├── ConversionViewModel.swift
    │   ├── TerminalView.swift      # Native terminal
    │   ├── ProgressPanel.swift
    │   ├── ModelStatusPanel.swift
    │   └── Models.swift
    └── Networking/
        └── GRPCClient.swift        # gRPC client
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SWIFTUI FRONTEND                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ File Drop   │  │ Progress    │  │ Terminal            │  │
│  │ Voice Select│  │ Model Status│  │ (10k+ lines)        │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │             │
│  ┌──────┴────────────────┴─────────────────────┴─────────┐  │
│  │              SwiftUI + Combine (@MainActor)           │  │
│  └──────────────────────────┬────────────────────────────┘  │
│                             │ gRPC (protobuf)                │
└─────────────────────────────┼────────────────────────────────┘
                              │ localhost:50051
┌─────────────────────────────┼────────────────────────────────┐
│                      PYTHON BACKEND                          │
│  ┌──────────────────────────┴─────────────────────────────┐  │
│  │              gRPC Server (grpcio + threading)           │  │
│  │  - ConversionService (streaming progress)              │  │
│  │  - ModelService (status streaming)                     │  │
│  │  - LibraryService (audiobook CRUD)                     │  │
│  └─────────────────────────────────────────────────────────┘  │
│                              │                                │
│  ┌───────────────────────────┴────────────────────────────┐  │
│  │              Existing Pipeline Modules                  │  │
│  │  - modules/pipeline/orchestrator.py                    │  │
│  │  - modules/tts/ (Kokoro/Orpheus engines)               │  │
│  │  - modules/audio/ (encoder, packager)                  │  │
│  │  - modules/ingestion/ (PDF/EPUB parsers)               │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 🔌 gRPC Services

### ConversionService

```protobuf
service ConversionService {
  rpc ConvertBook(ConversionRequest) returns (stream ConversionProgress);
  rpc CancelConversion(CancelRequest) returns (CancelResponse);
  rpc GetConversionStatus(Empty) returns (ConversionStatus);
}
```

**Features:**
- Real-time streaming of conversion progress
- Per-chapter progress updates
- Live log streaming to terminal
- Cancellation support

### ModelService

```protobuf
service ModelService {
  rpc GetModelStatus(Empty) returns (ModelStatus);
  rpc LoadModel(LoadModelRequest) returns (stream LoadProgress);
  rpc UnloadModel(UnloadModelRequest) returns (Empty);
  rpc StreamModelStatus(Empty) returns (stream ModelStatus);
}
```

**Features:**
- Real-time model loading status
- VRAM usage monitoring
- Load/unload model on demand

### LibraryService

```protobuf
service LibraryService {
  rpc ListBooks(ListBooksRequest) returns (ListBooksResponse);
  rpc GetBook(GetBookRequest) returns (Book);
  rpc DeleteBook(DeleteBookRequest) returns (Empty);
  rpc StreamAudio(StreamAudioRequest) returns (stream AudioChunk);
  rpc GetWaveform(WaveformRequest) returns (WaveformData);
}
```

**Features:**
- Audiobook library management
- Audio streaming for playback
- Waveform data for visualization

## 🎨 UI Features

### Native macOS Design
- **60fps** smooth updates (vs ~5fps in Streamlit)
- Native scrollback terminal with **10,000+ line buffer**
- Drag & drop file selection from Finder
- Native audio player with waveform visualization

### Real-Time Progress
- Stage indicator with live updates
- Per-chapter progress bars
- ETA estimation
- Log streaming to terminal

### Model Management
- Live model status display
- TTS and Cleaner model cards
- VRAM usage monitoring
- Active model highlighting

## 🛠️ Development

### Rebuild Protobuf Code

After modifying `proto/audiobook.proto`:

```bash
# Python
cd swift-ui
python -m grpc_tools.protoc \
  --python_out=BackendGRPC/generated \
  --grpc_python_out=BackendGRPC/generated \
  --proto_path=proto \
  proto/audiobook.proto

# Swift (requires swift-protobuf plugin)
protoc --swift_out=Sources/AudiobookCreator/Protobuf \
  --proto_path=proto \
  proto/audiobook.proto
```

### Running Tests

```bash
cd swift-ui
swift test
```

### Building for Release

```bash
cd swift-ui
swift build -c release
```

The binary will be at `.build/release/AudiobookCreator`.

## 📊 Performance Comparison

| Feature | Streamlit | SwiftUI |
|---------|-----------|---------|
| Frame rate | ~5 FPS | 60 FPS |
| Terminal scrollback | ~100 lines | 10,000+ lines |
| Progress latency | 1-2s | <100ms |
| File selection | Click + browse | Drag & drop |
| Audio player | Basic HTML | Native with waveform |
| App launch time | 3-5s | <1s |

## 🔧 Troubleshooting

### Backend won't start

```bash
# Check if port 50051 is in use
lsof -i :50051

# Kill existing process
kill -9 $(lsof -t -i :50051)
```

### Swift build fails

```bash
# Clean build
cd swift-ui
rm -rf .build
swift build
```

### gRPC connection failed

1. Make sure backend is running:
   ```bash
   python swift-ui/BackendGRPC/server.py
   ```

2. Check firewall settings for localhost:50051

3. Verify protobuf code is generated:
   ```bash
   ls swift-ui/BackendGRPC/generated/
   ```

## 📝 License

Same as parent project.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request
