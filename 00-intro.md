# 00 - Windows Red Team Engagements: Course Introduction

Read this entire file before touching anything else. Everything in this course builds on the ideas explained here. If you skip this, you will be running commands without understanding why, and you will be stuck the moment something does not work exactly as expected.

---

## What Is a Red Team Engagement?

A company has offices, servers, and hundreds of employees using Windows computers. They have antivirus, firewalls, and IT security staff watching for threats. They think they are secure. But they do not actually know if a real attacker could break in.

So they hire a red team. That is you.

Your job is to try to break into their systems exactly the way a real malicious hacker would. You are not doing a checklist scan with a tool. You are actually trying to get in, get deeper, steal data, and reach the most powerful admin account in their network. You have authorization to do all of this. The company signed a contract saying: go ahead, try to break us, tell us what you found.

The difference between you and a criminal is the authorization. The techniques are the same.

This course teaches you those techniques from scratch. By the end of it, you will go from having no access on a target Windows machine to owning the entire domain.

---

## What Is Post-Exploitation?

Getting initial access means you have tricked someone into running your program on their machine. Maybe they thought it was a PDF invoice. Maybe it was a fake software update. Either way, your code is now running on their computer.

That is just step one.

Post-exploitation is everything that happens after that first foothold. Think of it this way: when a piece of malware infects a computer, the infection itself takes five seconds. What the malware does after that, for days or months, is the actual attack.

Real attackers want:

- **Passwords and hashes.** If they can get the password of an IT admin, they can log in as that person from anywhere.
- **Access to other computers.** One infected machine is limited. An attacker who can jump to 50 machines inside the same company network has real power.
- **Domain Admin.** This is the God account of a Windows corporate network. Whoever holds Domain Admin can log in as any user, read any file, install anything on any machine in the company.
- **Staying hidden.** Real attackers do not smash and grab. They stay inside networks for weeks or months, quietly watching and taking what they want.

All of that happens in post-exploitation. Getting in is 10% of the work. What you do after is 90%.

Here is the full attack chain this course teaches:

```
[ You get a shell on a Windows 11 workstation ]
                    |
                    v
[ Map what you are working with - what is running, what is blocked, who are you? ]
                    |
                    v
[ Bypass Defender and AppLocker so your tools can run ]
                    |
                    v
[ Escalate from standard user to SYSTEM (the most powerful local account) ]
                    |
                    v
[ Dump credentials from memory - get NTLM hashes ]
                    |
                    v
[ Move to other machines using those hashes ]
                    |
                    v
[ Map Active Directory - find who has power over what ]
                    |
                    v
[ Attack Kerberos to get more credentials and elevated tickets ]
                    |
                    v
[ DCSync - pull all password hashes from the domain controller ]
                    |
                    v
[ You are Domain Admin. You own the network. ]
                    |
                    v
[ Plant persistence. Clean up your tracks. ]
```

Every module in this course is one step in that chain.

---

## The Environment You Are Attacking

For this course, the target environment is:

- A Windows 11 Enterprise workstation joined to an Active Directory domain
- Microsoft Defender is on with real-time protection enabled
- AppLocker is enforced with default rules

You are starting as a domain user named `CORP\vamsi` with a standard (non-admin) account and password `vamsi123`. There is also a local account called `ammulu` on the machine, but that was only used during Windows setup. Your attack persona throughout this entire course is `vamsi`. No admin rights. No special privileges.

The lab also has some deliberately configured weaknesses that you will exploit across the modules:
- A domain service account (`svc_backup`) with local admin access on WORKSTATION01 - you crack its password via Kerberoasting in module 14 and use that access for lateral movement in module 12
- A vulnerable Windows service on WORKSTATION01 running as `Network Service` with an unquoted path - you exploit this for privilege escalation in modules 07 and 11
- Domain admin credentials cached in LSASS memory on WORKSTATION01 - you dump these in module 08

You will not be disabling Defender. You will not be turning AppLocker off. If a technique fails because Defender catches it, that is the reality of the situation and the module shows you how to adapt. Real attackers cannot just turn off the antivirus. Neither can you.

---

## What Is Microsoft Defender and Why Is It a Problem?

