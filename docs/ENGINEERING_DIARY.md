# Engineering Diary

> A living document capturing development decisions, solutions, and architecture evolution.
> 
> **Project**: Audiobook Creator - PDF/EPUB to Audiobook converter using Apple Silicon MLX

---

## Project Vision

Convert PDF and EPUB books into high-quality audiobooks using local AI models on Apple Silicon, optimized for 16GB unified memory Macs.

### Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Streamlit UI                            │
│  (Upload → Configure → Generate → Export)                   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Pipeline Orchestrator                    │
│  (Sequential model loading, VRAM management)                │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
    ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
    │ Ingest  │         │   TTS   │         │  Audio  │
    │ Module  │         │  Engine │         │ Process │
    └─────────┘         └─────────┘         └─────────┘
    PDF/EPUB→Text      Text→Speech         Merge/Export
```

---

## 2026-01-28 - Phase 2: TTS Integration (Session 1)

### Tasks Completed

From `tasks/02_TTS_INTEGRATION.md`:

**2.1 Kokoro-82M TTS Engine**
- [x] Create `modules/tts/engine.py`
- [x] Implement `TTSEngine` class with load/synthesize/unload
- [x] Test basic synthesis with short text
- [x] Verify model download (bf16 variant, ~361MB)

**2.2 Text Chunking**
- [x] Create `modules/tts/chunker.py`
- [x] Implement `TextChunker` class with sentence boundary detection
- [x] Handle edge cases (quotes, dialogue)
- [x] Test with long chapter text (~950 chars → 3 chunks)

**2.4 VRAM Management**
- [x] Create `modules/tts/memory.py` utility
- [x] Implement `clear_vram()` function
- [x] Test memory freed after TTS unload (312MB → 0MB)
- [x] Ensure sequential model loading via VRAMManager singleton

**2.5 Voice Selection (partial)**
- [x] Create `config/voices.py` with presets and speed config

---

### Challenges & Solutions

#### Challenge 1: mlx-audio Model Authentication Error

**Problem**: Initial model path `lucasnewman/kokoro-mlx-4bit` returned 401 Unauthorized.

**Investigation**: Web search revealed the model was renamed/moved.

**Solution**: Updated to public repository `mlx-community/Kokoro-82M-bf16`.

**Code change** in `engine.py`:
```python
# Before
model_name: str = "lucasnewman/kokoro-mlx"

# After
model_name: str = "mlx-community/Kokoro-82M"
```

---

#### Challenge 2: generate_audio() Returns None

**Problem**: TTS test failed with "object of type 'NoneType' has no len()". The `generate_audio()` function from mlx-audio returns `None`.

**Investigation**: Checked function signature - it writes to files, doesn't return audio array.

```python
# API signature
def generate_audio(..., output_path: Optional[str] = None) -> None
```

**Solution**: Use temporary directory, let mlx-audio save file, then read it back:

```python
def synthesize(self, text, voice, speed):
    with tempfile.TemporaryDirectory() as temp_dir:
        generate_audio(
            text=text,
            model=self._model_path,
            voice=voice,
            output_path=temp_dir,
            file_prefix="tts_output",
            verbose=False
        )
        # Find and read the generated file
        wav_files = [f for f in os.listdir(temp_dir) if f.endswith('.wav')]
        audio_path = os.path.join(temp_dir, wav_files[0])
        audio, _ = sf.read(audio_path, dtype='float32')
        return audio
```

**Lesson**: Always verify external library APIs - documentation may be outdated or incomplete.

---

#### Challenge 3: Missing Dependencies

**Problem**: Cascading import errors when loading Kokoro model:
```
ModuleNotFoundError: No module named 'misaki'
ModuleNotFoundError: No module named 'num2words'
ModuleNotFoundError: No module named 'spacy'
```

**Solution**: Install with extras:
```bash
pip install "misaki[en]"  # Includes spacy, num2words, etc.
```

The model also downloads spaCy language model on first run:
```
python -m spacy download en_core_web_sm
```

**Lesson**: MLX-audio's Kokoro support has undocumented dependencies.

---

#### Challenge 4: Quantized Models Compatibility

**Problem**: 6-bit model failed with shape mismatch:
```
ValueError: Expected shape (512, 3, 512) but received shape (512, 512, 3)
```

**Investigation**: The quantized models on mlx-community may have been converted with a different mlx-audio version.

**Solution**: Use bf16 (full precision) model which works correctly. Size is ~361MB vs theoretical ~50MB for 4-bit, but reliability is more important.

**Lesson**: Stick with verified working model variants; smaller isn't always better.

---

### Architecture Changes

#### New Files Created

```
modules/tts/
├── __init__.py     # Updated with new exports
├── engine.py       # Modified: temp file synthesis
├── chunker.py      # NEW: TextChunker class
└── memory.py       # NEW: VRAMManager, clear_vram()

