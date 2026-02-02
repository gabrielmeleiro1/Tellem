import SwiftUI

struct ContentView: View {
    @EnvironmentObject var appState: AppState
    
    var body: some View {
        NavigationSplitView {
            Sidebar(selectedView: $appState.selectedView)
                .frame(minWidth: 200)
        } detail: {
            ZStack {
                Color.mossCore
                    .ignoresSafeArea()
                
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
        }
        .navigationSplitViewStyle(.balanced)
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
        ZStack {
            Color.mossCore.ignoresSafeArea()
            Text("Library View")
                .foregroundColor(.mossTextMain)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct PlayerView: View {
    var body: some View {
        ZStack {
            Color.mossCore.ignoresSafeArea()
            Text("Player View")
                .foregroundColor(.mossTextMain)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct ModelsView: View {
    var body: some View {
        ZStack {
            Color.mossCore.ignoresSafeArea()
            Text("Models View")
                .foregroundColor(.mossTextMain)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct SettingsView: View {
    var body: some View {
        ZStack {
            Color.mossCore.ignoresSafeArea()
            Text("Settings View")
                .foregroundColor(.mossTextMain)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
