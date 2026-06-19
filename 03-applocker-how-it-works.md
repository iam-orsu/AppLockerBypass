# AppLocker - How It Actually Works

This file has two goals. First: understand AppLocker deeply enough to know where it can fail. Second: set it up in your lab so you have something real to bypass in the files that follow.

Labs are woven in as you go. By the end of this file, AppLocker will be running and enforcing rules on your Windows 11 VM.

---

## Part A: What is AppLocker Really?

You already know the bouncer analogy from the intro. Now go deeper.

AppLocker is not a single program. It is a combination of two things working together:

**1. A Windows service called AppIDSvc (Application Identity Service)**

This is a background service that runs constantly. Its job is to figure out the identity of any program that tries to run - who made it, where it came from, what its hash is. It is the brain of AppLocker.

**2. A kernel driver called appid.sys**

The kernel is the deepest part of Windows - the part that controls hardware and manages all running programs. `appid.sys` sits at this level. When any program tries to start, the kernel driver intercepts it, checks with AppIDSvc, and either lets it through or blocks it before it even begins.

This matters because it means AppLocker's enforcement happens at a very low level. It is not just a check that runs after the program starts. The program never starts at all if AppLocker blocks it.

### What Can AppLocker Control?

AppLocker organizes its rules into five collections. Think of each collection as a separate rulebook for a different type of file:

| Collection | File Types | What it Controls |
|------------|-----------|-----------------|
| Executable Rules | `.exe`, `.com` | Standard programs |
| Script Rules | `.ps1`, `.bat`, `.cmd`, `.vbs`, `.js` | Scripts of all kinds |
| Windows Installer Rules | `.msi`, `.msp`, `.mst` | Software installers |
| DLL Rules | `.dll`, `.ocx` | Code libraries loaded by programs |
| Packaged App Rules | `.appx` | Windows Store apps |

Each collection is configured separately. A company might enable executable rules and script rules but leave DLL rules off. This matters a lot for bypasses - if DLL rules are off, you can load any DLL you want.

> **Critical note on DLL rules:** DLL rules are turned off by default. Always. The reason is performance - every program loads dozens of DLLs when it starts, and checking each one against AppLocker rules slows everything down. Most organizations never enable DLL rules. This is a massive blind spot you will exploit in File 06.

### Two Modes: Audit vs Enforce

AppLocker has two enforcement modes for each collection:

**Audit Only** - AppLocker evaluates every file against its rules, but it does not block anything. It just writes to the Event Log: "this would have been blocked." Companies use this to test rules before enforcing them.

**Enforce Rules** - AppLocker actively blocks files that do not match the rules. If something is not on the approved list, it does not run.

Why this matters for you: when you find AppLocker set to Audit Only, it looks like it is protecting the system but actually is not. A quick check of the AppLocker logs can tell you which mode is active.

---

## Part B: How AppLocker Decides What to Allow

When you try to run a program, here is the exact sequence of events:

```
1. You double-click an .exe (or run it from the command line)

2. Windows kernel calls appid.sys

3. appid.sys asks AppIDSvc: "Is this file allowed?"

4. AppIDSvc checks the file against the rules:
   - Does this file match an ALLOW rule? → Allow it
   - Does this file match a DENY rule? → Block it
   - Does it match nothing? → Block it (default deny)

5. AppIDSvc sends the decision back to appid.sys

6. appid.sys tells the kernel: allow or block

7. If blocked: Windows shows "Access is denied" or the program
   simply fails to start with no message

8. Event Viewer logs what happened
```

The key point in step 4: **default deny**. If AppLocker has rules and a file matches none of them, it is blocked. AppLocker does not allow things unless there is an explicit rule saying yes.

This is why the default rules are so important. If you set up AppLocker with no rules and enable enforcement, nothing runs at all - not even Windows itself.

### The Three Rule Types

AppLocker has three ways to identify a file and decide what to do with it:

---

**Rule Type 1: Publisher (Digital Signature)**

