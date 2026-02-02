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
    
    /// Reference to the main app window for restoration
    private weak var mainWindow: NSWindow?
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Configure the main window
        if let window = NSApplication.shared.windows.first {
            configureWindow(window)
            self.mainWindow = window
        }
    }
    
    /// Configure window appearance and behavior
    @MainActor
    private func configureWindow(_ window: NSWindow) {
        window.titlebarAppearsTransparent = false
        window.titleVisibility = .visible
        window.isReleasedWhenClosed = false
        window.setContentSize(NSSize(width: 1400, height: 900))
        window.center()
        
        // Set window level to normal (not floating)
        window.level = .normal
    }
    
    /// Called when the user clicks the dock icon or uses Cmd+Tab to switch to the app.
    /// This is the KEY method for handling window restoration on macOS.
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if let window = mainWindow ?? NSApplication.shared.windows.first {
            if window.isMiniaturized {
                // If minimized, deminiaturize it
                window.deminiaturize(nil)
            }
            // Always bring window to front and make it key
            window.makeKeyAndOrderFront(nil)
            window.orderFrontRegardless()
        }
        return true
    }
    
    /// Called when the app becomes active (e.g., clicking on the app in the Dock)
    func applicationDidBecomeActive(_ notification: Notification) {
        guard let window = mainWindow ?? NSApplication.shared.windows.first else { return }
        
        // Always bring window forward when app becomes active
        // This handles edge cases where the window might be behind others
        if !window.isVisible {
            window.makeKeyAndOrderFront(nil)
        } else if !window.isKeyWindow {
            window.makeKeyAndOrderFront(nil)
        }
    }
    
    /// Keep app running when last window is closed (standard for document-based apps)
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        // Return false to keep the app running when window is closed
        // This allows the window to be restored when clicking the dock icon
        return false
    }
    
    /// Called when a new window is created (e.g., after closing and reopening)
    func applicationDidUpdate(_ notification: Notification) {
        // Track the main window if we lost reference
        if mainWindow == nil || mainWindow?.isReleasedWhenClosed == nil {
            mainWindow = NSApplication.shared.windows.first
        }
    }
}
