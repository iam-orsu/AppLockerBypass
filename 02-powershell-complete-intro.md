# PowerShell - Complete Introduction From Zero

This file teaches PowerShell from absolute zero. You do not need to know anything about programming or command lines. Everything is explained before it is used.

By the end of this file, you will understand what PowerShell is, how it works, and why it matters for security testing.

---

## Part A: What is PowerShell?

### The Simple Version

PowerShell is a tool that lets you control Windows by typing commands.

Instead of clicking through menus and windows, you type an instruction and Windows executes it. That is the core idea.

For example, instead of opening Task Manager to see running programs, you can type one line in PowerShell and get the same information - faster, with more detail, and in a format you can work with programmatically.

### How is it Different From Command Prompt?

You have probably seen Command Prompt (cmd.exe) before. PowerShell and Command Prompt are both tools for typing commands. But they are very different under the hood.

**Command Prompt** was built in the 1980s. It was designed for DOS (an older operating system). It can do basic things like copy files, navigate folders, and run programs. It has not changed much in decades.

**PowerShell** was built by Microsoft in 2006, specifically for Windows administration. It is built on top of .NET, which is Microsoft's modern software framework. This means PowerShell can interact with almost every part of Windows at a deep level.

Here is the key difference in practice:

| Task | Command Prompt | PowerShell |
|------|----------------|------------|
| List running processes | `tasklist` (gives raw text) | `Get-Process` (gives structured data you can filter) |
| Stop a process | `taskkill /PID 1234` | `Stop-Process -Id 1234` |
| Download a file from internet | Not built in | `Invoke-WebRequest -Uri "url" -OutFile "file"` |
| Create a scheduled task | Complicated | Simple built-in commands |
| Work with Active Directory | Not possible | Full support built in |

The big difference: Command Prompt gives you raw text. PowerShell gives you objects - structured data you can sort, filter, and pass from one command to another.

### Why Do Security Researchers Use PowerShell?

PowerShell is extremely popular in security testing. Here is why:

**1. It is already on every Windows computer.**
You do not need to install anything. PowerShell is built into Windows. This means an attacker does not need to bring tools - they can use what is already there.

**2. It can do almost anything.**
PowerShell can download files from the internet, create processes, modify the registry, interact with network services, read and write files anywhere on the system, and more. It is effectively a full programming language with access to all of Windows.

**3. It runs in memory.**
PowerShell commands and scripts can run entirely in memory without ever writing files to disk. This makes detection harder because security tools often look for suspicious files on disk.

**4. It can be hidden.**
Commands can be encoded in ways that make them hard to read. A PowerShell command that downloads and runs malware can look like random characters at first glance.

**5. It is trusted.**
Because PowerShell is a Microsoft tool, security controls like AppLocker often allow it to run. This trust is exactly what attackers exploit.

### Why Do Companies Fear It?

For the same reasons. PowerShell gives administrators incredible power - and that same power is available to attackers. A single PowerShell command can:

- Download malware from the internet
- Dump all passwords from Windows memory
- Spread to other computers on the network
- Create backdoors that survive reboots
- Disable antivirus software

This is why companies try to lock down PowerShell. And this is why bypassing those restrictions is a core skill in penetration testing.

---

## Part B: How PowerShell Works

Before you run a single command, it helps to understand what actually happens when you type something into PowerShell.

### The Flow

```
You type a command
        |
        v
PowerShell reads and parses what you typed
        |
        v
PowerShell checks if the command is valid
        |
        v
PowerShell calls the relevant Windows functions
        |
        v
Windows does the work
        |
        v
PowerShell receives the result
        |
        v
PowerShell displays the result to you
```

When you type `Get-Process`, you are not directly talking to Windows. You are telling PowerShell to call the Windows API (Application Programming Interface) that returns a list of running processes. PowerShell then takes that data and formats it for you to read.

This is important for security reasons. PowerShell sits between you and Windows. Security features like execution policies and AppLocker restrictions operate at the PowerShell layer. But as you will learn later, there are ways to go around that layer entirely.

### Where PowerShell Lives on Disk

PowerShell itself is just a program. You can find it at:

```
C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe
```