This is the most powerful and the most common rule type.

Every legitimate program from a real company is digitally signed. The signature is like a certificate that says "Microsoft made this" or "Adobe made this." AppLocker can read this signature and make decisions based on it.

Example rule: Allow anything signed by Microsoft Corporation.

This means every Microsoft-signed program - Notepad, Calculator, PowerShell, Word, everything - is automatically allowed. One rule covers thousands of programs.

You can get even more specific:
- Allow only this specific product (e.g., Microsoft Office)
- Allow only this specific file (e.g., winword.exe)
- Allow only versions above a certain number

Why attackers care: if you can get your malicious code signed by a trusted publisher, it bypasses publisher-based rules. This is obviously difficult. But what is easier is finding a legitimate signed program that can be abused - which is exactly what LOLBins are.

---

**Rule Type 2: Path**

Path rules allow or block files based on where they are stored on disk.

Example rule: Allow everything in `C:\Program Files\` and `C:\Windows\`.

This is the simplest rule to set up and the weakest. Here is why: path rules trust the location, not the file. If an attacker can write a malicious file into an allowed path, AppLocker allows it without question.

Allowed paths that are often writable by regular users (making path rules exploitable):
- `C:\Windows\Tasks\`
- `C:\Windows\Temp\`
- `C:\Windows\tracing\`
- `C:\Windows\System32\spool\drivers\color\`

These are writable because Windows needs normal users to write to them. But if they are inside `C:\Windows\`, an AppLocker path rule saying "allow everything in C:\Windows\" covers them too.

---

**Rule Type 3: File Hash**

Hash rules use a fingerprint of the exact file content.

Every file has a hash - a mathematical calculation run against its bytes that produces a unique string. If you change even one byte of the file, the hash changes completely.

Example rule: Allow the file whose SHA-256 hash is `a1b2c3d4...`.

This is the most precise rule. The exact file and only that exact file is allowed. But it breaks every time the file is updated - because the new version has a different hash. Maintaining hash rules for constantly-updated software is a maintenance nightmare.

---

## Lab 1: Check What AppLocker Rules Exist Right Now

Before setting anything up, check the current state. Run this in PowerShell on your Windows 11 VM:

```powershell
Get-AppLockerPolicy -Effective -Xml
```

If AppLocker has never been configured, you will see something like:

```xml
<AppLockerPolicy Version="1">
</AppLockerPolicy>
```

Empty. No rules. This means if AppLocker enforcement were enabled right now with no rules, nothing could run - not even Windows itself. This is why the first step when setting up AppLocker is always to create default rules.

You can also check via the registry where AppLocker stores its policy:

```powershell
Get-ChildItem "HKLM:\SOFTWARE\Policies\Microsoft\Windows\SrpV2"
```

If you get an error saying the path does not exist, AppLocker has never been configured. If you see keys named `Exe`, `Script`, `Msi`, `Dll`, `Appx` - those are the rule collections with rules stored inside.

Write down what you see. You will compare this after the setup in the next lab.

---

## Part C: How AppLocker Rules Are Set Up

AppLocker is configured through Group Policy. Group Policy is Windows' central system for applying settings to computers and users across a company. On a standalone machine (like your lab VM), you use the Local Group Policy Editor.

Understanding what Group Policy is matters for the bypasses. Group Policy settings are applied at startup and periodically refreshed. AppLocker rules live inside Group Policy. If you can modify the right registry keys, you can alter AppLocker rules - but that requires admin access and is noisy. The cleaner approach is to find what the rules allow and slip through gaps.

### The Condition That Makes Default Rules Matter

When you enable AppLocker on a real collection (say, Executable Rules) with no rules at all and set it to Enforce, **nothing can run**. Not Notepad, not PowerShell, not Windows itself. The system may become unusable.

This is why "Create Default Rules" is the first thing you do. Default rules create three automatic allow rules:

1. Allow everything in `C:\Windows\` (covers all Windows system files)
2. Allow everything in `C:\Program Files\` (covers installed software)
3. Allow everything run by local Administrators (admins can always run anything)

These three rules mean normal Windows use keeps working. AppLocker only blocks things that fall outside these three zones.

---

## Lab 2: Enable AppLocker and Create Default Rules

Do this on your Windows 11 Enterprise VM. You need to be logged in as Administrator.

### Step 1 - Start the AppLocker Service

AppLocker needs its background service running. Open Command Prompt as Administrator and run:

```cmd
sc config AppIDSvc start= auto
sc start AppIDSvc
```

Verify it started:

```cmd
sc query AppIDSvc
```

Expected output:
```
SERVICE_NAME: AppIDSvc
        TYPE               : 20  WIN32_SHARE_PROCESS
        STATE              : 4  RUNNING
