import SwiftUI

@main
struct AudiobookCreatorApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var appState = AppState()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appState)
                .frame(minWidth: 1200, minHeight: 800)
        }
        .defaultSize(width: 1400, height: 900)
        .windowStyle(.titleBar)
        .windowResizability(.contentSize)
        .commands {
            CommandMenu("Conversion") {
                Button("Start Conversion") {
                    appState.conversionViewModel.startConversion()
                }
                .keyboardShortcut("r", modifiers: .command)
                .disabled(appState.conversionViewModel.selectedFile == nil || appState.conversionViewModel.isConverting)
                
                Button("Cancel") {
                    appState.conversionViewModel.cancelConversion()
                }
                .keyboardShortcut(".", modifiers: [.command, .shift])
                .disabled(!appState.conversionViewModel.isConverting)
            }
            
            CommandMenu("View") {
                Picker("View", selection: $appState.selectedView) {
                    Text("Convert").tag(AppState.AppView.convert)
                    Text("Library").tag(AppState.AppView.library)
                    Text("Models").tag(AppState.AppView.models)
                }
                .pickerStyle(.inline)
            }
        }
    }
}

// MARK: - App State

@MainActor
class AppState: ObservableObject {
    enum AppView {
        case convert
        case library
        case player
        case models
        case settings
    }
    
    @Published var selectedView: AppView = .convert
    @Published var isConnected = false
    
    // Shared ViewModel - persists across view switches
    @Published var conversionViewModel: ConversionViewModel
    
    // Services
    let grpcClient: GRPCClient
    
    init() {
        self.grpcClient = GRPCClient(target: .host("localhost", port: 50051))
        self.conversionViewModel = ConversionViewModel(grpcClient: grpcClient)
        
        // Check connection on init
        Task {
            await checkConnection()
        }
    }
    
    func checkConnection() async {
        do {
            try await grpcClient.connect()
            isConnected = true
        } catch {
            isConnected = false
        }
    }
}

// MARK: - App Delegate

class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Ensure proper window level and visibility
        if let window = NSApplication.shared.windows.first {
            window.titlebarAppearsTransparent = false
            window.titleVisibility = .visible
            window.isReleasedWhenClosed = false
            window.setContentSize(NSSize(width: 1400, height: 900))
            window.center()
        }
    }
    
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }
    
    func applicationDidBecomeActive(_ notification: Notification) {
        // Ensure window is properly shown when app becomes active
        if let window = NSApplication.shared.windows.first, !window.isVisible {
            window.makeKeyAndOrderFront(nil)
        }
    }
}