config/
└── voices.py       # Updated: get_voice_choices(), speed presets
```

#### Dependencies Added

```bash
pip install mlx-audio soundfile "misaki[en]"
```

These install: mlx, mlx-lm, kokoro support, spacy, soundfile, and related packages.

#### Key Design Decisions

1. **Singleton VRAMManager**: Ensures only one model loaded at a time
2. **Temp file synthesis**: Works around mlx-audio's file-based output
3. **bf16 over quantized**: Reliability chosen over smaller model size
4. **Token-based chunking**: Estimate ~4 chars/token for chunk sizing

---

### Current State

**What Works**:
- TTS generates audio from text (tested: ~2.1s audio, 50,400 samples)
- Memory properly freed after model unload (verified: 312MB → 0MB)
- Text chunking splits long content at sentence boundaries
- Voice configuration ready for UI integration

**What's Next**:
- Add Streamlit sidebar for voice/speed selection
- Integrate chunker with TTS for chapter processing
- Optional: LLM text cleaner (2.3) for improved TTS quality

---

### Commits

| Hash | Message |
|------|---------|
| c1bdcd6 | fix tts synthesize to use temp file output |
| e3a4600 | add text chunker for vram management |
| bb62107 | add vram memory management utility |
| cdf4970 | add voice choices and speed presets for ui |
| 8d9de37 | export chunker and memory utilities |

---

## 2026-01-28 - Phase 3: Audio Processing Complete

### Tasks Completed

From `tasks/03_AUDIO_PROCESSING.md`:

**3.1 Audio Processor (PyDub)**
- [x] Create `modules/audio/processor.py`
- [x] Implement `AudioProcessor` class with concatenate, normalize, silence
- [x] Test with multiple WAV file concatenation

**3.2 MP3 Encoder (FFmpeg)**
- [x] Create `modules/audio/encoder.py`
- [x] Implement `AudioEncoder` class with wav_to_mp3, get_duration
- [x] Verify VideoToolbox hardware acceleration available

**3.3 M4B Packager**
- [x] Create `modules/audio/packager.py`
- [x] Implement `M4BPackager` with chapter markers
- [x] Test chapter navigation (verified: 3 chapters with correct timestamps)

**3.4 Metadata Handling**
- [x] Integrated with existing EPUB/PDF parsers
- [x] `AudiobookMetadata` dataclass for user editing
- [x] Metadata embedded via FFmpeg metadata file

---

### Architecture Changes

#### New Files Created

```
modules/audio/
├── __init__.py     # Updated: exports all audio classes
├── processor.py    # NEW: AudioProcessor (PyDub)
├── encoder.py      # NEW: AudioEncoder (FFmpeg)
└── packager.py     # NEW: M4BPackager, AudiobookMetadata, ChapterMarker
```

#### Dependencies Added

```bash
pip install pydub  # Audio processing
# ffmpeg required (brew install ffmpeg)
```

#### Key Design Decisions

1. **PyDub for processing**: High-level API for WAV manipulation
2. **FFmpeg for encoding**: Industry standard, hardware accelerated on Mac
3. **Pure FFmpeg for M4B**: No m4b-tool dependency, uses ffmetadata format
4. **Dataclasses for metadata**: Clean API for user editing before export

---

### Current State

**What Works**:
- WAV concatenation and volume normalization (-16 dBFS target)
- MP3 encoding at 128kbps with duration utilities
- M4B creation with chapter markers and metadata
- Chapter navigation verified working

**What's Next (Phase 3.5 Cover Art - Deferred)**:
- Extract cover from EPUB
- Allow custom cover upload
- Embed cover in M4B

---

### Commits

| Hash | Message |
|------|---------|
| 1947c20 | add audio processor with pydub |
| b425736 | fix type annotations for pydub |
| d2e94f7 | export audio processor |
| b50df8d | add ffmpeg audio encoder |
| a931972 | add m4b audiobook packager |
| beb695e | export encoder and packager |

---

*Next entry will be added when continuing development.*