The `v1.0` in the path is misleading - even modern PowerShell 5.1 lives in this folder. It is a legacy naming convention.

There is also a 32-bit version at:

```
C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe
```

Knowing these paths matters for AppLocker. AppLocker can be configured to block PowerShell, but it needs to block BOTH locations. If only one is blocked, an attacker just uses the other.

---

## Part C: Basic PowerShell Syntax

This section breaks down PowerShell's language piece by piece. You do not need to memorize all of this now. The goal is to understand the pattern so that when you see PowerShell code later, you can read it.

### Cmdlets - The Basic Commands

PowerShell commands are called "cmdlets" (pronounced "command-lets").

Every cmdlet follows the same pattern:

```
Verb-Noun
```

Examples:
- `Get-Process` - Get (retrieve) a list of Processes
- `Stop-Process` - Stop (end) a Process
- `Get-Content` - Get the Content of a file
- `Set-ExecutionPolicy` - Set the ExecutionPolicy setting
- `Invoke-WebRequest` - Invoke (make) a WebRequest

This consistent naming makes PowerShell predictable. Once you know the pattern, you can often guess what a command does just by reading its name.

### Parameters - Giving Instructions to Cmdlets

Cmdlets on their own do a general thing. Parameters tell them to do something specific.

Parameters start with a dash `-`.

Example without parameter:
```powershell
Get-Process
```
This returns a list of ALL running processes.

Example with parameter:
```powershell
Get-Process -Name "notepad"
```
This returns only the process named "notepad".

Some parameters need a value after them (like `-Name "notepad"`). Some are just flags (like `-Verbose`), which you include or leave out.

### Variables - Storing Information

A variable is a container that holds a piece of information so you can use it later.

In PowerShell, all variables start with `$`.

```powershell
$name = "Alice"
```

This creates a variable called `name` and stores the text "Alice" in it.

You can then use that variable:
```powershell
Write-Host "Hello, $name"
```

Output:
```
Hello, Alice
```

Variables can store different types of data:

```powershell
$number = 42                    # A number
$text = "Hello"                 # Text (called a string)
$list = @("one", "two", "three") # A list (called an array)
$result = Get-Process           # The entire output of a command
```

That last one is important. You can store the output of a command in a variable and then work with it later. This is how PowerShell scripts are built.

### The Pipeline - Chaining Commands

The pipeline is one of PowerShell's most powerful features. The pipe character `|` takes the output of one command and passes it as input to the next.

Example:

```powershell
Get-Process | Where-Object { $_.Name -like "chrome" }
```

Break this down:
- `Get-Process` - gets all running processes
- `|` - passes that list to the next command
- `Where-Object` - filters the list
- `{ $_.Name -like "chrome" }` - the filter condition: keep only items where the Name contains "chrome"
- `$_` - this is a special variable that represents "the current item" as the pipeline loops through each process

The result: only Chrome processes are shown.

Another example - count how many processes are running:

```powershell
Get-Process | Measure-Object
```

Or sort processes by how much memory they use:

```powershell
Get-Process | Sort-Object WorkingSet -Descending
```

Pipelines are everywhere in PowerShell. Learn to read them left to right - each `|` is a "then pass this to".

### Strings - Working With Text

Text in PowerShell is surrounded by quotes. There are two types:

**Double quotes** `"..."` - variables inside them get replaced with their value:
```powershell
$name = "Alice"
"Hello, $name"      # Output: Hello, Alice
```

**Single quotes** `'...'` - everything inside is taken literally:
```powershell
$name = "Alice"
'Hello, $name'      # Output: Hello, $name
```

This distinction matters when you are reading PowerShell code. If you see single quotes, the text is literal. If you see double quotes, variables inside will be expanded.

---

## Part D: PowerShell Security Features

This is the important part for security testing. PowerShell has built-in security controls. Understanding what they do - and how they fail - is the foundation of everything that comes next.

### Execution Policy

#### What is it?

Execution Policy is a setting that controls whether PowerShell scripts (.ps1 files) are allowed to run.

When someone (like a company IT department) sets execution policy to "Restricted", PowerShell will refuse to run script files. You can still type individual commands interactively, but you cannot run a saved .ps1 script file.

#### The Different Levels

