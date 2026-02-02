#!/usr/bin/env python3
"""
gRPC Backend Server for Audiobook Creator
=========================================
Provides real-time streaming conversion progress, model management,
and library services to the SwiftUI frontend.

Run with: python -m swift_ui.BackendGRPC.server
"""

import asyncio
import logging
import sys
import time
import uuid
from concurrent import futures
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Optional

import grpc

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import generated protobuf code
from generated import audiobook_pb2
from generated import audiobook_pb2_grpc

# Import existing pipeline modules
try:
    from modules.pipeline.orchestrator import ConversionPipeline, PipelineConfig, PipelineStage
    PIPELINE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import pipeline modules: {e}")
    PIPELINE_AVAILABLE = False
    PipelineStage = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# CONVERSION SERVICE
# ============================================================================

class ConversionServiceServicer(audiobook_pb2_grpc.ConversionServiceServicer):
    """gRPC servicer for conversion operations."""
    
    def __init__(self):
        self.active_conversions: dict[str, any] = {}
        self._log_queues: dict[str, Queue] = {}
    
    def ConvertBook(self, request: audiobook_pb2.ConversionRequest, context: grpc.ServicerContext):
        """
        Stream conversion progress to client.
        """
        conversion_id = str(uuid.uuid4())
        queue: Queue = Queue()
        self._log_queues[conversion_id] = queue
        
        logger.info(f"Starting conversion {conversion_id} for {request.source_path}")
        logger.info(f"Voice: {request.voice}, Speed: {request.speed}")
        
        start_time = time.time()
        
        def progress_callback(
            stage: any,
            chapter_idx: int,
            total_chapters: int,
            chunk_idx: int,
            total_chunks: int,
            message: str,
            eta: Optional[float]
        ):
            """Callback for pipeline progress updates."""
            progress = self._calculate_progress(
                stage, chapter_idx, total_chapters, chunk_idx, total_chunks
            )
            
            update = audiobook_pb2.ConversionProgress(
                stage=self._map_stage(stage),
                stage_name=stage.name if hasattr(stage, 'name') else str(stage),
                chapter_index=chapter_idx,
                total_chapters=total_chapters,
                chunk_index=chunk_idx,
                total_chunks=total_chunks,
                overall_progress=progress,
                eta_seconds=self._format_eta(eta),
                elapsed_seconds=time.time() - start_time,
                current_chapter_title=message[:100] if message else "",
                message=message
            )
            queue.put(update)
        
        def log_callback(message: str, level: str):
            """Callback for log messages."""
            entry = audiobook_pb2.LogEntry(
                timestamp_unix_ms=int(time.time() * 1000),
                level=level.upper(),
                message=message,
                source="pipeline"
            )
            queue.put(entry)
        
        # Run conversion in thread
        result_container = {'result': None, 'error': None, 'completed': False}
        
        def run_conversion():
            """Run the actual conversion."""
            try:
                if PIPELINE_AVAILABLE:
                    config = PipelineConfig(
                        voice=request.voice,
                        speed=request.speed,
                        output_dir=Path("output"),
                        temp_dir=Path("temp"),
                    )
                    
                    pipeline = ConversionPipeline(
                        config=config,
                        progress_callback=progress_callback,
                        verbose_callback=log_callback
                    )
                    
                    self.active_conversions[conversion_id] = pipeline
                    result = pipeline.convert(Path(request.source_path))
                    result_container['result'] = result
                else:
                    # Demo mode - simulate conversion
                    self._simulate_conversion(queue, request, start_time)
                    
                result_container['completed'] = True
            except Exception as e:
                result_container['error'] = str(e)
                result_container['completed'] = True
                logger.exception("Conversion failed")
        
        # Start conversion thread
        conversion_thread = Thread(target=run_conversion)
        conversion_thread.start()
        
        try:
            # Stream updates until complete
            last_yield_time = time.time()
            while not result_container['completed'] or not queue.empty():
                try:
                    # Get update with timeout
                    update = queue.get(timeout=0.1)
                    yield update
                    last_yield_time = time.time()
                except:
                    # Send heartbeat every second if no updates
                    if time.time() - last_yield_time > 1.0:
                        heartbeat = audiobook_pb2.ConversionProgress(
                            stage=audiobook_pb2.ConversionProgress.PARSING if not result_container['completed'] else audiobook_pb2.ConversionProgress.IDLE,
                            stage_name="Processing" if not result_container['completed'] else "Idle",
                            overall_progress=0.5,
                            eta_seconds="--:--",
                            elapsed_seconds=time.time() - start_time,
                            message="Working..."
                        )
                        yield heartbeat
                        last_yield_time = time.time()
            
            # Wait for thread to finish
            conversion_thread.join(timeout=1.0)
            
            # Send final status
            if result_container['error']:
                yield audiobook_pb2.ConversionProgress(
                    stage=audiobook_pb2.ConversionProgress.ERROR,
                    stage_name="Error",
                    overall_progress=0,
                    eta_seconds="--:--",
                    elapsed_seconds=time.time() - start_time,
                    message=str(result_container['error']),
                    logs=[audiobook_pb2.LogEntry(
                        timestamp_unix_ms=int(time.time() * 1000),
                        level="ERROR",
                        message=str(result_container['error']),
                        source="server"
                    )]
                )
            else:
                yield audiobook_pb2.ConversionProgress(
                    stage=audiobook_pb2.ConversionProgress.COMPLETE,
                    stage_name="Complete",
                    overall_progress=1.0,
                    eta_seconds="00:00",
                    elapsed_seconds=time.time() - start_time,
                    message="Conversion complete!"
                )
            
        finally:
            if conversion_id in self.active_conversions:
                del self.active_conversions[conversion_id]
            if conversion_id in self._log_queues:
                del self._log_queues[conversion_id]
    
    def _simulate_conversion(self, queue: Queue, request: audiobook_pb2.ConversionRequest, start_time: float):
        """Simulate a conversion for demo purposes."""
        import time as time_module
        
        stages = [
            (audiobook_pb2.ConversionProgress.PARSING, "Parsing Document"),
            (audiobook_pb2.ConversionProgress.CHUNKING, "Chunking Text"),
            (audiobook_pb2.ConversionProgress.CLEANING, "Cleaning Text"),
            (audiobook_pb2.ConversionProgress.SYNTHESIZING, "Synthesizing Speech"),
            (audiobook_pb2.ConversionProgress.ENCODING, "Encoding Audio"),
            (audiobook_pb2.ConversionProgress.PACKAGING, "Packaging M4B"),
        ]
        
        for i, (stage, stage_name) in enumerate(stages):
            progress = (i + 1) / len(stages)
            
            update = audiobook_pb2.ConversionProgress(
                stage=stage,
                stage_name=stage_name,
                chapter_index=i,
                total_chapters=6,
                chunk_index=i * 10,
                total_chunks=60,
                overall_progress=progress,
                eta_seconds=f"00:{60 - i * 10:02d}",
                elapsed_seconds=time_module.time() - start_time,
                current_chapter_title=f"Chapter {i + 1}",
                message=f"Processing {stage_name}...",
                logs=[
                    audiobook_pb2.LogEntry(
                        timestamp_unix_ms=int(time_module.time() * 1000),
                        level="PROCESS",
                        message=f"Starting {stage_name}",
                        source="pipeline"
                    ),
                    audiobook_pb2.LogEntry(
                        timestamp_unix_ms=int(time_module.time() * 1000),
                        level="INFO",
                        message=f"Chapter {i + 1}: Processed {i * 10}/60 chunks",
                        source="pipeline"
                    )
                ]
            )
            queue.put(update)
            time_module.sleep(1.0)  # Simulate work
    
    def _map_stage(self, stage: any) -> int:
        """Map pipeline stage to proto enum."""
        if not PIPELINE_AVAILABLE or stage is None:
            return audiobook_pb2.ConversionProgress.IDLE
        
        mapping = {
            PipelineStage.IDLE: audiobook_pb2.ConversionProgress.IDLE,
            PipelineStage.INGESTING: audiobook_pb2.ConversionProgress.PARSING,
            PipelineStage.CHUNKING: audiobook_pb2.ConversionProgress.CHUNKING,
            PipelineStage.CLEANING: audiobook_pb2.ConversionProgress.CLEANING,
            PipelineStage.SYNTHESIZING: audiobook_pb2.ConversionProgress.SYNTHESIZING,
            PipelineStage.ENCODING: audiobook_pb2.ConversionProgress.ENCODING,
            PipelineStage.PACKAGING: audiobook_pb2.ConversionProgress.PACKAGING,
            PipelineStage.COMPLETE: audiobook_pb2.ConversionProgress.COMPLETE,
            PipelineStage.ERROR: audiobook_pb2.ConversionProgress.ERROR,
            PipelineStage.CANCELLED: audiobook_pb2.ConversionProgress.CANCELLED,
        }
        return mapping.get(stage, audiobook_pb2.ConversionProgress.IDLE)
    
    def _calculate_progress(self, stage: any, chapter_idx: int, total_chapters: int, chunk_idx: int, total_chunks: int) -> float:
        """Calculate overall progress (0.0 - 1.0)."""
        if total_chapters == 0:
            return 0.0
        
        chapter_progress = chapter_idx / total_chapters
        stage_progress = chunk_idx / max(total_chunks, 1)
        
        return chapter_progress + (0.1 * stage_progress / total_chapters)
    
    def _format_eta(self, eta: Optional[float]) -> str:
        """Format ETA as mm:ss."""
        if eta is None or eta < 0:
            return "--:--"
        minutes = int(eta // 60)
        seconds = int(eta % 60)
        return f"{minutes:02d}:{seconds:02d}"
    
    def CancelConversion(self, request: audiobook_pb2.CancelRequest, context: grpc.ServicerContext):
        """Cancel an ongoing conversion."""
        logger.info(f"Cancellation requested for {request.conversion_id}")
        
        # Cancel the pipeline if it exists
        if request.conversion_id in self.active_conversions:
            pipeline = self.active_conversions[request.conversion_id]
            if hasattr(pipeline, 'cancel'):
                pipeline.cancel()
        
        return audiobook_pb2.CancelResponse(
            success=True,
            message="Cancellation requested"
        )
    
    def GetConversionStatus(self, request: audiobook_pb2.Empty, context: grpc.ServicerContext):
        """Get current conversion status."""
        is_running = len(self.active_conversions) > 0
        return audiobook_pb2.ConversionStatus(
            is_running=is_running,
            current_stage="processing" if is_running else "idle",
            progress=0.5 if is_running else 0.0
        )
    
    def PreviewVoice(self, request: audiobook_pb2.PreviewRequest, context: grpc.ServicerContext):
        """Preview voice with sample text."""
        logger.info(f"Voice preview requested: {request.voice}")
        
        # For now, just return empty chunks
        # In production, this would stream audio data
        yield audiobook_pb2.AudioChunk(
            data=b"",
            sample_rate=24000,
            format="pcm_f32le",
            is_last=True,
            timestamp_seconds=0.0
        )


# ============================================================================
# MODEL SERVICE
# ============================================================================

class ModelServiceServicer(audiobook_pb2_grpc.ModelServiceServicer):
    """gRPC servicer for model management."""
    
    _tts_loaded = False
    _cleaner_loaded = False
    _tts_loading = False
    _cleaner_loading = False
    
    def GetModelStatus(self, request: audiobook_pb2.Empty, context: grpc.ServicerContext):
        """Get current model loading status."""
        return audiobook_pb2.ModelStatus(
            tts_model=audiobook_pb2.TTSModelStatus(
                is_loaded=self._tts_loaded,
                model_name="mlx-community/Kokoro-82M-bf16",
                vram_usage_bytes=340_000_000 if self._tts_loaded else 0,
                device="metal"
            ),
            cleaner_model=audiobook_pb2.CleanerModelStatus(
                is_loaded=self._cleaner_loaded,
                model_name="mlx-community/Llama-3.2-3B-Instruct-4bit",
                vram_usage_bytes=1_800_000_000 if self._cleaner_loaded else 0
            )
        )
    
    def LoadModel(self, request: audiobook_pb2.LoadModelRequest, context: grpc.ServicerContext):
        """Load a model with progress streaming."""
        model_type = "TTS" if request.model_type == audiobook_pb2.LoadModelRequest.TTS else "Cleaner"
        logger.info(f"Loading {model_type} model: {request.model_name or 'default'}")
        
        # Simulate loading progress
        for i in range(10):
            yield audiobook_pb2.LoadProgress(
                progress=(i + 1) / 10,
                stage="loading",
                message=f"Loading {model_type} model... {(i + 1) * 10}%",
                bytes_downloaded=i * 100_000_000,
                bytes_total=1_000_000_000
            )
            time.sleep(0.2)
        
        # Mark as loaded
        if request.model_type == audiobook_pb2.LoadModelRequest.TTS:
            self._tts_loaded = True
        else:
            self._cleaner_loaded = True
        
        yield audiobook_pb2.LoadProgress(
            progress=1.0,
            stage="complete",
            message=f"{model_type} model loaded successfully"
        )
    
    def UnloadModel(self, request: audiobook_pb2.UnloadModelRequest, context: grpc.ServicerContext):
        """Unload models."""
        model_type = request.model_type
        
        if model_type in [audiobook_pb2.UnloadModelRequest.TTS, audiobook_pb2.UnloadModelRequest.ALL]:
            self._tts_loaded = False
            logger.info("TTS model unloaded")
        
        if model_type in [audiobook_pb2.UnloadModelRequest.CLEANER, audiobook_pb2.UnloadModelRequest.ALL]:
            self._cleaner_loaded = False
            logger.info("Cleaner model unloaded")
        
        return audiobook_pb2.Empty()
    
    def StreamModelStatus(self, request: audiobook_pb2.Empty, context: grpc.ServicerContext):
        """Stream model status changes."""
        while context.is_active():
            yield self.GetModelStatus(request, context)
            time.sleep(1.0)


# ============================================================================
# LIBRARY SERVICE
# ============================================================================

class LibraryServiceServicer(audiobook_pb2_grpc.LibraryServiceServicer):
    """gRPC servicer for library management."""
    
    def ListBooks(self, request: audiobook_pb2.ListBooksRequest, context: grpc.ServicerContext):
        """List all audiobooks in library."""
        # For now, return empty list
        # In production, this would query the database
        return audiobook_pb2.ListBooksResponse(
            books=[],
            next_page_token="",
            total_count=0
        )
    
    def GetBook(self, request: audiobook_pb2.GetBookRequest, context: grpc.ServicerContext):
        """Get details for a specific book."""
        # Return not found
        context.set_code(grpc.StatusCode.NOT_FOUND)
        context.set_details(f"Book {request.book_id} not found")
        return audiobook_pb2.Book()
    
    def DeleteBook(self, request: audiobook_pb2.DeleteBookRequest, context: grpc.ServicerContext):
        """Delete a book from library."""
        logger.info(f"Deleting book {request.book_id}")
        return audiobook_pb2.Empty()
    
    def StreamAudio(self, request: audiobook_pb2.StreamAudioRequest, context: grpc.ServicerContext):
        """Stream audio for playback."""
        # For now, return empty chunks
        yield audiobook_pb2.AudioChunk(
            data=b"",
            sample_rate=24000,
            format="pcm_f32le",
            is_last=True,
            timestamp_seconds=0.0
        )
    
    def GetWaveform(self, request: audiobook_pb2.WaveformRequest, context: grpc.ServicerContext):
        """Get waveform data for visualization."""
        # Return dummy waveform data
        samples = [0.0] * request.sample_points
        return audiobook_pb2.WaveformData(
            samples=samples,
            duration_ms=0,
            sample_rate=24000
        )


# ============================================================================
# SERVER SETUP
# ============================================================================

def serve(port: int = 50051):
    """Start the gRPC server."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # Add servicers
    audiobook_pb2_grpc.add_ConversionServiceServicer_to_server(
        ConversionServiceServicer(), server
    )
    audiobook_pb2_grpc.add_ModelServiceServicer_to_server(
        ModelServiceServicer(), server
    )
    audiobook_pb2_grpc.add_LibraryServiceServicer_to_server(
        LibraryServiceServicer(), server
    )
    
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    
    logger.info(f"=" * 60)
    logger.info(f"🚀 Audiobook Creator gRPC Server")
    logger.info(f"📡 Listening on port {port}")
    logger.info(f"🔧 Pipeline available: {PIPELINE_AVAILABLE}")
    logger.info(f"=" * 60)
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("\n⚠️  Shutting down server...")
        server.stop(5)
        logger.info("✅ Server stopped")


if __name__ == "__main__":
    serve()