```

`STATE: 4 RUNNING` means it is active. If you see `STOPPED` the service did not start - try rebooting and running the command again.

### Step 2 - Open Group Policy Editor

Press `Win + R`, type `gpedit.msc`, press Enter.

The Local Group Policy Editor opens. This is the control panel for every policy setting on this machine.

### Step 3 - Navigate to AppLocker

In the left panel, expand these folders in order:

```
Computer Configuration
  └── Windows Settings
        └── Security Settings
              └── Application Control Policies
                    └── AppLocker
```

Click on **AppLocker**. In the right panel you will see:

```
Executable Rules
Windows Installer Rules
Script Rules
Packaged app Rules
DLL Rules
```

These are the five rule collections.

### Step 4 - Create Default Rules for Each Collection

Right-click on **Executable Rules** and select **Create Default Rules**.

Three rules appear automatically:
- `(Default Rule) All files located in the Program Files folder`
- `(Default Rule) All files located in the Windows folder`
- `(Default Rule) All files`  (this one applies only to the local Administrators group)

Do the same for **Script Rules**: right-click > **Create Default Rules**.

Do the same for **Windows Installer Rules**: right-click > **Create Default Rules**.

Leave **DLL Rules** and **Packaged app Rules** alone for now.

### Step 5 - Enable Enforcement

Right-click on **AppLocker** (the parent, not the sub-items) and click **Properties**.

A window opens with tabs for each collection. For **Executable Rules**, change the dropdown from `Not configured` to `Enforce rules`. Do the same for **Script Rules**.

Click OK.

### Step 6 - Apply the Policy

Open Command Prompt as Administrator and run:

```cmd
gpupdate /force
```

Expected output:
```
Updating policy...
Computer Policy update has completed successfully.
User Policy update has completed successfully.
```

AppLocker is now active with default rules enforcing.

### Step 7 - Verify AppLocker is Working

Run this in PowerShell:

```powershell
Get-AppLockerPolicy -Effective -Xml
```

Now you will see actual rules in the XML output instead of the empty output from before. You should see rules for `Exe` and `Script` collections with three entries each.

Also verify the service is still running:

```cmd
sc query AppIDSvc
```

Still `RUNNING`. Good.

---

## Part D: How AppLocker Logs Events

AppLocker logs everything it does to the Windows Event Log. This is how security analysts see what is being blocked - and it is also how you, as a tester, can see whether AppLocker is actually doing anything.

### The Event IDs You Need to Know

| Event ID | What Happened |
|----------|--------------|
| 8003 | A file was allowed to run (Audit mode only - would have been blocked) |
| 8004 | A file was **blocked** from running (Enforce mode) |
| 8005 | A script was allowed (Audit mode) |
| 8007 | A script was **blocked** (Enforce mode) |
| 8006 | A DLL was blocked (Enforce mode, DLL rules enabled) |

Event ID 8004 is your most important one. Every time AppLocker blocks something, 8004 fires. If you are doing bypass testing and 8004 events stop appearing, it means AppLocker is either not enforcing or your bypass worked.

### Where to Find AppLocker Logs

The logs are not in the main Windows Logs area. They are in the Applications and Services Logs section.

Open Event Viewer:
- Press `Win + R`, type `eventvwr.msc`, press Enter

Navigate to:
```
Applications and Services Logs
  └── Microsoft
        └── Windows
              └── AppLocker