| Policy | What it Does |
|--------|-------------|
| `Restricted` | No scripts can run at all. Only interactive commands work. |
| `AllSigned` | Scripts can only run if they have a valid digital signature from a trusted source. |
| `RemoteSigned` | Scripts downloaded from the internet must be signed. Scripts you create locally can run without a signature. |
| `Unrestricted` | All scripts run. Shows a warning for internet-downloaded scripts, but does not block them. |
| `Bypass` | Nothing is blocked. No warnings. No prompts. Scripts always run. |

**The default on Windows 11:** `Restricted`

This means out of the box, you cannot run PowerShell scripts by double-clicking or calling them from the command line.

#### The Critical Misunderstanding

Many companies set execution policy to `Restricted` and think their systems are protected. They are not.

Microsoft itself states in their documentation: execution policy is **not a security feature**. It is a convenience feature designed to prevent accidental script execution.

Here is proof: you can override the execution policy for a single session with one parameter:

```powershell
powershell -ExecutionPolicy Bypass -File myscript.ps1
```

This runs `myscript.ps1` regardless of what the system-wide execution policy says. No admin rights needed.

Execution policy is a speed bump, not a wall. It stops accidents. It does not stop intentional attacks.

#### How to Check the Current Policy

Open PowerShell and type:

```powershell
Get-ExecutionPolicy
```

To see the policy at every scope level:

```powershell
Get-ExecutionPolicy -List
```

Output will look like this:

```
        Scope ExecutionPolicy
        ----- ---------------
MachinePolicy       Undefined
   UserPolicy       Undefined
      Process       Undefined
  CurrentUser       Undefined
 LocalMachine      Restricted
```

Each scope is checked from top to bottom. The first one that is not `Undefined` wins. `MachinePolicy` (set by Group Policy) takes highest priority.

### Script Signing - What is it?

Digital signing is a way to prove that a file came from a specific person or organization and has not been changed since it was signed.

Think of it like a wax seal on a letter. The seal proves who sent it and that nobody opened the letter in transit.

When execution policy is set to `AllSigned`, PowerShell checks for this seal on every script. If the seal is missing or from an untrusted source, the script does not run.

In practice, very few organizations enforce `AllSigned` because it requires managing code signing certificates and signing every internal script. The overhead is significant.

### Constrained Language Mode (CLM)

This is more powerful than execution policy - and more relevant to AppLocker bypasses.

#### What is it?

Constrained Language Mode locks down what PowerShell can do, even while it is running.

In normal (Full Language) mode, PowerShell can:
- Access any .NET class
- Create COM objects
- Load external code into memory
- Do essentially anything Windows allows

In Constrained Language Mode, PowerShell is restricted:
- Cannot access most .NET classes
- Cannot create COM objects
- Cannot compile and run C# code inline
- Cannot load arbitrary assemblies from memory

#### How Does AppLocker Trigger CLM?

This is the connection between AppLocker and PowerShell.

When AppLocker has script rules active and a script is not on the approved list, PowerShell does not just block the script. It also puts itself into Constrained Language Mode for the rest of that session.

This means even if an attacker finds a way to run a script, CLM limits what that script can actually do.

Or at least, that is how it is supposed to work. You will learn the bypass methods in File 05.

### AMSI - The Content Scanner

AMSI stands for Antimalware Scan Interface.

When you run a PowerShell command, AMSI takes the content of that command and sends it to your antivirus software for inspection - before the command runs. If the antivirus flags it as malicious, AMSI blocks execution.

The important thing about AMSI: it scans the actual code, not just the file. This means even if you encode or obfuscate a script, PowerShell decodes it first and then AMSI scans the decoded version. You cannot hide malicious code from AMSI just by encoding it.

This is why AMSI bypass is a separate topic from execution policy bypass. They protect against different things.

The details of AMSI bypass are covered in File 05. For now, just know it exists and what it does.

---

## Part E: Lab - First PowerShell Commands

Open PowerShell on your Windows 11 VM now. You can open it by:
- Pressing `Win + X` and clicking **Windows PowerShell**
- Searching for "PowerShell" in the Start menu
- Right-clicking the Start button and selecting **Windows PowerShell**

