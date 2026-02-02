import SwiftUI
import UniformTypeIdentifiers

// MARK: - Main Conversion View

struct ConversionView: View {
    @EnvironmentObject var viewModel: ConversionViewModel
    
    var body: some View {
        HStack(spacing: 16) {
            // Left panel: File drop + settings
            VStack(spacing: 16) {
                FileDropView(viewModel: viewModel)
                    .frame(height: 200)
                
                VoiceSettingsPanel(viewModel: viewModel)
                    .frame(maxHeight: .infinity)
            }
            .frame(width: 350)
            
            // Middle panel: Progress
            VStack(spacing: 16) {
                ProgressPanel(viewModel: viewModel)
                    .frame(height: 300)
                
                ModelStatusPanel(viewModel: viewModel)
                    .frame(maxHeight: .infinity)
            }
            .frame(width: 350)
            
            // Right panel: Terminal
            TerminalView(viewModel: viewModel)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .padding()
        .background(Color.mossCore)
    }
}

// MARK: - File Drop View

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
                SelectedFileView(file: file, viewModel: viewModel)
            } else {
                DropTargetView(isDropTarget: $isDropTarget) {
                    viewModel.showFilePicker()
                }
            }
        }
        .onDrop(of: [.pdf, .epub], isTargeted: $isDropTarget) { providers in
            handleDrop(providers)
        }
    }
    
    private func handleDrop(_ providers: [NSItemProvider]) -> Bool {
        for provider in providers {
            provider.loadFileRepresentation(forTypeIdentifier: UTType.pdf.identifier) { url, error in
                if let url = url {
                    DispatchQueue.main.async {
                        viewModel.selectFile(url)
                    }
                }
            }
            
            provider.loadFileRepresentation(forTypeIdentifier: "org.idpf.epub") { url, error in
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

struct SelectedFileView: View {
    let file: SelectedFile
    let viewModel: ConversionViewModel
    
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: file.iconName)
                .font(.system(size: 48))
                .foregroundColor(.mossAccent)
            
            Text(file.name)
                .font(.system(.body, design: .monospaced))
                .foregroundColor(.mossTextMain)
                .lineLimit(1)
                .truncationMode(.middle)
                .padding(.horizontal)
            
            Text(file.formattedSize)
                .font(.caption)
                .foregroundColor(.mossTextDim)
            
            HStack(spacing: 12) {
                Button("Change") {
                    viewModel.showFilePicker()
                }
                .buttonStyle(MossButtonStyle(isPrimary: false))
                
                Button("Convert") {
                    viewModel.startConversion()
                }
                .buttonStyle(MossButtonStyle(isPrimary: true))
                .disabled(viewModel.isConverting)
            }
            .padding(.top, 8)
        }
    }
}

struct DropTargetView: View {
    @Binding var isDropTarget: Bool
    let onTap: () -> Void
    @State private var isHovered = false
    
    var body: some View {
        Button(action: onTap) {
            VStack(spacing: 16) {
                Image(systemName: "arrow.down.document")
                    .font(.system(size: 48))
                    .foregroundColor(isDropTarget ? .mossAccent : (isHovered ? .mossTextMain : .mossTextDim))
                
                Text("Drop PDF or EPUB")
                    .font(.system(.body, design: .monospaced))
                    .foregroundColor(.mossTextMain)
                
                Text("or click to browse")
                    .font(.caption)
                    .foregroundColor(isHovered ? .mossAccent : .mossTextDim)
            }
        }
        .buttonStyle(DropZoneButtonStyle(isDropTarget: isDropTarget, isHovered: isHovered))
        .onHover { hovering in
            isHovered = hovering
        }
    }
}

// MARK: - Drop Zone Button Style

struct DropZoneButtonStyle: ButtonStyle {
    let isDropTarget: Bool
    let isHovered: Bool
    
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .contentShape(Rectangle())
            .opacity(configuration.isPressed ? 0.7 : 1.0)
            .background(
                isHovered && !isDropTarget ? Color.mossElevated.opacity(0.5) : Color.clear
            )
    }
}

// MARK: - Voice Settings Panel

struct VoiceSettingsPanel: View {
    @ObservedObject var viewModel: ConversionViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("VOICE SETTINGS")
                .font(.system(.caption, design: .monospaced))
                .foregroundColor(.mossTextDim)
            
            // Voice selection
            VStack(alignment: .leading, spacing: 8) {
                Text("Voice")
                    .font(.system(.caption, design: .monospaced))
                    .foregroundColor(.mossTextMain)
                
                Picker("", selection: $viewModel.selectedVoice) {
                    ForEach(VoiceOption.allCases) { voice in
                        Text(voice.displayName).tag(voice)
                    }
                }
                .pickerStyle(.menu)
                .disabled(viewModel.isConverting)
            }
            
            // Speed slider
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("Speed")
                        .font(.system(.caption, design: .monospaced))
                        .foregroundColor(.mossTextMain)
                    
                    Spacer()
                    
                    Text(String(format: "%.1fx", viewModel.speed))
                        .font(.system(.caption, design: .monospaced))
                        .foregroundColor(.mossTextDim)
                }
                
                Slider(value: $viewModel.speed, in: 0.5...2.0, step: 0.1)
                    .disabled(viewModel.isConverting)
                    .tint(.mossAccent)
            }
            
            Divider()
                .background(Color.mossBorder)
            
            // Preview button
            Button("Preview Voice") {
                viewModel.previewVoice()
            }
            .buttonStyle(MossButtonStyle(isPrimary: false))
            .disabled(viewModel.isConverting)
            
            Spacer()
        }
        .padding()
        .mossPanel()
    }
}
