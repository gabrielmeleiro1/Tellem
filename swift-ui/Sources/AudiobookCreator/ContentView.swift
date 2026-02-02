import SwiftUI

struct ContentView: View {
    @EnvironmentObject var appState: AppState
    
    var body: some View {
        NavigationSplitView {
            Sidebar(selectedView: $appState.selectedView)
                .frame(minWidth: 200)
        } detail: {
            Group {
                switch appState.selectedView {
                case .convert:
                    ConversionView()
                        .environmentObject(appState.conversionViewModel)
                case .library:
                    LibraryView()
                case .player:
                    PlayerView()
                case .models:
                    ModelsView()
                case .settings:
                    SettingsView()
                }
            }
        }
        .background(Color.mossCore)
    }
}

// MARK: - Sidebar

struct Sidebar: View {
    @Binding var selectedView: AppState.AppView
    
    var body: some View {
        List(selection: $selectedView) {
            Section("Main") {
                NavigationLink(value: AppState.AppView.convert) {
                    Label("Convert", systemImage: "arrow.right.circle")
                }
                
                NavigationLink(value: AppState.AppView.library) {
                    Label("Library", systemImage: "books.vertical")
                }
            }
            
            Section("Tools") {
                NavigationLink(value: AppState.AppView.models) {
                    Label("Models", systemImage: "cpu")
                }
            }
            
            Section("App") {
                NavigationLink(value: AppState.AppView.settings) {
                    Label("Settings", systemImage: "gear")
                }
            }
        }
        .listStyle(.sidebar)
        .navigationTitle("Audiobook Creator")
    }
}

// MARK: - Placeholder Views

struct LibraryView: View {
    var body: some View {
        Text("Library View")
            .foregroundColor(.mossTextMain)
    }
}

struct PlayerView: View {
    var body: some View {
        Text("Player View")
            .foregroundColor(.mossTextMain)
    }
}

struct ModelsView: View {
    var body: some View {
        Text("Models View")
            .foregroundColor(.mossTextMain)
    }
}

struct SettingsView: View {
    var body: some View {
        Text("Settings View")
            .foregroundColor(.mossTextMain)
    }
}
