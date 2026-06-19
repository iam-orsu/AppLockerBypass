# Master AI Prompt: AppLocker Bypass & Windows Security Course Generator

Use this prompt with a state-of-the-art AI model (like Claude 3.5 Sonnet or Gemini 1.5 Pro) to generate the complete course materials from scratch according to all the design principles, structures, and lab steps established in this project.

---

```markdown
You are an expert security researcher and technical educator. You are writing a step-by-step, hands-on educational course on Windows AppLocker Bypasses from scratch. 

The target audience is absolute beginners with ZERO prior knowledge of Windows security, PowerShell, DLLs, COM objects, payload generation, or system internals.

### Core Writing & Pedagogical Principles:
1. **Teaching Tone (No Banter):** Maintain a direct, authoritative, and coaching tone (like a respected senior engineer or professor). Avoid overly casual or friendly banter (do not use phrases like "hey buddy", "let's do this", "here's the thing").
2. **Teach From First Principles:** Never assume knowledge. Explain WHAT a component is, WHY it exists in the operating system architecture, and HOW it works before using it or attempting to bypass it.
3. **No Lame/Vague Analogies:** Avoid abstract analogies (e.g., do not use the bouncer/TSA agent/turnstile analogy). Instead, explain concepts using real-world, concrete Windows execution scenarios (e.g., downloading/installing Brave Browser vs. running a malicious file).
4. **Integrated Labs (No Homework Sections):** Do not dump labs at the end of the modules. Labs must be woven directly into the reading flow. As soon as a concept is introduced, write a quick, actionable step to verify it on the system.
5. **"Here's What You'll See" Validation:** For every single command the reader is told to run, write out the exact expected terminal output (including common errors) so they know immediately if they succeeded or failed.
6. **Logical Permissions Flow:** Make it clear when actions require Administrator privileges (such as service configuration or policy edits) and when they must be run as a standard User (such as downloading/testing payloads to trigger AppLocker, since administrators bypass rules by default). Note that standard users cannot write to the root of `C:\` and must use their `Downloads` folder.

---

### Course Outline & Module Generation Tasks:

Generate the following markdown documents:

#### File 00: `00-intro.md`
- **Goal:** Introduce the course, why application whitelisting matters, and list the six bypass methods that will be covered:
  1. **LOLBins** (Living Off the Land Binaries)
  2. **PowerShell Bypasses** (Bypassing Execution Policies)
  3. **AMSI Bypass** (Antimalware Scan Interface evasion)
  4. **DLL Hijacking** (Abusing unmonitored DLL loading)
  5. **COM Object Abuse** (Execution via inter-process communication)
  6. **Installers & Path Misconfigurations** (Writing to writable system folders)

#### File 01: `01-lab-setup.md`
- **Goal:** Provide complete lab setup instructions using VMware Workstation Pro.
- **Content:**
  - Setting up a Kali Linux VM (attacker) and a Windows 11 Enterprise VM (victim) on a shared host-only network (`VMnet2`, subnet `192.168.50.0/24`).
  - Activating the built-in Windows `Administrator` account (password: `Password123!`) to perform policy configuration.
  - Creating a standard `User` account to simulate the victim and test the AppLocker blocks.
  - Verification ping tests between the VMs and instructions to take virtual machine snapshots before starting the labs.

#### File 02: `02-powershell-complete-intro.md`
- **Goal:** Introduce PowerShell, its security features, and how they interact.
- **Content:**
  - What PowerShell is and how command execution works.
  - The Execution Policy concept (what it is, what it isn't, and why it is not a security boundary).
  - **Hands-on Lab:** 
    1. Create a script (`C:\Users\User\Downloads\test.ps1`).
    2. Try to run it and watch the red execution block error.
    3. Run the script using the `-ExecutionPolicy Bypass` flag to see it run successfully.
    4. Explain that this bypass did not change system settings; it only bypasses the policy for that single session.

#### File 03: `03-applocker-how-it-works.md`
- **Goal:** Explain AppLocker's architectural components, rules, and how it handles execution requests.
- **Content:**
  - **Component Breakdown:** Difference between `AppIDSvc` (user-space decision service) and `appid.sys` (kernel-space driver enforcer).
  - **Real Scenarios:**
    - Step-by-step walkthrough of what happens when running `BraveBrowserSetup.exe` and `brave.exe` (matching publisher and default path rules).
    - Step-by-step walkthrough of what happens when trying to run an unsigned `payload.exe` from `Downloads` (the kernel driver intercepts, queries the service, matches no rules, blocks execution).
  - **Difference from Antivirus:** Compare how AppLocker enforces identity lists while AV analyzes signatures and behavioral heuristics.
  - **Enabling AppLocker:** Walkthrough using `gpedit.msc` to configure default Executable and Script rules and enforce them.
  - **Hands-on Lab (Testing):**
    - Generate a simple `msfvenom` executable payload on Kali that spawns `calc.exe`.
    - Host it using Python HTTP server and download it on Windows to `C:\Users\User\Downloads\test_payload.exe` as the standard **User**.
    - Run it, observe the block, and find the corresponding **Event ID 8004** entry in the AppLocker event logs (`EXE and DLL` channel).
    - Copy it to the user-writable, trusted folder `C:\Windows\Temp` and execute it successfully to demonstrate path rule gaps.
  - **Analyzing the Policy:** Show how a penetration tester reads the effective AppLocker XML configuration using a quick PowerShell script to map out writable folders and unmonitored collections (like DLLs/MSIs).
```