Defender is Windows' built-in antivirus and security tool. Think of it like this: every program that runs on Windows is doing things in the background that you cannot see. Notepad is reading your `.txt` file. Chrome is downloading data from a server. A game is loading textures into memory. Defender is sitting there watching all of them at all times.

When you download a file, Defender scans it immediately. It checks the file against a massive database of known malware. If you download `mimikatz.exe` (a famous password dumping tool), Defender recognises it, deletes it, and shows you a warning. The file never even gets a chance to run.

But that is just the obvious part. The harder problem is what Defender does at runtime.

Even if your program has never been seen before and passes the initial scan, Defender watches what it does while it is running. If your program starts doing things that malware typically does, Defender kills it.

For example: a piece of malware often needs to store code in memory and then run that code. Chrome does this too (it runs JavaScript), but Chrome is a trusted application that Microsoft has seen billions of times. Your custom program is not. So Defender watches these memory operations much more aggressively on unknown programs.

This course teaches you exactly what patterns Defender watches for and how to avoid each one. Every module addresses this.

---

## What Is AppLocker and Why Is It a Problem?

AppLocker is a Windows feature that controls which programs are allowed to run at all. Think of it as a whitelist for executables.

Normally, any program can run on Windows. You download something, double-click it, it runs. AppLocker breaks this. When AppLocker is enabled, Windows checks every program before letting it execute. If the program is not on the approved list, it simply does not run. No error about missing DLLs, no crash, just a "this program is blocked by group policy" message and nothing happens.

