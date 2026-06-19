# AppLocker - How It Actually Works

Before you break something, you need to understand it. Not just "AppLocker blocks programs" - that is the Wikipedia version. You need to know what is actually happening under the hood when AppLocker decides to allow or block something. Because the bypasses in the next files all come directly from how AppLocker works internally.

So let's build that understanding, piece by piece. And while we do that, we'll set it up in your lab so you have something real to test against.

---

## Let's Start With What AppLocker Actually Is

Most people think AppLocker is a single program sitting somewhere watching what you run. It is not. It is two separate pieces working together, and understanding what each one does changes how you think about bypassing it.

**Piece 1: AppIDSvc (Application Identity Service)**

This is a Windows service - a background process that runs constantly. Its one job is to figure out the "identity" of any file that tries to run. Who made it? Where did it come from? What is its cryptographic fingerprint? AppIDSvc answers these questions.

Think of it like the TSA database system at an airport. When you scan your boarding pass, the system looks you up and returns an answer - cleared or flagged. AppIDSvc is that database lookup system.

**Piece 2: appid.sys (a kernel-mode driver)**

The kernel is the lowest layer of Windows - the part that talks directly to hardware and controls every running process. `appid.sys` lives here.

When any executable tries to start, `appid.sys` intercepts it before it runs a single instruction, asks AppIDSvc for a decision, and either lets it through or kills it right there. The key word is "before." The program does not start and then get stopped. It never starts at all.

This is different from antivirus, which often scans files while they run. AppLocker is a gate, not a checkpoint inside the road.

---

Let's verify AppIDSvc is actually there on your machine. Open PowerShell and run:

```powershell
Get-Service AppIDSvc
```

You will see:

```
Status   Name               DisplayName
------   ----               -----------
Stopped  AppIDSvc           Application Identity
```

It is stopped. That is normal on a fresh Windows install. AppLocker does not enforce anything until this service is running. This matters: **if AppIDSvc is stopped, AppLocker is completely disabled**. Keep that in mind.

---

## What AppLocker Can Actually Control

AppLocker does not watch everything. It watches specific file types, organized into five groups called "rule collections." Each collection is independent - you can enable some and leave others off.

| Collection | Files It Watches |
|------------|-----------------|
| Executable Rules | `.exe`, `.com` |
| Script Rules | `.ps1`, `.bat`, `.cmd`, `.vbs`, `.js` |
| Windows Installer Rules | `.msi`, `.msp`, `.mst` |
| Packaged App Rules | `.appx` (Store apps) |
| DLL Rules | `.dll`, `.ocx` |

Here is the thing that should immediately catch your attention: **DLL rules are off by default**. Not just unconfigured - Microsoft specifically leaves them disabled because enabling them tanks system performance. Every program that runs loads tens or hundreds of DLLs. Checking each one against AppLocker rules is expensive.

The result? On virtually every AppLocker deployment you will ever encounter, DLL loading is completely unmonitored. Drop a malicious DLL anywhere, load it through a trusted program, and AppLocker never sees it. That entire attack surface is wide open by default. We exploit this in File 06.

---

## The Two Modes: Audit and Enforce

Each rule collection has two modes:

**Audit Only:** AppLocker evaluates files against the rules but does not block anything. It just writes to the Windows Event Log saying "this would have been blocked." Companies use this phase to figure out which rules they need before they start blocking things.

**Enforce Rules:** AppLocker actively blocks files that do not have a matching allow rule.

Why does this matter for you? If you land on a machine and AppLocker is running in Audit mode, it looks like it is protecting the system - but it is not blocking a thing. Checking the mode is one of the first things you do.

Let's check right now on your VM. Run this in PowerShell:

```powershell
Get-AppLockerPolicy -Effective -Xml
```

On a fresh machine with no AppLocker configured, you will get:

```xml
<AppLockerPolicy Version="1">
</AppLockerPolicy>
```

Empty. No rules, no enforcement mode, nothing. AppLocker exists as a feature on this machine but it is doing absolutely nothing right now. That is the state we are about to change.

---

## How AppLocker Decides: The Three Rule Types

When AppLocker does have rules, it uses three different ways to identify a file. Understanding each one tells you exactly where the gaps are.

### Publisher Rules (Trusting the Signature)

