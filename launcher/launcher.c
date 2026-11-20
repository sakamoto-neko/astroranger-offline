/* AstroRanger one-click launcher (v2)
 * Starts the local server (Start.exe) hidden, then presses the server's own
 * "launch game" button (bottom-right push button) so the server does all of
 * its normal setup and starts the game itself. Closes the server when the
 * game exits. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winsock2.h>
#include <iphlpapi.h>
#include <tlhelp32.h>
#include <string.h>

static char g_dir[MAX_PATH], g_gameExe[MAX_PATH];
static DWORD g_serverPid;
static int g_showServer;
static HWND g_btn; static LONG g_best;

static void fail(const char *msg) { MessageBoxA(NULL, msg, "AstroRanger Launcher", MB_ICONERROR); ExitProcess(1); }

static int port_listening(int port) {
    DWORD sz = 0; int found = 0;
    GetExtendedTcpTable(NULL, &sz, FALSE, AF_INET, TCP_TABLE_OWNER_PID_LISTENER, 0);
    sz += 4096;
    MIB_TCPTABLE_OWNER_PID *t = (MIB_TCPTABLE_OWNER_PID *)HeapAlloc(GetProcessHeap(), 0, sz);
    if (t && GetExtendedTcpTable(t, &sz, FALSE, AF_INET, TCP_TABLE_OWNER_PID_LISTENER, 0) == NO_ERROR)
        for (DWORD i = 0; i < t->dwNumEntries; i++)
            if (ntohs((u_short)t->table[i].dwLocalPort) == port) { found = 1; break; }
    if (t) HeapFree(GetProcessHeap(), 0, t);
    return found;
}

/* mode 0 = move off-screen (window stays "visible" so its embedded browser control
   still loads), mode 1 = hide completely, mode 2 = bring back on screen */
static int g_mode;
static BOOL CALLBACK hide_cb(HWND h, LPARAM lp) {
    DWORD pid; GetWindowThreadProcessId(h, &pid);
    if (pid != g_serverPid || !IsWindowVisible(h)) return TRUE;
    if (GetWindow(h, GW_OWNER)) return TRUE;
    RECT r; GetWindowRect(h, &r);
    int offx = GetSystemMetrics(SM_XVIRTUALSCREEN) + GetSystemMetrics(SM_CXVIRTUALSCREEN) + 200;
    if (g_mode == 1) ShowWindow(h, SW_HIDE);
    else if (g_mode == 0 && r.left < offx)
        SetWindowPos(h, NULL, offx, 0, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE);
    return TRUE;
}
static void hide_server(void) { if (!g_showServer && g_serverPid) EnumWindows(hide_cb, 0); }

static int server_has_client(int port) {
    DWORD sz = 0; int found = 0;
    GetExtendedTcpTable(NULL, &sz, FALSE, AF_INET, TCP_TABLE_OWNER_PID_CONNECTIONS, 0);
    sz += 8192;
    MIB_TCPTABLE_OWNER_PID *t = (MIB_TCPTABLE_OWNER_PID *)HeapAlloc(GetProcessHeap(), 0, sz);
    if (t && GetExtendedTcpTable(t, &sz, FALSE, AF_INET, TCP_TABLE_OWNER_PID_CONNECTIONS, 0) == NO_ERROR)
        for (DWORD i = 0; i < t->dwNumEntries; i++)
            if (t->table[i].dwOwningPid == g_serverPid && t->table[i].dwState == MIB_TCP_STATE_ESTAB &&
                ntohs((u_short)t->table[i].dwLocalPort) == port) { found = 1; break; }
    if (t) HeapFree(GetProcessHeap(), 0, t);
    return found;
}

/* find the bottom-right-most push button among the server's windows */
static BOOL CALLBACK child_cb(HWND h, LPARAM lp) {
    char cls[32]; GetClassNameA(h, cls, sizeof cls);
    if (!lstrcmpiA(cls, "Button")) {
        LONG st = GetWindowLongA(h, GWL_STYLE) & BS_TYPEMASK;
        if (st == BS_PUSHBUTTON || st == BS_DEFPUSHBUTTON) {
            RECT r; GetWindowRect(h, &r);
            LONG score = r.right + r.bottom;
            if (!g_btn || score > g_best) { g_btn = h; g_best = score; }
        }
    }
    return TRUE;
}
static BOOL CALLBACK top_cb(HWND h, LPARAM lp) {
    DWORD pid; GetWindowThreadProcessId(h, &pid);
    if (pid == g_serverPid) EnumChildWindows(h, child_cb, 0);
    return TRUE;
}
static HWND find_button(void) { g_btn = NULL; g_best = 0; EnumWindows(top_cb, 0); return g_btn; }

