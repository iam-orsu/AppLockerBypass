# Lab Setup - VMware Pro + Kali + Windows 11

This is your entire lab environment setup. Follow each step in order. By the end you will have two virtual machines talking to each other - Kali Linux as the attacker and Windows 11 as the target.

---

## What You Need Before Starting

- **VMware Workstation Pro** installed on your computer
- At least **16 GB of RAM** (8 GB minimum but things will be slow)
- At least **80 GB of free disk space**
- The following downloads ready:

| Download | Where to Get It | Size |
|----------|----------------|------|
| Kali Linux VMware image | https://www.kali.org/get-kali/#kali-virtual-machines | ~3 GB |
| Windows 11 Enterprise ISO | https://www.microsoft.com/en-us/evalcenter/evaluate-windows-11-enterprise | ~5 GB |

Use the **Kali VMware image** (not the ISO). It is pre-configured and saves you time. For Windows 11, use the 90-day evaluation - it is free and fully functional.

---

## Part 1: Set Up Kali Linux

### Step 1: Import Kali into VMware

1. Extract the downloaded Kali `.7z` or `.zip` file - you will get a folder with `.vmx` and `.vmdk` files
2. Open VMware Workstation Pro
3. Click **File** > **Open**
4. Navigate to the extracted folder and open the `.vmx` file
5. VMware will import it - this takes 1-2 minutes

### Step 2: Configure Kali VM Settings

Before starting Kali, right-click the VM and choose **Settings**:

- **Memory:** Set to 4096 MB (4 GB) minimum
- **Processors:** Set to 2 cores
- **Network Adapter:** Set to **VMnet2** (we will configure this shared network in Part 3)

Click OK.

### Step 3: Start Kali and Log In

1. Click **Power On**
2. Default credentials:
   - Username: `kali`
   - Password: `kali`
3. Open a terminal (right-click desktop > Open Terminal)
4. Run this to update Kali:

```bash
sudo apt update && sudo apt upgrade -y
```

This takes 5-10 minutes. Let it finish.

### Step 4: Note Your Kali IP Address

In the Kali terminal, run:

```bash
ip a
```

Look for the line that shows `inet` followed by an IP address (something like `192.168.x.x`). Write this down - you will use it throughout the labs.

---

## Part 2: Set Up Windows 11

### Step 1: Create a New VM

1. In VMware, click **Create a New Virtual Machine**
2. Choose **Typical (recommended)** > Next
3. Choose **Installer disc image file (ISO)** > Browse to your Windows 11 ISO > Next
4. Select **Windows 11** from the dropdown > Next
5. Name it: `Windows11-Target`
6. Disk size: **60 GB** minimum, select **Store virtual disk as a single file** > Next
7. Click **Customize Hardware** before finishing:
   - **Memory:** 4096 MB (4 GB)
   - **Processors:** 2 cores
   - **Network Adapter:** Set to **VMnet2**
8. Click Finish

### Step 2: Install Windows 11

1. Power on the VM
2. Press any key when prompted to boot from DVD
3. Click through the installer:
   - Language: English (or your preference)
   - Click **Install Now**
   - Choose **Windows 11 Enterprise** from the list
   - Accept the license terms
   - Choose **Custom: Install Windows only**
   - Select the unallocated space > Next
4. Windows installs automatically - takes 10-20 minutes
5. The VM reboots several times - this is normal

### Step 3: Windows First-Time Setup

When Windows boots to the setup screens:

1. Choose your region > Next
2. Choose keyboard layout > Next
3. **Skip** the second keyboard layout
4. When asked to sign in with Microsoft account, click **Sign-in options** > **Domain join instead**
   - This lets you create a local account without a Microsoft account
5. Username: `User` (or anything you like)
6. Password: set something simple you will remember
7. Security questions: fill them in
8. Privacy settings: turn everything off > Accept

### Step 4: Note Your Windows IP Address

Once Windows is set up:

1. Open **Command Prompt** (search for `cmd` in the Start menu)
2. Run:

```cmd
ipconfig
```

Look for the IP address under your network adapter. Write it down.

---

## Part 3: Connect the Two VMs on the Same Network

Both VMs need to talk to each other. We use a VMware Host-Only network for this.

### Step 1: Configure VMnet2 in VMware

1. In VMware, go to **Edit** > **Virtual Network Editor**
2. Click **Add Network** > Select **VMnet2** > OK
3. Set VMnet2 to **Host-only**
4. Make sure **Use local DHCP service** is checked
5. Subnet IP: `192.168.50.0`
6. Subnet mask: `255.255.255.0`
7. Click **Apply** > OK

### Step 2: Assign Both VMs to VMnet2

For **each VM** (Kali and Windows 11):
1. Right-click the VM > Settings
2. Click **Network Adapter**
3. Change to **Custom: Specific virtual network** > Select **VMnet2**
4. Click OK

### Step 3: Verify They Can Talk

1. Get the IP of your Windows 11 VM: run `ipconfig` in Windows Command Prompt
2. Get the IP of your Kali VM: run `ip a` in Kali terminal
3. From Kali, ping Windows:

```bash
ping [windows_ip]
```

4. From Windows, ping Kali:

```cmd
ping [kali_ip]
```

If you get replies, both VMs can communicate. 

> **Note:** Windows Firewall may block pings from Kali by default. If the ping from Kali fails but the Windows ping works, that is fine. The labs will still work. We will disable the Windows Firewall when needed.

---

## Part 4: Configure Windows 11 for the Labs

A few settings to change on Windows 11 before the labs start.

### Disable Windows Firewall (for lab purposes)

1. Open **Control Panel** > **System and Security** > **Windows Defender Firewall**
2. Click **Turn Windows Defender Firewall on or off**
3. Turn off for both **Private** and **Public** networks
4. Click OK

> This makes the labs easier. In a real environment, you would not do this.

### Enable Administrator Account

AppLocker setup requires admin access. Enable the built-in Administrator:

1. Open Command Prompt **as Administrator** (right-click cmd > Run as administrator)
2. Run:

```cmd
net user Administrator /active:yes
net user Administrator Password123!
```

3. Log out and log back in as `Administrator` with password `Password123!`

> Use this account for all AppLocker configuration in later labs.

### Install Required Tools on Windows

Open **PowerShell as Administrator** and run:

```powershell
# Verify PowerShell version (should be 5.1)
$PSVersionTable.PSVersion
```

You should see `Major: 5` and `Minor: 1`. That is Windows PowerShell 5.1, which is what these labs use.

> **Note:** PowerShell 2.0 is NOT available on Windows 11. This is intentional - Microsoft removed it. Some older guides reference PowerShell 2.0 downgrade attacks - those do not work on Windows 11.

---

## Part 5: Install Metasploit Tools on Kali (Verify)

Metasploit comes pre-installed on Kali. Just verify it works:

```bash
msfconsole --version
```

You should see something like `Framework Version: 6.x.x`.

Also verify msfvenom:

```bash
msfvenom --version
```

If either command fails, run: `sudo apt install metasploit-framework -y`

---

## Your Lab Is Ready

Here is what you now have:

| VM | Role | OS |
|----|------|----|
| Windows 11 Enterprise | Target (victim machine) | Windows 11 |
| Kali Linux | Attacker machine | Kali Linux |

Both machines are on the same private network and can communicate with each other.

### Quick Reference - Your IPs

Write these down now:

```
Kali IP:    _________________
Windows IP: _________________
```

You will use these in every lab.

---

## Snapshot Both VMs Now

Before doing anything else, take a snapshot of both VMs. This lets you reset to a clean state if something breaks.

In VMware:
1. Right-click the VM
2. Snapshot > Take Snapshot
3. Name it: `Clean Install`
4. Click OK

Do this for both Kali and Windows 11.

---

**Next: [02-powershell-complete-intro.md](./02-powershell-complete-intro.md)**