Every legitimate program from a real company is digitally signed. The signature is a cryptographic stamp that says "I am Microsoft" or "I am Adobe" and cannot be faked without the private key.

AppLocker can read that stamp and make decisions based on it. A publisher rule looks like: "Allow any file signed by Microsoft Corporation." That one rule covers thousands of Windows programs - Notepad, PowerShell, Windows Defender, everything Microsoft ships.

You can narrow it down further: allow only a specific product, or only a specific version range. This flexibility is why publisher rules are the most commonly used type.

**The attack angle:** Publisher rules trust the stamp, not what the program does. If `mshta.exe` is signed by Microsoft and you write a rule that allows everything signed by Microsoft, AppLocker will happily let `mshta.exe` run - even if you use it to execute malicious code. The signature is valid. AppLocker does not care what the program does after it starts.

### Path Rules (Trusting the Location)

Path rules allow or block based on where a file is stored. "Allow everything in `C:\Windows\`" or "Allow everything in `C:\Program Files\`."

This is the simplest rule type to understand and the weakest to rely on. The rule trusts the location, not the file. It does not check who created the file or when. If an attacker writes a malicious executable into an allowed folder, AppLocker allows it without question.

**The attack angle:** Several folders inside `C:\Windows\` are writable by regular users because Windows needs them to be writable for legitimate reasons:

```
C:\Windows\Temp
C:\Windows\Tasks
C:\Windows\tracing
C:\Windows\System32\spool\drivers\color
C:\Windows\System32\Tasks
```

A path rule saying "allow everything in C:\Windows\" covers all of these. A regular user can drop anything into `C:\Windows\Temp\` and AppLocker's default rules will allow it to run.

### Hash Rules (Trusting the Exact File)

A file hash is a mathematical fingerprint calculated from every byte in a file. Change one byte and the hash changes completely. Hash rules say: "Allow the exact file whose SHA-256 hash is `a1b2c3...`."

This is the most precise type. Only that specific file, untampered, is allowed.

**The practical problem:** Every time a program updates, its bytes change, which means its hash changes. A hash rule for Chrome, for example, would break every time Chrome updates. Maintaining hash rules for real software is a constant maintenance burden. In practice, hash rules are used for custom internal tools that never change.

---

## Setting Up AppLocker in Your Lab

Enough reading. Let's set it up so you have something to actually test against.

Everything below is done on your **Windows 11 Enterprise VM**, logged in as Administrator.

### First: Start the AppLocker Service

Open Command Prompt as Administrator and run these two commands:

```cmd
sc config AppIDSvc start= auto
sc start AppIDSvc
```

The first command tells Windows to automatically start this service at boot. The second starts it right now.

Verify it is running:

```cmd
sc query AppIDSvc
```

You are looking for this:

```
SERVICE_NAME: AppIDSvc
        STATE              : 4  RUNNING
```

`STATE 4 RUNNING` - good. If it shows `STOPPED`, reboot the VM and run `sc start AppIDSvc` again.

---

### Second: Open the Group Policy Editor

Press `Win + R`, type `gpedit.msc`, hit Enter.

Group Policy Editor is the central configuration tool for Windows security settings. AppLocker lives here. On a real corporate network, these settings would be pushed from a domain controller to every machine. In your lab, you are configuring the local machine directly.

In the left panel, navigate here:

```
Computer Configuration
  └── Windows Settings
        └── Security Settings
              └── Application Control Policies
                    └── AppLocker
