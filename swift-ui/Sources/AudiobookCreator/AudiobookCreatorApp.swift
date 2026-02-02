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
        .windowStyle(.titleBar)
        .commands {
            CommandMenu("Conversion") {
                Button("Start Conversion") {
                    appState.startConversion()
                }
                .keyboardShortcut("r", modifiers: .command)
                
                Button("Cancel") {
                    appState.cancelConversion()
                }
                .keyboardShortcut(".", modifiers: [.command, .shift])
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
    
    // Services
    let grpcClient: GRPCClient
    
    init() {
        self.grpcClient = GRPCClient(target: .host("localhost", port: 50051))
        
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
    
    func startConversion() {
        // Handled by ConversionViewModel
    }
    
    func cancelConversion() {
        // Handled by ConversionViewModel
    }
}

// MARK: - App Delegate

class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Setup menu bar or other app-level config
    }
    
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }
}
