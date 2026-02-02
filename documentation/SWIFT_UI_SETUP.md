# SwiftUI Frontend Setup Guide

Complete guide for setting up and running the Audiobook Creator SwiftUI frontend.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Installation](#installation)
4. [Running the System](#running-the-system)
5. [Development Workflow](#development-workflow)
6. [Troubleshooting](#troubleshooting)

---

## Overview

The SwiftUI frontend provides a native macOS interface for the Audiobook Creator with:

- **Real-time streaming** via gRPC
- **Native 60fps UI** (vs ~5fps in Streamlit)
- **10,000+ line terminal buffer**
- **Drag & drop file selection**
- **Live model status monitoring**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  SWIFTUI FRONTEND (macOS 13+)                                   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐    │
│  │ File Drop    │ │ Progress     │ │ Terminal             │    │
│  │ Voice Select │ │ Model Status │ │ (Native scrollback)  │    │
│  └──────┬───────┘ └──────┬───────┘ └──────────┬───────────┘    │
│         │                │                    │                 │
│  ┌──────┴────────────────┴────────────────────┴────────────┐   │
│  │  SwiftUI + Combine (@MainActor)                          │   │
│  └───────────────────────────┬──────────────────────────────┘   │
│                              │ gRPC/protobuf                    │
└──────────────────────────────┼──────────────────────────────────┘
                               │ localhost:50051
┌──────────────────────────────┼──────────────────────────────────┐
│  PYTHON BACKEND              │                                  │
│  ┌───────────────────────────┴─────────────────────────────┐    │
│  │  gRPC Server (grpcio)                                   │    │
│  │  - ConversionService (streaming)                       │    │
│  │  - ModelService (status)                               │    │
│  │  - LibraryService (CRUD)                               │    │
│  └───────────────────────────┬─────────────────────────────┘    │
│                              │                                   │
│  ┌───────────────────────────┴─────────────────────────────┐    │
│  │  Existing Pipeline (modules/)                            │    │
│  │  - pipeline/orchestrator.py                              │    │
│  │  - tts/ (Kokoro, Orpheus)                                │    │
│  │  - audio/ (encoder, packager)                            │    │
│  │  - ingestion/ (PDF, EPUB parsers)                        │    │
│  └──────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Installation

### Step 1: System Requirements

- **macOS 13.0+** (Ventura)
- **Xcode 15.0+** or Command Line Tools
- **Python 3.11+**
- **Swift 5.9+**

Verify Swift installation:
```bash
swift --version
```

### Step 2: Install gRPC Tools

```bash
# Activate your audiobook environment
cd /Users/main/Developer/Audiobook
source venv/bin/activate

# Install gRPC
pip install grpcio grpcio-tools

# Verify installation
python -c "import grpc; print(grpc.__version__)"
```

### Step 3: Generate Protobuf Code

```bash
cd swift-ui

# Create directories
mkdir -p BackendGRPC/generated
mkdir -p Sources/AudiobookCreator/Protobuf

# Generate Python code
python -m grpc_tools.protoc \
  --python_out=BackendGRPC/generated \
  --grpc_python_out=BackendGRPC/generated \
  --proto_path=proto \
  proto/audiobook.proto

# Verify generated files
ls BackendGRPC/generated/
# Output: audiobook_pb2.py  audiobook_pb2_grpc.py
```

### Step 4: Build Swift Project

```bash
cd swift-ui

# Resolve dependencies (first time only)
swift package resolve

# Build
swift build

# This will download:
# - grpc-swift
# - swift-protobuf
# - swift-nio
# ... (may take 5-10 minutes first time)
```

---

## Running the System

### Terminal 1: Start Backend

```bash
cd /Users/main/Developer/Audiobook
source venv/bin/activate

python swift-ui/BackendGRPC/server.py
```

Expected output:
```
============================================================
🚀 Audiobook Creator gRPC Server
📡 Listening on port 50051
🔧 Pipeline available: True
============================================================
```

### Terminal 2: Run SwiftUI App

```bash
cd /Users/main/Developer/Audiobook/swift-ui
swift run
```

The app will:
1. Connect to localhost:50051
2. Show the main interface
3. Start receiving model status updates

---

## Development Workflow

### Making Changes to Proto

1. Edit `proto/audiobook.proto`

2. Regenerate code:
```bash
cd swift-ui

# Python
python -m grpc_tools.protoc \
  --python_out=BackendGRPC/generated \
  --grpc_python_out=BackendGRPC/generated \
  --proto_path=proto \
  proto/audiobook.proto

# Swift (manual update or use protoc)
# Edit Sources/AudiobookCreator/Protobuf/audiobook.pb.swift
```

3. Rebuild:
```bash
swift build
```

### Adding New UI Components

1. Create view in `Sources/AudiobookCreator/Features/`
2. Add to `ContentView.swift` navigation
3. Update `ConversionViewModel.swift` if needed
4. Test with `swift run`

### Debugging

Enable verbose logging in Python:
```python
# In BackendGRPC/server.py
logging.basicConfig(level=logging.DEBUG)
```

Enable gRPC tracing in Swift:
```swift
// In GRPCClient.swift
var logger = Logger(label: "grpc")
logger.logLevel = .debug
```

---

## Troubleshooting

### Issue: "No such module 'GRPC'"

**Cause:** Dependencies not downloaded

**Fix:**
```bash
cd swift-ui
swift package resolve
swift build
```

### Issue: "Port 50051 already in use"

**Fix:**
```bash
# Find process
lsof -i :50051

# Kill it
kill -9 $(lsof -t -i :50051)

# Or use different port
python swift-ui/BackendGRPC/server.py --port 50052
```

### Issue: "Cannot find type 'Audiobook_...'"

**Cause:** Protobuf types not generated

**Fix:**
```bash
cd swift-ui
# Copy the protobuf types from documentation or regenerate
# The types are in: Sources/AudiobookCreator/Protobuf/audiobook.pb.swift
```

### Issue: Build takes forever

**Cause:** First build downloads many dependencies

**Fix:** Be patient! Initial build takes 5-10 minutes. Subsequent builds are fast.

### Issue: "Module compiled with Swift 5.x cannot be imported"

**Cause:** Swift version mismatch

**Fix:**
```bash
# Clean build
rm -rf .build
swift build
```

### Issue: Python "No module named 'generated'"

**Cause:** Python path issue

**Fix:**
```bash
cd /Users/main/Developer/Audiobook
source venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:swift-ui/BackendGRPC"
python swift-ui/BackendGRPC/server.py
```

---

## File Structure Reference

```
swift-ui/
├── Package.swift                    # Dependencies: grpc-swift, swift-protobuf
├── proto/
│   └── audiobook.proto             # Service definitions
├── BackendGRPC/
│   ├── generated/                  # Auto-generated Python
│   │   ├── audiobook_pb2.py
│   │   └── audiobook_pb2_grpc.py
│   └── server.py                   # gRPC server implementation
└── Sources/AudiobookCreator/
    ├── Protobuf/
    │   └── audiobook.pb.swift      # Swift protobuf types
    ├── Networking/
    │   └── GRPCClient.swift        # gRPC client
    ├── Features/Conversion/
    │   ├── ConversionView.swift    # Main UI
    │   ├── ConversionViewModel.swift
    │   ├── TerminalView.swift
    │   ├── ProgressPanel.swift
    │   └── ModelStatusPanel.swift
    ├── DesignSystem/
    │   └── Colors.swift            # Industrial Moss theme
    ├── AudiobookCreatorApp.swift
    └── ContentView.swift
```

---

## Performance Tips

1. **Use Release Build for Testing:**
   ```bash
   swift build -c release
   .build/release/AudiobookCreator
   ```

2. **Enable Compiler Optimizations:**
   ```swift
   // In Package.swift
   swiftSettings: [
       .unsafeFlags(["-O", "-whole-module-optimization"])
   ]
   ```

3. **Profile with Instruments:**
   - Build in Xcode
   - Use Product > Profile
   - Check for memory leaks and performance bottlenecks

---

## Next Steps

1. **Library Browser:** Implement `LibraryView.swift`
2. **Audio Player:** Add `PlayerView.swift` with waveform
3. **Settings:** Create `SettingsView.swift`
4. **App Packaging:** Create `.app` bundle for distribution

See `UI_REVAMP_PLAN.md` for full roadmap.