```

Click on AppLocker. You will see the five rule collections in the right panel.

---

### Third: Create Default Rules

Here is something important to understand before you enable enforcement: if you turn on AppLocker enforcement with zero rules, nothing runs. Not Notepad, not PowerShell, not Windows Explorer. The machine becomes unusable.

Default rules are the safety net. They automatically allow:
- Everything in `C:\Windows\` (all Windows system files)
- Everything in `C:\Program Files\` (all installed software)
- Everything for the local Administrators group (admins can always run anything)

These three rules mean normal Windows use keeps working after you enable enforcement.

Right-click on **Executable Rules** and select **Create Default Rules**. Watch three rules appear:

```
(Default Rule) All files located in the Windows folder
(Default Rule) All files located in the Program Files folder
(Default Rule) All files  [this one is for Administrators only]
```

Now do the same for **Script Rules**: right-click > **Create Default Rules**.

Leave DLL Rules, Windows Installer Rules, and Packaged App Rules alone.

---

### Fourth: Enable Enforcement

Right-click on **AppLocker** (the parent item, not the sub-items) and select **Properties**.

You will see tabs for each collection. Under **Executable Rules**, change the dropdown from `Not configured` to `Enforce rules`. Do the same for **Script Rules**.

Click OK.

---

### Fifth: Apply It

Back in Command Prompt (as Administrator):

```cmd
gpupdate /force
```

You will see:

```
Updating policy...
Computer Policy update has completed successfully.
User Policy update has completed successfully.
```

AppLocker is now active and enforcing. Let's make sure.

Run this in PowerShell:

```powershell
Get-AppLockerPolicy -Effective -Xml
```

This time, instead of the empty XML from before, you will see rules. Look for `RuleCollection Type="Exe" EnforcementMode="Enabled"` and `RuleCollection Type="Script" EnforcementMode="Enabled"`. Those words `EnforcementMode="Enabled"` confirm rules are being enforced, not just logged.

---

## Testing That AppLocker Is Actually Blocking Things

Knowing AppLocker is configured is different from knowing it works. Let's test it.

### Test 1: Block Something

Create a simple batch file in a location that is NOT in an allowed path:

```cmd
echo echo This script ran > C:\Users\Public\test.bat
```

Now try to run it:

```cmd
C:\Users\Public\test.bat
```

What you will see:

```
Access is denied.
```

Or depending on context, nothing happens at all - the file just does not execute. Either way, AppLocker blocked it.

Now check the Event Log to confirm. Open Event Viewer:
- Press `Win + R`, type `eventvwr.msc`, Enter

Navigate to:
```
Applications and Services Logs
  └── Microsoft
        └── Windows
              └── AppLocker
                    └── MSI and Script
```

You should see an entry with Event ID **8007**. Double-click it. The description will tell you the exact file that was blocked, the user who tried to run it, and the rule that caused the block (in this case, no matching rule).

That is AppLocker doing its job.

---

### Test 2: Confirm Allowed Paths Work

Copy that same file to a location inside `C:\Windows\`:

```cmd
copy C:\Users\Public\test.bat C:\Windows\Temp\test.bat
```

Run it:

```cmd
C:\Windows\Temp\test.bat
```

What you will see:

```
This script ran
```

It ran. Because `C:\Windows\Temp\` is inside `C:\Windows\`, and the default rule allows everything in `C:\Windows\`.

Here is the thing - `C:\Windows\Temp\` is writable by regular users. Any user on this machine can put a file there. And AppLocker just told you it will run anything from there.

That right there is your first bypass hint. It is not a bug. It is the default configuration working exactly as designed. The design just has a gap.

---

### Test 3: Prove Execution Policy Bypass Does NOT Bypass AppLocker

Remember the `-ExecutionPolicy Bypass` flag from File 02? Let's see what happens when AppLocker is involved.

Take the `C:\test.ps1` script you created in File 02. Try running it with the bypass flag:

```powershell
powershell -ExecutionPolicy Bypass -File C:\test.ps1
```

What you will see - not an execution policy error, but an AppLocker error:

```
C:\test.ps1 cannot be loaded. The file C:\test.ps1 is not digitally signed.
You cannot run this script on the current system.
    + CategoryInfo    : SecurityError
```

Or sometimes:

```
Access to the path 'C:\test.ps1' is denied.
```

Either way: blocked. The `-ExecutionPolicy Bypass` flag bypasses PowerShell's execution policy. It does absolutely nothing to AppLocker. They are completely separate systems.

This is a crucial thing to internalize: **bypassing one layer does not bypass the other**. Execution policy and AppLocker both need to be handled, independently. The later files show you how.

---

## Reading the Rules Like an Attacker

When a penetration tester lands on a machine, one of the first things they do is read the AppLocker policy. Not to admire it - to find the gaps.

Run this in PowerShell:

```powershell
$policy = Get-AppLockerPolicy -Effective -Xml
[xml]$xml = $policy
$xml.AppLockerPolicy.RuleCollection | ForEach-Object {
    $collection = $_
    Write-Host "`n=== $($collection.Type) ($($collection.EnforcementMode)) ===" -ForegroundColor Cyan
    $collection.FilePathRule | ForEach-Object {
        Write-Host "  ALLOW (path): $($_.Conditions.FilePathCondition.Path)"
    }
    $collection.FilePublisherRule | ForEach-Object {
        Write-Host "  ALLOW (publisher): $($_.Conditions.FilePublisherCondition.PublisherName)"
    }
}
```

What you will see:

```
=== Exe (Enabled) ===
  ALLOW (path): %PROGRAMFILES%\*
  ALLOW (path): %WINDIR%\*