Do NOT use PowerShell as Administrator for this lab unless instructed. Use a normal user session.

---

### Lab E-1: Check Your PowerShell Version

Type this and press Enter:

```powershell
$PSVersionTable
```

Expected output:

```
Name                           Value
----                           -----
PSVersion                      5.1.22621.4111
PSEdition                      Desktop
PSCompatibleVersions           {1.0, 2.0, 3.0, 4.0, 5.0, 5.1.22621.4111}
BuildVersion                   10.0.22621.4111
CLRVersion                     4.0.30319.42000
WSManStackVersion              3.0
PSRemotingProtocolVersion      2.3
SerializationVersion           1.1.0.1
```

What this tells you:
- `PSVersion 5.1` - you are running Windows PowerShell 5.1. This is the version built into Windows 11.
- `PSEdition Desktop` - "Desktop" means Windows PowerShell (as opposed to "Core" which means PowerShell 7)
- `CLRVersion 4.0` - this is the .NET version underneath PowerShell

**Why this matters for security:** PowerShell version matters because older versions had fewer security controls. PowerShell 2.0 had no AMSI, no Constrained Language Mode, and no Script Block Logging. Attackers used to downgrade to v2 to bypass all controls. On Windows 11, PowerShell 2.0 has been removed entirely - this downgrade attack no longer works.

---

### Lab E-2: Check Execution Policy

```powershell
Get-ExecutionPolicy
```

Expected output:
```
Restricted
```

Now check all scopes:

```powershell
Get-ExecutionPolicy -List
```

Write down what you see. Most scopes will say `Undefined`. The `LocalMachine` scope will say `Restricted`.

---

### Lab E-3: See Running Processes

```powershell
Get-Process
```

You will get a large table of all running processes. The columns are:

| Column | What it means |
|--------|--------------|
| `Handles` | Number of system handles the process has open |
| `NPM(K)` | Non-paged memory in kilobytes |
| `PM(K)` | Paged memory in kilobytes |
| `WS(K)` | Working set (active memory) in kilobytes |
| `CPU(s)` | CPU time used |
| `Id` | Process ID (unique number for this running process) |
| `SI` | Session ID |
| `ProcessName` | The name of the process |

Now filter it. Open Notepad first (Start menu > Notepad), then run:

```powershell
Get-Process | Where-Object { $_.Name -like "notepad" }
```

Expected output:
```
Handles  NPM(K)    PM(K)      WS(K)     CPU(s)     Id  SI ProcessName
-------  ------    -----      -----     ------     --  -- -----------
    260      16     6852      32548       0.19   4532   1 Notepad
```

You filtered the entire list down to just Notepad. The `$_` refers to "the current process" as PowerShell loops through each one. `.Name` is the process name property. `-like` is a comparison that allows wildcard matching.

---

### Lab E-4: Store Output in a Variable

```powershell
$processes = Get-Process
```

No output appears. The data is stored in `$processes`. Now query it:

```powershell
$processes.Count
```

This tells you how many processes are running. Then:

```powershell
$processes | Where-Object { $_.WorkingSet -gt 100MB }
```

This shows only processes using more than 100 megabytes of memory. `-gt` means "greater than". `100MB` is PowerShell shorthand - you can write `100MB`, `1GB`, `500KB` and PowerShell understands the units.

---

### Lab E-5: Get Help on Any Command

PowerShell has built-in help for every command.

```powershell
Get-Help Get-Process
```

This shows the description, syntax, and parameters for `Get-Process`. To see examples:

```powershell
Get-Help Get-Process -Examples
```

You can use `Get-Help` on any cmdlet. It is the single most useful command to know when learning PowerShell.

---

## Part F: Lab - Create and Run Your First Script

A script is just a text file containing PowerShell commands. The file has a `.ps1` extension.

### Step 1: Create the Script

Open Notepad (not PowerShell - just regular Notepad).

Type this exactly:

```
Write-Host "Hello from PowerShell"
Write-Host "Current user: $env:USERNAME"
Write-Host "Computer name: $env:COMPUTERNAME"
```

`Write-Host` prints text to the screen. `$env:USERNAME` and `$env:COMPUTERNAME` are environment variables - Windows stores your username and computer name in these automatically.