static DWORD find_proc(const char *exe) {
    DWORD pid = 0; PROCESSENTRY32 pe; pe.dwSize = sizeof pe;
    HANDLE s = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (s == INVALID_HANDLE_VALUE) return 0;
    if (Process32First(s, &pe)) do { if (!lstrcmpiA(pe.szExeFile, exe)) { pid = pe.th32ProcessID; break; } } while (Process32Next(s, &pe));
    CloseHandle(s);
    return pid;
}
static int wait_game_start(int ms) {
    for (int t = 0; t < ms; t += 100) { if (find_proc(g_gameExe)) return 1; hide_server(); Sleep(100); }
    return 0;
}

int WINAPI WinMain(HINSTANCE hi, HINSTANCE hp, LPSTR cl, int show) {
    char ini[MAX_PATH], cfg[MAX_PATH], srv[MAX_PATH], srvPath[MAX_PATH], srvCmd[MAX_PATH + 2];
    /* Settings live next to the launcher. The game folder is, in order:
       1. a folder given on the command line, 2. GameDir= in the .ini
       (absolute, or relative to the launcher), 3. the launcher's own folder. */
    char self[MAX_PATH], want[MAX_PATH], tmp[MAX_PATH], *fp;
    GetModuleFileNameA(NULL, self, MAX_PATH);
    *strrchr(self, '\\') = 0;
    wsprintfA(ini, "%s\\AstroRanger_Play.ini", self);
    want[0] = 0;
    if (cl && *cl) {
        lstrcpynA(want, cl, MAX_PATH);
        char *p = want; if (*p == '"') p++;
        lstrcpynA(tmp, p, MAX_PATH);
        int n = lstrlenA(tmp);
        while (n && (tmp[n-1] == '"' || tmp[n-1] == ' ' || tmp[n-1] == '\\')) tmp[--n] = 0;
        lstrcpynA(want, tmp, MAX_PATH);
    }
    if (!want[0]) GetPrivateProfileStringA("Launcher", "GameDir", "", want, MAX_PATH, ini);
    if (want[0]) {
        SetCurrentDirectoryA(self);                      /* relative paths are relative to the launcher */
        if (!GetFullPathNameA(want, MAX_PATH, g_dir, &fp)) lstrcpynA(g_dir, want, MAX_PATH);
        int n = lstrlenA(g_dir);
        while (n > 3 && g_dir[n-1] == '\\') g_dir[--n] = 0;
    } else lstrcpynA(g_dir, self, MAX_PATH);
    if (!SetCurrentDirectoryA(g_dir)) {
        char m[MAX_PATH + 64]; wsprintfA(m, "Game folder not found:\n%s", g_dir); fail(m);
    }
    wsprintfA(cfg, "%s\\config\\loginsvr.cfg", g_dir);
    int port = GetPrivateProfileIntA("Login Server", "port", 6760, cfg);
    g_showServer = GetPrivateProfileIntA("Launcher", "ShowServer", 0, ini);
    int timeout = GetPrivateProfileIntA("Launcher", "ServerWaitSeconds", 15, ini);
    int settle = GetPrivateProfileIntA("Launcher", "ExtraDelayMs", 2500, ini);
    int hideAfter = GetPrivateProfileIntA("Launcher", "HideServerAfterConnect", 1, ini);
    GetPrivateProfileStringA("Launcher", "Server", "Start.exe", srv, MAX_PATH, ini);
    GetPrivateProfileStringA("Launcher", "Game", "Astro Ranger.exe", g_gameExe, MAX_PATH, ini);

    if (find_proc(g_gameExe)) fail("Astro Ranger is already running.\nClose it (or end it in Task Manager) first.");

    /* a leftover server from an earlier run would get in the way */
    DWORD old = find_proc(srv);
    if (old) {
        HANDLE h = OpenProcess(PROCESS_TERMINATE | SYNCHRONIZE, FALSE, old);
        if (h) { TerminateProcess(h, 0); WaitForSingleObject(h, 3000); CloseHandle(h); }
        for (int i = 0; i < 30 && port_listening(port); i++) Sleep(100);
    }

    /* 1. start the server */
    wsprintfA(srvPath, "%s\\%s", g_dir, srv);
    if (GetFileAttributesA(srvPath) == INVALID_FILE_ATTRIBUTES) { char m[MAX_PATH * 2]; wsprintfA(m, "%s not found.\nPut the launcher in the game folder, or set GameDir= in AstroRanger_Play.ini.", srvPath); fail(m); }
    wsprintfA(srvCmd, "\"%s\"", srvPath);
    STARTUPINFOA si = { sizeof si }; PROCESS_INFORMATION pi;
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_SHOWNOACTIVATE;
    if (!CreateProcessA(srvPath, srvCmd, NULL, NULL, FALSE, 0, NULL, g_dir, &si, &pi))
        fail("Could not start the local server (Start.exe).");
    CloseHandle(pi.hThread);
    HANDLE hServer = pi.hProcess; g_serverPid = pi.dwProcessId;

    /* 2. wait until it listens and its launch button exists */
    DWORD start = GetTickCount(); HWND btn = NULL;
    for (;;) {
        hide_server();
        if (WaitForSingleObject(hServer, 0) == WAIT_OBJECT_0) fail("The local server (Start.exe) closed unexpectedly.");
        btn = find_button();
        if (btn && port_listening(port)) break;
        if (GetTickCount() - start > (DWORD)timeout * 1000) break;
        Sleep(100);
    }
    if (!btn) { TerminateProcess(hServer, 0); fail("Couldn't find the launch button in Start.exe."); }
    for (int t = 0; t < settle; t += 50) { hide_server(); Sleep(50); }

    /* 3. press the server's button (several methods, stop when the game appears) */
    HWND parent = GetParent(btn);
    int id = GetDlgCtrlID(btn);
    PostMessageA(btn, BM_CLICK, 0, 0);
    if (!wait_game_start(4000)) {
        PostMessageA(parent, WM_COMMAND, MAKEWPARAM(id, BN_CLICKED), (LPARAM)btn);
        if (!wait_game_start(4000)) {
            /* last resort: show the server window briefly and click the button for real */
            HWND top = GetAncestor(btn, GA_ROOT);
            g_mode = 2;
            ShowWindow(top, SW_SHOWNORMAL);
            SetWindowPos(top, HWND_TOP, 100, 100, 0, 0, SWP_NOSIZE); SetForegroundWindow(top);
            Sleep(300);
            RECT r; GetWindowRect(btn, &r);
            SetCursorPos((r.left + r.right) / 2, (r.top + r.bottom) / 2);
            INPUT in[2] = {0}; in[0].type = in[1].type = INPUT_MOUSE;
            in[0].mi.dwFlags = MOUSEEVENTF_LEFTDOWN; in[1].mi.dwFlags = MOUSEEVENTF_LEFTUP;
            SendInput(2, in, sizeof(INPUT));
            if (!wait_game_start(6000)) {
                TerminateProcess(hServer, 0);
                fail("The server did not start the game. Try ShowServer=1 in AstroRanger_Play.ini.");
            }
        }
    }

    /* 3b. once the game has connected to the login server, hide the server window */
    for (int t = 0; t < 60000 && !server_has_client(port); t += 200) {
        if (!find_proc(g_gameExe)) break;
        if (g_mode == 0) hide_server();
        Sleep(200);
    }
    g_mode = hideAfter ? 1 : 0;
    if (g_mode == 1) { Sleep(1000); hide_server(); }

    /* 4. wait for the game to close */
    for (;;) {
        DWORD gpid = find_proc(g_gameExe);
        if (!gpid) break;
        HANDLE g = OpenProcess(SYNCHRONIZE, FALSE, gpid);
        if (!g) { Sleep(1000); continue; }
        while (WaitForSingleObject(g, 500) == WAIT_TIMEOUT) hide_server();
        CloseHandle(g);
        Sleep(1000);
    }

    /* 5. close the server */
    if (GetPrivateProfileIntA("Launcher", "CloseServerOnExit", 1, ini)) TerminateProcess(hServer, 0);
    CloseHandle(hServer);
    return 0;
}