```

Inside you will find separate logs for EXE and DLL, MSI and Script, and Packaged app-Deployment.

---

## Lab 3: Test That AppLocker is Blocking Things

Now test that the rules you created actually work.

### Test 1 - Try to Run Something From a Blocked Location

Create a test batch file in a location that is NOT in Program Files or Windows:

```cmd
echo @echo off > C:\Users\Public\test.bat
echo echo This ran >> C:\Users\Public\test.bat
```

Now try to run it:

```cmd
C:\Users\Public\test.bat
```

Expected result - it is blocked. You will either see:
```
Access is denied.
```
Or the file simply does not run.

Check Event Viewer. Go to the AppLocker > MSI and Script log. You should see an Event ID 8007 entry showing the batch file was blocked.

### Test 2 - Confirm Allowed Locations Still Work

Copy the same batch file to a location that IS allowed:

```cmd
copy C:\Users\Public\test.bat C:\Windows\Temp\test.bat
```

Run it:

```cmd
C:\Windows\Temp\test.bat
```

Wait - this is inside `C:\Windows\`, which is an allowed path. It should run.

Did it? If yes, AppLocker is working correctly - it blocks things outside allowed paths and allows things inside them.

> **This is already a hint at a bypass.** If `C:\Windows\Temp\` is writable by regular users AND AppLocker allows everything in `C:\Windows\`, then a regular user can drop anything into `C:\Windows\Temp\` and run it. This is a path-based bypass we will explore in File 04.

### Test 3 - Check Execution Policy vs AppLocker for Scripts

Go back to your `C:\test.ps1` from File 02. Try running it with the bypass flag:

```powershell
powershell -ExecutionPolicy Bypass -File C:\test.ps1
```

`C:\` is not in an allowed path. If AppLocker script rules are enforcing, this should be blocked - regardless of the `-ExecutionPolicy Bypass` flag.

Expected output:
```
C:\test.ps1 cannot be loaded. The file C:\test.ps1 is not digitally signed.
You cannot run this script on the current system.
```

Or a different error depending on how AppLocker is configured. Either way - blocked.

This confirms something important: **execution policy bypass and AppLocker are separate systems**. Bypassing execution policy does not bypass AppLocker. You need to defeat both independently.

Check the AppLocker log again. You should see an 8007 event for the blocked PowerShell script.

---

## Part E: Where AppLocker's Default Rules Leave Gaps

The default rules allow everything in `C:\Windows\` and `C:\Program Files\`. This sounds comprehensive. It is not. Here are the problems:

### Problem 1: Writable Folders Inside Allowed Paths

Several folders inside `C:\Windows\` are writable by regular users:

```
C:\Windows\Tasks
C:\Windows\Temp
C:\Windows\tracing
C:\Windows\System32\spool\drivers\color
C:\Windows\System32\Tasks
```

AppLocker's path rule says "allow everything in C:\Windows\". It does not check who wrote the file or when. If a regular user drops a malicious executable into `C:\Windows\Temp\` and runs it, AppLocker's default rule allows it.

### Problem 2: LOLBins

Every program in `C:\Windows\System32\` is automatically allowed by the default rules. This includes legitimate Windows tools like:

- `mshta.exe` - runs HTML application files
- `certutil.exe` - certificate tool that can also download files and decode content
- `rundll32.exe` - runs code from DLL files
- `regsvr32.exe` - registers COM components, can execute remote scripts
- `msbuild.exe` - compiles and runs C# code from XML files

All of these are in `C:\Windows\System32\`. All are allowed by default AppLocker rules. All can be abused to run code that AppLocker never checks. These are the LOLBins covered in File 04.

### Problem 3: Trusted Publishers Signing Bad Things

Publisher rules say "trust anything from Microsoft." If an attacker can get code into a legitimate Microsoft-signed tool - for example, by placing code that a Microsoft tool then executes - AppLocker sees the Microsoft-signed tool and allows it, never knowing what it actually ran.

### Problem 4: DLL Rules Are Off

Because DLL rules are disabled by default, anything you can load as a DLL is completely invisible to AppLocker. Drop a malicious DLL anywhere, load it through any allowed program, and AppLocker never sees it. This is File 06.

---

## Lab 4: Read the AppLocker Effective Policy

This is something real penetration testers do the moment they land on a Windows machine. Read the AppLocker rules to understand what is allowed and where the gaps are.

Run this in PowerShell on your Windows 11 VM:

```powershell
Get-AppLockerPolicy -Effective | ConvertFrom-Json
```

Or for a cleaner view of just the allowed paths:

```powershell
$policy = Get-AppLockerPolicy -Effective -Xml
[xml]$xml = $policy
$xml.AppLockerPolicy.RuleCollection | ForEach-Object {
    Write-Host "=== $($_.Type) - $($_.EnforcementMode) ===" -ForegroundColor Cyan
    $_.FilePathRule | ForEach-Object {
        Write-Host "  Path: $($_.Conditions.FilePathCondition.Path)"
    }
}
```

Expected output (with default rules configured):

```
=== Exe - Enabled ===
  Path: %PROGRAMFILES%\*
  Path: %WINDIR%\*