Save the file as `C:\script.ps1`

Important: when saving in Notepad, change "Save as type" from "Text Documents (*.txt)" to "All Files (*.*)" - otherwise Notepad adds `.txt` to the end and you get `script.ps1.txt`.

### Step 2: Try to Run It - Expect Failure

Open PowerShell and type:

```powershell
C:\script.ps1
```

Expected output:
```
File C:\script.ps1 cannot be loaded because running scripts is disabled on this system.
For more information, see about_Execution_Policies at https://go.microsoft.com/fwlink/?LinkID=135170.
    + CategoryInfo          : SecurityError: (:) [], PSSecurityException
    + FullyQualifiedErrorId : UnauthorizedAccess
```

The script was blocked. Execution policy is set to `Restricted`.

This is the defense working as intended. Now bypass it.

### Step 3: Bypass Execution Policy and Run It

```powershell
powershell -ExecutionPolicy Bypass -File C:\script.ps1
```

Expected output:
```
Hello from PowerShell
Current user: User
Computer name: DESKTOP-XXXXXXX
```

The script ran. You bypassed execution policy with a single parameter.

This is a critical lesson: **execution policy is not a security boundary.** It stopped an accidental double-click. It did not stop an intentional bypass.

### Step 4: Understand What Just Happened

The `-ExecutionPolicy Bypass` parameter tells PowerShell: "For this one run, ignore the system's execution policy and just run the script."

This does not change the system-wide policy. If you open a new PowerShell window and run `Get-ExecutionPolicy`, it still says `Restricted`. But for the duration of that one command, the policy was bypassed.

This is how attackers run malicious scripts on locked-down systems. They do not change the policy permanently (which would be noisy and require admin rights). They just pass `-ExecutionPolicy Bypass` for each command they need to run.

Document what you found:
- What did the error say when execution policy blocked the script?
- What exact command bypassed it?
- Did you need admin rights to bypass it?
- Could a regular user (not administrator) do this?

---

## Part G: Understanding the Security Stack

Before moving to the next file, it helps to see the full picture of what PowerShell security controls exist and where each one sits.

```
User types a command
        |
        v
[Execution Policy] - Is this script file allowed to run?
        |             (Bypassed easily with -ExecutionPolicy Bypass)
        v
[AppLocker] - Is powershell.exe or the script itself blocked?
        |      (The main focus of this guide)
        v
[AMSI] - Does the content of this command contain malware?
        |  (Scans decoded content, catches known-bad code)
        v
[Constrained Language Mode] - Is PowerShell in restricted mode?
        |                      (Limits what the script can do)
        v
[Windows itself] - Does the user account have permission to do this?
        |           (Normal Windows file/registry permissions)
        v
Action executes
```

Each layer is independent. Bypassing one does not bypass the others. Real attacks often need to bypass multiple layers in sequence.

For example:
1. Bypass execution policy (-ExecutionPolicy Bypass)
2. Bypass AppLocker (use a LOLBin instead of running the script directly)
3. Bypass AMSI (patch it in memory before running the payload)
4. Work around CLM (use an unmanaged code path)

The later files in this guide cover each of those steps.

---

## Summary

Here is what you learned:

| Concept | Key Point |
|---------|-----------|
| PowerShell | A command tool built on .NET that can control all of Windows |
| Cmdlets | Commands in Verb-Noun format (`Get-Process`, `Stop-Service`) |
| Pipeline `\|` | Passes output of one command into the next |
| Variables `$` | Store data for later use |
| Execution Policy | NOT a security boundary - easily bypassed |
| Script Signing | Rarely enforced in practice |
| Constrained Language Mode | Triggered by AppLocker, limits what scripts can do |
| AMSI | Scans content before execution - bypassing it is a separate skill |

---

## What to Do Before Moving On

1. You should have successfully run `C:\script.ps1` using the `-ExecutionPolicy Bypass` method
2. You should understand why execution policy is not real security
3. You should know how to use `Get-Process`, `Where-Object`, and variables
4. You should be able to read a basic PowerShell pipeline and understand what it does

If any of that is unclear, re-read the relevant section before continuing.

---

**Next: [03-applocker-how-it-works.md](./03-applocker-how-it-works.md)**