The approved list works by path, hash, or publisher. Most companies configure it to allow:
- Anything in `C:\Windows\`
- Anything in `C:\Program Files\`
- Anything signed by Microsoft

So if you drop your malicious program in `C:\Users\vamsi\Downloads\`, it gets blocked. But if you can get it into `C:\Windows\Temp\`, it runs because that path is trusted.

There is also a critical default: **AppLocker only blocks .exe and .ps1 files by default. It ignores DLL files completely.** This means while your standalone malicious program gets blocked, a malicious DLL loaded by a trusted Microsoft program is completely invisible to AppLocker.

You will exploit both of these gaps across this course.

---

## What Is a C2 Framework?

C2 stands for Command and Control. This is how you control a compromised machine remotely after you get initial access.

Without a C2 framework, getting initial access is almost pointless. Say your program runs on the victim machine. Great. Now what? You cannot type commands into it. You cannot see what files are on the machine. You have a process running somewhere, silently, doing nothing.

A C2 framework solves this. Here is how it works:

1. You run a C2 server on your Kali machine. It listens for incoming connections.
2. Your payload on the victim machine is called an **implant** or **beacon**. After it starts running, it reaches out to your C2 server over HTTPS - the same protocol Chrome uses to load websites.
3. The C2 server receives the connection. Now you have a live session. You can type commands: list files, dump passwords, move to another machine, anything.
4. All communication is encrypted. To a network monitor, it looks like normal web traffic.

The C2 framework in this course is **Sliver**, built by Bishop Fox. It is open source and free. If you have heard of Cobalt Strike (the commercial tool that professional red teams use), Sliver is the free equivalent. Same concepts, same techniques, no $5,000 annual license.

Why not Metasploit? Because Defender knows every Metasploit payload. The moment a default Meterpreter shell starts, Defender kills it. Sliver with a custom-built loader bypasses Defender because the combination of your custom code and Sliver's encrypted traffic is something Defender has never seen before.

---

## What Is Nim and Why Are We Using It?

Nim is a programming language that compiles into a native Windows `.exe` or `.dll` file. It is not a scripting language like Python. When you compile a Nim program, you get a real Windows executable that runs at full speed without needing any runtime or interpreter installed.

Why does this matter for red teaming?

Defender has seen every version of every well-known attack tool. Mimikatz, Metasploit, Covenant payloads, all of it. Defender recognises them by their byte patterns, like a fingerprint. Even if you rename the file, the internal bytes match a known signature.

When you write a Nim program yourself, the resulting `.exe` has a completely unique structure that Defender has never seen before. There is no signature to match. Defender cannot automatically say "this is malware" because it has never seen this specific combination of code before.

On top of that, Nim can cross-compile. You write the code on Kali Linux, and the compiler produces a Windows `.exe` that runs perfectly on Windows. You never need to touch the victim machine to build your tools.

In module 02 you will write a Nim program that:
- Fetches your Sliver shellcode from your Kali server over HTTPS at runtime (nothing malicious on disk)
- Decodes it from XOR encryption in memory
- Allocates memory as Read/Write first (not Execute, which Defender watches for)
- Copies the shellcode in
- Flips the memory to Execute only after writing is done
- Installs hardware breakpoints on AMSI and ETW using CPU debug registers so those functions are intercepted without modifying a single byte of system DLL code
- Executes the shellcode by passing it as a callback to a legitimate Windows enumeration API rather than creating a thread directly

The result is a live Sliver session on the victim machine with Defender running.

---

## What Is AMSI?

AMSI stands for Antimalware Scan Interface.

Here is the problem AMSI was designed to solve: attackers figured out that if they ran malicious code through PowerShell, Defender could not see it because the script never touched disk. They would just type the attack commands directly into a PowerShell window, or have their implant run PowerShell commands in memory. Defender scans files on disk but cannot scan things that only exist in RAM.

Microsoft's answer was AMSI. It works like this: before PowerShell actually runs any command, it feeds the script content through AMSI. AMSI sends it to Defender. Defender checks it against all its signatures and behavioral rules. If it looks like malware, execution is blocked before a single line runs.

AMSI plugs into PowerShell, the .NET runtime, and several other Windows scripting engines.

If AMSI is active and you try to run a known attack command through your beacon's PowerShell, it gets caught and blocked. This is why bypassing AMSI is one of the first things your loader does.

Module 04 covers AMSI in complete depth.

---

## What Is CLM?

CLM stands for Constrained Language Mode. This is a PowerShell security restriction.

PowerShell in its normal state is extremely powerful. You can write full programs in it, load .NET code, call any Windows API, do almost anything. That power is also why attackers love it. Almost every advanced Windows attack technique involves running something through PowerShell.

When AppLocker is enforcing script rules, Windows automatically puts PowerShell into Constrained Language Mode. In CLM, most of the powerful stuff is disabled:
- You cannot load external .NET code
- You cannot call most Windows API functions directly
- You cannot use reflection (which is how most in-memory attack tools work)
- You are basically limited to basic scripting commands

If your beacon tries to run a powerful PowerShell-based attack tool in CLM, it fails. The tool needs features that CLM has locked out.

Module 06 covers how to escape CLM completely.

---

## What Is Active Directory?

Active Directory (AD) is Microsoft's system for managing everything in a corporate Windows network from one central place.

Think of it this way: a company has 500 employees. Without Active Directory, every computer would have its own separate list of usernames and passwords. If someone changes their password, IT would have to update it on every machine they use. If someone leaves the company, IT would have to go to every computer and delete their account. That is unmanageable at scale.

Active Directory solves this. There is one central server called the **domain controller** (DC). Every user account lives on the DC. Every Windows computer in the company is joined to the domain. When `vamsi` logs into any computer in the building, Windows checks with the DC: does this user exist? Is their password correct? What are they allowed to do?

The domain controller is the crown jewel of a corporate network. If you compromise it, you own the entire company. You can create accounts, reset passwords, read any file on any computer, install software on every machine.

**Domain Admin** is the highest privilege level in Active Directory. Whoever has Domain Admin access controls everything. Getting Domain Admin is the final objective of this course.

---

## The Tools Stack

Here is every tool you will use in this course and what each one does.

### On Kali (Your Attack Machine)

**Sliver C2**
Your command and control framework. Runs on Kali. The victim machine connects back to it. You issue commands through it and get back results.

**Nim compiler**
Compiles your custom Defender-evading shellcode loader from Nim source code into a Windows .exe.
Install: `sudo apt install nim`

**winim**
A Nim library that gives you access to Windows internal functions. Your loader uses this to work with Windows memory and processes at a low level.
Install: `nimble install winim`

**mingw-w64**
The cross-compiler that lets Nim produce Windows .exe files while running on Linux.
Install: `sudo apt install mingw-w64`

**Hashcat**
Offline password cracker. After you extract password hashes from the victim machine's memory, you feed them to Hashcat with a wordlist. It tries millions of password guesses per second until it finds a match.
Install: `sudo apt install hashcat`

**Impacket**
A Python toolkit for attacking Windows network protocols. You use it to run attacks like Pass-the-Hash and DCSync directly from Kali without needing to run anything on the victim.
Install: `pip3 install impacket`

**BloodHound + Neo4j**
BloodHound maps out the entire Active Directory structure and shows you the shortest path from your current user to Domain Admin. Neo4j is the graph database it uses under the hood. The data is collected on the victim by SharpHound and sent back to you.
Install: `sudo apt install bloodhound neo4j`

**evil-winrm**
A shell tool that connects to Windows machines over WinRM (Windows Remote Management). Once you have credentials for an account that has remote access, you use this to get an interactive shell without needing to go through your Sliver beacon. Particularly useful during lateral movement to log straight into the DC.
Install: `sudo gem install evil-winrm`

### On the Victim Machine (Via Sliver)

These tools never touch disk as .exe files. They run entirely in memory through your Sliver session.

**Seatbelt**
Runs a large collection of security checks on the victim machine and reports back. Tells you: what is AppLocker blocking, what privileges does your token have, what programs are installed, are there stored credentials anywhere, and much more. Your first tool to run after getting a beacon.

**PowerView**
A PowerShell toolkit for enumerating Active Directory. Lists users, groups, which accounts have admin access to which machines, who can reset whose password. Essential for understanding the AD environment before you attack it.

**SharpHound**
Collects Active Directory data and sends it to BloodHound. Walks the entire domain structure and maps relationships. Feed its output into BloodHound on Kali to see the attack paths.

**PrintSpoofer / GodPotato**
Privilege escalation tools. If your beacon is running as a service account that has a specific privilege called `SeImpersonatePrivilege`, these tools exploit that to get SYSTEM access. Used in module 07.

**Rubeus**
A Kerberos attack toolkit. Requests, forges, and manipulates Kerberos tickets (the authentication tokens Windows uses internally). Used for Kerberoasting, AS-REP Roasting, and pass-the-ticket attacks. All in memory.

---

## How Each Module Is Structured

Every module after this one follows the same format:

**Scenario:** A short paragraph explaining where you are in the engagement and what problem you are facing right now.

**Objective:** One clear sentence describing what you need to accomplish by the end of the module.

**The Concept:** A full explanation of why this technique works, what is happening under the hood, and what Defender or AppLocker is doing in response.

**The Attack:** Step-by-step commands. Every command is explained. You will not be copy-pasting things you do not understand.

**What to Do When It Fails:** Defender and AppLocker will block some of your attempts. This section explains what the detection looks like and gives you the adjusted technique.

**OPSEC Note:** What evidence this technique leaves behind. What a defender would see in logs. What you should know before doing this in a real engagement.

---

## Module List

| Number | File | Phase |
|--------|------|-------|
| 00 | `00-intro.md` | Orientation (this file) |
| 01 | `01-lab-setup.md` | Lab Setup |
| 02 | `02-initial-access-nim.md` | Foothold |
| 03 | `03-situational-awareness.md` | Recon |
| 04 | `04-amsi-bypass.md` | Evasion |
| 05 | `05-applocker-lolbins.md` | Evasion |
| 06 | `06-powershell-clm.md` | Evasion |
| 07 | `07-privesc.md` | Privilege Escalation |
| 08 | `08-credential-dumping.md` | Credential Access |
| 09 | `09-dll-hijacking.md` | Advanced Bypass |
| 10 | `10-com-abuse.md` | Advanced Bypass |
| 11 | `11-path-misconfigs.md` | Advanced Bypass |
| 12 | `12-lateral-movement.md` | Lateral Movement |
| 13 | `13-ad-enumeration.md` | Active Directory |
| 14 | `14-kerberos-attacks.md` | Active Directory |
| 15 | `15-dcsync-domain-takeover.md` | Active Directory |
| 16 | `16-persistence.md` | Persistence |
| 17 | `17-opsec-cleanup.md` | OPSEC |

---

## A Word on Legality

Everything in this course is for your authorized lab environment only. Running these techniques against systems you do not own or do not have written authorization to test is illegal in most countries, including India under the IT Act.

Build your lab, break your lab, learn in your lab.

---

Open `01-lab-setup.md` next.