=== Script - Enabled ===
  Path: %PROGRAMFILES%\*
  Path: %WINDIR%\*
=== Msi - NotConfigured ===
```

You can now see exactly which paths are trusted. `%WINDIR%` is `C:\Windows`. `%PROGRAMFILES%` covers both `C:\Program Files` and `C:\Program Files (x86)`.

Look at that output and ask: where can a regular user write files that falls inside these paths? The answer to that question is where your bypass starts.

---

## Part F: What AppLocker Cannot Do

Before moving to the bypass files, be clear on what AppLocker fundamentally cannot control:

**It cannot inspect what a trusted program does.** AppLocker checks if a program is allowed to start. Once it starts, AppLocker has no visibility into what that program does. If `mshta.exe` is allowed and you pass it a malicious script, AppLocker does not know.

**It cannot control COM objects.** AppLocker has no concept of COM. When a script creates a COM object to run code, AppLocker never sees it.

**It cannot check DLLs (unless DLL rules are on, which they are not by default).** Any DLL loaded by any allowed program is invisible to AppLocker.

**It cannot check in-memory code.** Code that is downloaded and run entirely in memory, never written to a file on disk, has nothing for AppLocker to evaluate.

**It cannot stop code run by allowed interpreters.** If PowerShell is allowed to run, and you pass it commands via `-EncodedCommand` or `-Command`, those commands are not script files. AppLocker blocks script files. A string of code passed on the command line is not a file.

Each of these limitations is a technique. The next files each exploit one of them.

---

## Summary

| Concept | Key Point |
|---------|-----------|
| AppIDSvc | The service that evaluates files against rules |
| appid.sys | Kernel driver that enforces the decisions |
| Rule collections | Separate rulesets for exe, scripts, DLLs, installers, packaged apps |
| DLL rules | Off by default - massive blind spot |
| Audit vs Enforce | Audit logs but does not block. Enforce actually blocks. |
| Default rules | Allow C:\Windows\, C:\Program Files\, and all for Admins |
| Publisher rules | Trust by digital signature - most common, most powerful |
| Path rules | Trust by location - weakest, many writable subfolders inside allowed paths |
| Hash rules | Trust exact file - breaks on updates, hard to maintain |
| Event ID 8004 | Executable blocked. Your most important log event. |
| Event ID 8007 | Script blocked. |

AppLocker is now running in your lab. Default rules are in place. You have verified it blocks scripts from outside allowed paths and you have seen the Event Log entries it creates.

The next file uses these exact gaps to bypass it.

---

**Next: [04-lolbins-lab-from-scratch.md](./04-lolbins-lab-from-scratch.md)**