=== Script (Enabled) ===
  ALLOW (path): %PROGRAMFILES%\*
  ALLOW (path): %WINDIR%\*

=== Msi (NotConfigured) ===

=== Dll (NotConfigured) ===

=== Appx (NotConfigured) ===
```

Read that output and think like an attacker:

- `%WINDIR%\*` means everything in `C:\Windows\` is allowed. Where in `C:\Windows\` can a regular user write files? That is your path bypass.
- `%PROGRAMFILES%\*` means `C:\Program Files\`. Users cannot write there by default - not useful.
- `Msi: NotConfigured` means installer rules are not enforced.
- `Dll: NotConfigured` means DLL rules are not enforced. That entire attack surface is open.
- `Exe (Enabled)` - executables are enforced.
- `Script (Enabled)` - scripts are enforced.

With this single command output, you already know: run executables from `C:\Windows\Temp\`, use LOLBins already in `C:\Windows\System32\`, load DLLs freely, use installer files freely. That is most of the bypass surface right there.

---

## What AppLocker Simply Cannot Do

Before we move to the actual bypasses, you need to understand AppLocker's hard limits - the things it cannot control no matter how well it is configured.

**It cannot see inside allowed programs.** Once an allowed program starts running, AppLocker is done with it. What that program does next - what it downloads, what it executes, what it reads - AppLocker has no visibility. `mshta.exe` is allowed. You pass it a script. AppLocker sees `mshta.exe`, gives the thumbs up, and exits the picture. Whatever `mshta.exe` does with your script happens outside AppLocker's view.

**It cannot control COM objects.** COM is a Windows system that lets programs communicate and share functionality. Certain COM objects can execute commands. When a script creates a COM object to run code, there is no file being executed - just two programs talking. AppLocker has no hook into this.

**It cannot check DLLs (when DLL rules are off).** Which, as established, they almost always are. Any DLL loaded by any allowed program is completely invisible.

**It cannot evaluate in-memory code.** Code that lives only in RAM - never written to a file - has nothing for AppLocker to evaluate. AppLocker is file-based. No file, no check.

**It cannot check command-line arguments.** If PowerShell is allowed and you run `powershell -Command "malicious code here"`, AppLocker sees PowerShell start (allowed), and exits. The string of code you passed is not a file. AppLocker does not touch it.

---

Each one of those limitations is a bypass technique. The LOLBins file exploits the first one. The COM file exploits the second. DLL hijacking exploits the third. PowerShell encoding exploits the last two.

That is why you needed to understand how AppLocker works before learning how to bypass it. Every bypass is a direct consequence of a real design decision. Nothing here is magic - it is just knowing the system well enough to walk around it.

---

## Quick Reference

| Thing | What to Know |
|-------|-------------|
| AppIDSvc | The service that does policy lookups. If it is stopped, AppLocker is dead. |
| appid.sys | Kernel driver that enforces decisions. Blocks before execution starts. |
| DLL rules | Off by default on every real deployment. Huge blind spot. |
| Audit mode | Logs but does not block. Looks like protection, is not. |
| Enforce mode | Actually blocks. What you just set up. |
| Default rules | Trust `C:\Windows\` and `C:\Program Files\`. Many writable subfolders inside. |
| Publisher rules | Trust by signature. LOLBins exploit this - they are validly signed. |
| Path rules | Trust by location. Writable subfolders inside trusted paths break this. |
| Hash rules | Most precise, breaks on updates, rarely used at scale. |
| Event ID 8004 | An executable was blocked. |
| Event ID 8007 | A script was blocked. |

---

**Next: [04-lolbins-lab-from-scratch.md](./04-lolbins-lab-from-scratch.md)**
