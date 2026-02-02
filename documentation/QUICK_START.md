# Audiobook Creator SwiftUI - Quick Start

## 🚀 Run Everything (Step by Step)

### Step 1: Install gRPC (One-time setup)

```bash
cd /Users/main/Developer/Audiobook
source venv/bin/activate
pip install grpcio grpcio-tools
```

### Step 2: Start the Backend

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
🔧 Pipeline available: True/False (depending on imports)
============================================================
```

### Step 3: Run the SwiftUI App (New Terminal)

```bash
cd /Users/main/Developer/Audiobook/swift-ui
swift run
```

The app will open with:
- **Left panel**: File drop + voice settings
- **Middle panel**: Progress + model status
- **Right panel**: Terminal with live logs

## 🎮 Using the App

1. **Drop a file**: Drag PDF or EPUB into the drop zone
2. **Select voice**: Choose from 6 voices in the dropdown
3. **Adjust speed**: Use the slider (0.5x - 2.0x)
4. **Click Convert**: Watch real-time progress
5. **Monitor logs**: See live output in the terminal

## ✅ What's Working

| Feature | Status |
|---------|--------|
| gRPC Server | ✅ Fully implemented |
| SwiftUI App | ✅ Building & running |
| File Drop | ✅ Drag & drop from Finder |
| Voice Selection | ✅ 6 voices |
| Speed Control | ✅ 0.5x - 2.0x |
| Progress Streaming | ✅ Real-time updates |
| Terminal | ✅ 10,000+ line buffer |
| Model Status | ✅ Live monitoring |
| Simulated Conversion | ✅ Demo mode working |
| Real Pipeline | ✅ Auto-detects if available |

## 🛠️ Troubleshooting

### "No module named 'grpc'"
```bash
pip install grpcio grpcio-tools
```

### "No module named 'audiobook_pb2'"
This was a bug in the generated imports. It's now fixed. If you still see it:
```bash
cd swift-ui/BackendGRPC/generated
# The import in audiobook_pb2_grpc.py should be:
# from . import audiobook_pb2 as audiobook__pb2
```

### Port already in use
```bash
lsof -i :50051
kill -9 $(lsof -t -i :50051)
```

### Swift build fails
```bash
cd swift-ui
rm -rf .build
swift build
```

### Python module not found
```bash
cd /Users/main/Developer/Audiobook
source venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:swift-ui/BackendGRPC"
python swift-ui/BackendGRPC/server.py
```

## 📚 Documentation

- `swift-ui/README.md` - Project overview
- `documentation/UI_REVAMP_PLAN.md` - Full architecture plan
- `documentation/SWIFT_UI_SETUP.md` - Detailed setup guide

## 🎯 Next Steps

1. **Test with real pipeline**: Ensure your Python modules are importable
2. **Library Browser**: Add LibraryView.swift for audiobook library
3. **Audio Player**: Add PlayerView.swift with waveform
4. **Settings**: Add SettingsView.swift for configuration
5. **App Bundle**: Package as .app for distribution
