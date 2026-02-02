import SwiftUI

// MARK: - Model Status Panel

struct ModelStatusPanel: View {
    @ObservedObject var viewModel: ConversionViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("MODELS")
                .font(.system(.caption, design: .monospaced))
                .foregroundColor(.mossTextDim)
            
            // TTS Model
            ModelCard(
                name: "TTS Model",
                modelId: "mlx-community/Kokoro-82M-bf16",
                isLoaded: viewModel.ttsModelLoaded,
                isActive: viewModel.activeModel == "tts",
                vramUsage: viewModel.ttsModelLoaded ? "340 MB" : nil
            )
            
            // Cleaner Model
            ModelCard(
                name: "Text Cleaner",
                modelId: "mlx-community/Llama-3.2-3B-Instruct-4bit",
                isLoaded: viewModel.cleanerModelLoaded,
                isActive: viewModel.activeModel == "cleaner",
                vramUsage: viewModel.cleanerModelLoaded ? "1.8 GB" : nil
            )
            
            Spacer()
        }
        .padding()
        .mossPanel()
    }
}

// MARK: - Model Card

struct ModelCard: View {
    let name: String
    let modelId: String
    let isLoaded: Bool
    let isActive: Bool
    let vramUsage: String?
    
    private var statusIcon: String {
        isLoaded ? "●" : "○"
    }
    
    private var statusColor: Color {
        if isActive { return .mossAccent }
        return isLoaded ? .mossSuccess : .mossTextFaded
    }
    
    private var statusText: String {
        if isActive { return "active" }
        return isLoaded ? "loaded" : "standby"
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 8) {
                Text(statusIcon)
                    .foregroundColor(statusColor)
                    .font(.system(.body, design: .monospaced))
                
                Text(name)
                    .font(.system(.caption, design: .monospaced))
                    .foregroundColor(isActive ? .mossAccent : .mossTextMain)
                
                if isActive {
                    Image(systemName: "bolt.fill")
                        .font(.caption2)
                        .foregroundColor(.mossGold)
                }
                
                Spacer()
            }
            
            Text(modelId)
                .font(.caption2)
                .foregroundColor(.mossTextFaded)
                .lineLimit(1)
                .truncationMode(.middle)
            
            HStack {
                Text("status: \(statusText)")
                    .font(.caption2)
                    .foregroundColor(.mossTextDim)
                
                Spacer()
                
                if let vram = vramUsage {
                    Text(vram)
                        .font(.caption2)
                        .foregroundColor(.mossTextFaded)
                }
            }
        }
        .padding(8)
        .background(Color.mossCore)
        .border(isActive ? Color.mossAccent : Color.mossBorder, width: 1)
    }
}
