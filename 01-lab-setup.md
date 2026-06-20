# 01 - Lab Setup: Build Your Range

## What You Are Building

You need three virtual machines running on your physical computer using VMware Pro. Each machine has a specific role:

| Machine | Role | Why You Need It |
|---------|------|----------------|
| Kali Linux | Attacker machine | Runs Sliver C2, compiles Nim payloads, cracks hashes, runs all your attack tools |
| Windows 11 Enterprise | Victim machine | The machine you are attacking. AppLocker enforced, Defender on, domain-joined |
| Windows Server 2022 | Domain Controller | Runs Active Directory. The final target. Getting Domain Admin here means you win. |

---

## Network Design: Why NAT?

In VMware Pro, virtual machines can use different network modes. You are using **NAT** for this course.

**What NAT does:**
NAT (Network Address Translation) means VMware creates a private virtual network for your VMs. All VMs on that network can talk to each other. They also share your physical computer's internet connection, so they can reach the internet. Your home or office network cannot directly reach the VMs.

**Why not Host-Only?**
Host-Only cuts off internet access entirely. That sounds more secure for a lab, but it is a problem in practice:
- You cannot run `apt install` to set up Kali tools
- You cannot install Sliver from its download URL
- You cannot install Nim libraries
- You cannot download Windows evaluation ISOs or updates

NAT lets you keep internet access while still having the VMs isolated from your real network devices.

**The VMware NAT network is VMnet8.** All three VMs will be connected to VMnet8. They can reach each other and the internet through your host machine.

**IP addresses you will use:**

```
192.168.10.10    Kali Linux (attacker)
192.168.10.20    Windows 11 Enterprise (victim)
192.168.10.30    Windows Server 2022 (domain controller)

Subnet:  192.168.10.0/24
Gateway: 192.168.10.2   (VMware NAT gateway, automatically provided by VMware)
Domain:  corp.local
```

---

## Configure VMware's NAT Subnet

By default VMware picks a random subnet for VMnet8. You need to set it to `192.168.10.0/24` so all your IP addresses match this guide.

1. Open VMware Pro
2. Go to **Edit** in the top menu -> **Virtual Network Editor**
3. Click **Change Settings** (bottom right, requires admin rights)
4. Find **VMnet8** in the list and click it
5. Make sure **NAT** is selected as the type
6. Look at the **Subnet IP** field. Change it to `192.168.10.0`
7. Change **Subnet mask** to `255.255.255.0`
8. Click **Apply**, then **OK**

VMware will restart the VMnet8 adapter. Now any VM connected to VMnet8 gets an IP in the `192.168.10.x` range.

---

## User Accounts in This Course

Get this clear before you start, because these accounts show up everywhere:

| Account | Where It Exists | Password | What It Is |
|---------|----------------|----------|-----------|
| `ammulu` | Windows 11 local only | `Ammulu@123` | Local account created during Win11 install. Not a domain account. |
| `CORP\vamsi` | Active Directory (domain) | `vamsi123` | Your attack persona. Standard domain user. No admin rights. |
| `CORP\svc_backup` | Active Directory (domain) | `Backup@2024!` | Service account. Kerberoastable. You attack this in module 14. |
| `CORP\Administrator` | Active Directory (domain) | `P@ssw0rd123!` | Domain Admin. Your goal to reach. |
| `WORKSTATION01\Administrator` | Windows 11 local only | `LocalAdmin@123!` | Local admin for configuration tasks only. |

**The local `ammulu` account is only used during Windows 11 setup.** After you join Win11 to the domain, you log in as `CORP\vamsi` for all attack modules. `vamsi` is a regular domain user with no admin rights anywhere. That is your starting point for every attack.

---

## Part 1: Kali Linux Setup

### 1.1 Download Kali Linux

Go to `https://www.kali.org/get-kali/#kali-virtual-machines` and download the **VMware** image. It comes as a `.7z` compressed archive. Extract it with 7-Zip (`https://www.7-zip.org/`).

Inside the extracted folder you will find a `.vmx` file. That is the VMware configuration for the Kali VM.

### 1.2 Open Kali in VMware Pro

Open VMware Pro. Go to **File -> Open** and select the `.vmx` file. When VMware asks if you moved or copied the VM, click **I copied it**.

The Kali VM appears in your library on the left.

### 1.3 Configure Kali VM Hardware

Right-click the Kali VM and select **Settings**:
- **Memory:** 4096 MB (4 GB)
- **Processors:** 2 cores
- **Network Adapter:** Change to **NAT**

Click OK.

### 1.4 Power On and Log In

Click the Play button. Default credentials:
```
Username: kali
Password: kali
```

Open a terminal (find it in the taskbar or right-click desktop -> Open Terminal Here).

### 1.5 Change the Default Password

```bash
passwd
```

Type a new password twice. Do not leave it as `kali`.

### 1.6 Set a Static IP

By default Kali gets a random IP from VMware's DHCP. You need it fixed at `192.168.10.10` so your victim machine always knows where to call back.

Run this to open the text-based network manager:

```bash
sudo nmtui
```

- Select **Edit a connection**
- Select your network adapter (probably `eth0` or `ens33`, not `lo`)
- Press Enter to edit

You will see the Edit Connection screen. It starts collapsed and looks like this:

```
Profile name   Wired connection 1
Device         eth0 (00:0C:29:xx:xx:xx)

ETHERNET                                   <Show>
802.1X SECURITY                            <Show>

IPv4 CONFIGURATION  <Manual>              <Show>
IPv6 CONFIGURATION  <Automatic>           <Show>

[X] Automatically connect
[X] Available to all users
```

**Step 1: Make sure IPv4 CONFIGURATION says `<Manual>`.**
Arrow over to where it shows `<Automatic>` or `<DHCP>` next to IPv4 CONFIGURATION and press Enter to cycle through until it shows `<Manual>`.

**Step 2: Expand the IPv4 section.**
Arrow to the right side where it says `<Show>` next to IPv4 CONFIGURATION and press Enter. The section expands and now looks like this:

```
IPv4 CONFIGURATION  <Manual>              <Hide>
        Addresses   <Add ... >
          Gateway   ________________________
      DNS servers   <Add ... >
   Search domains   <Add ... >
```

**Step 3: Add your IP address.**
Arrow down to **Addresses** and press Enter on `<Add ... >`. A text field appears. Type:

```
192.168.10.10/24
```

The `/24` at the end sets the subnet mask to `255.255.255.0`. Press Enter to confirm.

**Step 4: Set the gateway.**
Arrow down to the **Gateway** field (the blank underlined area next to it). Type:

```
192.168.10.2
```

This is the VMware NAT gateway. It gives your Kali VM internet access through your host machine.

**Step 5: Add DNS.**
Arrow down to **DNS servers** and press Enter on `<Add ... >`. Type:

```
8.8.8.8
```

This is Google's DNS. It allows Kali to resolve domain names for internet access.

**Step 6: Save and exit.**
- Tab down to **OK** and press Enter to save
- Select **Back** to return to the connection list
- Select **Quit** to exit nmtui, then **Quit**

Restart the network connection to apply:

```bash
sudo nmcli connection reload
sudo nmcli connection up "$(nmcli -t -f NAME connection show | head -1)"
```

Or simply reboot:

```bash
sudo reboot
```

After reboot, verify:

```bash
ip a
ping -c 2 8.8.8.8
```

You should see `192.168.10.10` on your adapter and pings to `8.8.8.8` should succeed (internet works).

### 1.7 Update Kali and Install Tools

```bash
sudo apt update && sudo apt upgrade -y
```

This might take a while. Then install everything you need:

```bash
sudo apt install -y \
    nim \
    mingw-w64 \
    hashcat \
    neo4j \
    bloodhound \
    git \
    curl \
    wget \
    python3-pip \
    ncat \
    smbclient \
    crackmapexec \
    golang-go

pip3 install impacket

# evil-winrm: WinRM shell for lateral movement (module 12)
sudo gem install evil-winrm
```

What each tool does:

| Tool | Purpose in This Course |
|------|------------------------|
| `nim` | Compiles your custom Defender-evading shellcode loader |
| `mingw-w64` | Lets Nim cross-compile Windows .exe files on Linux |
| `hashcat` | Cracks NTLM password hashes offline using a wordlist |
| `neo4j` | Graph database backend for BloodHound |
| `bloodhound` | Maps Active Directory and shows paths to Domain Admin |
| `git` | Clones tools from GitHub |
| `curl` | HTTP requests, used in scripts to fetch staged payloads |
| `python3-pip` | Installs Python packages (impacket) |
| `ncat` | Netcat for testing connections |
| `smbclient` | Browse Windows file shares from Kali |
| `crackmapexec` | SMB/WinRM attacks, Pass-the-Hash, AD enumeration |
| `golang-go` | Go language, some tools need this to compile |
| `impacket` | Python AD attack toolkit: DCSync, Kerberos, secretsdump |
| `evil-winrm` | WinRM-based interactive shell for lateral movement (module 12) |

### 1.8 Install winim for Nim

The `winim` library gives Nim access to Windows API functions. Your shellcode loader in module 02 needs it.

```bash
nimble install winim
```

If `nimble` is not found, run `sudo apt install nim` again. `nimble` is the Nim package manager and comes with Nim.

### 1.9 Install Sliver C2

```bash
curl https://sliver.sh/install | sudo bash
```

This downloads and installs the Sliver server binary. It also sets up a systemd daemon to run the server in the background. After it completes, connect to the Sliver console:

```bash
sliver
```

You will see the Sliver ASCII art banner and then a `sliver >` prompt. This is the Sliver interactive console. Every time you start a new module, you will start Sliver like this.

**Leave this terminal running with the Sliver console.** Open a second terminal for the rest of your Kali work.

To test Sliver is working, type in the Sliver console:

```
sliver > help
```

You should see a list of commands. If you see that, Sliver is installed correctly.

---

## Part 2: Windows Server 2022 (Domain Controller)

### 2.1 Download Windows Server 2022

Go to: `https://www.microsoft.com/en-us/evalcenter/evaluate-windows-server-2022`

Click **Download the ISO**. Select **64-bit**. Fill out the form (use any info, Microsoft does not verify it). Download the ISO. It is around 5 GB.

### 2.2 Create the VM in VMware Pro

Open VMware Pro. **File -> New Virtual Machine**.

- Select **Typical** and click Next
- Select **Installer disc image file (iso)** and browse to the Server 2022 ISO
- Windows version: **Windows Server 2022 Standard**
- Leave product key blank (evaluation does not need one)
- Full name: anything
- Password: `P@ssw0rd123!` (this becomes the local Administrator password)
- VM name: `DC01`
- Disk size: **80 GB**, store as single file
- Click Finish

Before powering on, right-click `DC01` -> **Settings**:
- Memory: 2048 MB
- Processors: 2
- Network Adapter: **NAT**

### 2.3 Install Windows Server 2022

Power on `DC01`. Go through the Windows setup:

1. Select language, time, keyboard. Click **Next**.
2. Click **Install now**.
3. Select **Windows Server 2022 Standard Evaluation (Desktop Experience)** - the Desktop Experience gives you a graphical interface. Without it you only have a command line, which is harder for setup.
4. Accept the license.
5. Select **Custom: Install Windows only**.
6. Select the unallocated space and click **Next**.

Windows installs and reboots a few times. When setup finishes it asks you to set the Administrator password. Use `P@ssw0rd123!`.

Log in as `Administrator` with `P@ssw0rd123!`.

### 2.4 Set a Static IP on the DC

Open PowerShell as Administrator (right-click Start -> Windows PowerShell (Admin)).

First check your adapter name:

```powershell
Get-NetAdapter
```

Look for the adapter with Status `Up`. It is usually `Ethernet0`.

Set the IP:

```powershell
# Remove any existing IP on this adapter first
Remove-NetIPAddress -InterfaceAlias "Ethernet0" -Confirm:$false -ErrorAction SilentlyContinue
Remove-NetRoute -InterfaceAlias "Ethernet0" -Confirm:$false -ErrorAction SilentlyContinue

# Set the static IP
New-NetIPAddress `
    -InterfaceAlias "Ethernet0" `
    -IPAddress 192.168.10.30 `
    -PrefixLength 24 `
    -DefaultGateway 192.168.10.2

# Point DNS at itself - explained below
Set-DnsClientServerAddress `
    -InterfaceAlias "Ethernet0" `
    -ServerAddresses 127.0.0.1
```

**Why does the DC point DNS at itself (`127.0.0.1`)?**

After you promote this machine to a domain controller, it will run a DNS server for the `corp.local` domain. Active Directory requires its own DNS zone to work. `127.0.0.1` means "this machine itself". When the DC needs to resolve `corp.local` names, it asks its own DNS service. When it needs to resolve internet names, the DNS service forwards the query outward using the DNS forwarder you will configure next.

Verify:

```powershell
ipconfig /all
```

You should see `192.168.10.30` and subnet mask `255.255.255.0`.

Test internet access:

```powershell
ping 8.8.8.8
```

This should work because the VM is on NAT.

### 2.5 Rename the Computer

```powershell
Rename-Computer -NewName "DC01" -Restart
```

Log back in as `Administrator` after reboot.

### 2.6 Install Active Directory Domain Services

Active Directory is a Windows Server role. Install it:

```powershell
Install-WindowsFeature AD-Domain-Services -IncludeManagementTools
```

`-IncludeManagementTools` adds the GUI tools for managing AD (Active Directory Users and Computers, etc.). Takes a few minutes.

### 2.7 Promote to Domain Controller

This command creates the `corp.local` domain and makes this server the first (and only) domain controller:

```powershell
Import-Module ADDSDeployment

Install-ADDSForest `
    -DomainName "corp.local" `
    -DomainNetbiosName "CORP" `
    -SafeModeAdministratorPassword (ConvertTo-SecureString "P@ssw0rd123!" -AsPlainText -Force) `
    -InstallDns `
    -Force
```

**What each parameter does:**

- `-DomainName "corp.local"` - The full DNS name of your domain. Other machines will join `corp.local`.
- `-DomainNetbiosName "CORP"` - The short legacy name. Used in `CORP\username` style authentication.
- `-SafeModeAdministratorPassword` - Password for Directory Services Restore Mode. A recovery mode for the DC if AD gets corrupted. Set it to the same as your admin password for simplicity.
- `-InstallDns` - Also configure the DNS server role. Active Directory will not work without DNS.
- `-Force` - Do not ask for confirmation prompts.

The machine reboots automatically. After reboot, log in as `CORP\Administrator` with `P@ssw0rd123!`. Notice the login prompt now shows the domain name.

### 2.8 Configure DNS Forwarder

Your DC runs DNS for `corp.local`. But when someone queries an internet name (like `google.com`), the DC needs to forward that to an external DNS server. Configure this:

```powershell
Add-DnsServerForwarder -IPAddress 8.8.8.8
```

This tells the DNS server: if you cannot resolve a name from your local zone, forward the query to Google's DNS at `8.8.8.8`.

### 2.9 Set Domain Password Complexity Policy

By default, Windows domain password policy requires:
- At least 7 characters
- Cannot contain the username
- Must have 3 of these 4: uppercase, lowercase, number, symbol

The password `mywish` fails this because it has no uppercase, no number, and no symbol. Your domain user `vamsi` needs a password that passes this policy.

You can either keep the default policy (and use a complex password for `vamsi`) or relax the policy for the lab. For a lab, relaxing it is fine:

```powershell
# Relax minimum password length and complexity for the lab
Set-ADDefaultDomainPasswordPolicy `
    -Identity "corp.local" `
    -MinPasswordLength 1 `
    -ComplexityEnabled $false `
    -PasswordHistoryCount 0 `
    -MaxPasswordAge 0
```

This disables complexity requirements. In a real corporate domain, you would never do this. In your lab, it makes life easier so you can use simple passwords.

### 2.10 Create Domain Users

Now create the accounts you need:

```powershell
# Your main attack persona - standard domain user, no admin rights
# This is who you ARE in every attack module
New-ADUser `
    -Name "vamsi" `
    -SamAccountName "vamsi" `
    -UserPrincipalName "vamsi@corp.local" `
    -AccountPassword (ConvertTo-SecureString "vamsi123" -AsPlainText -Force) `
    -Enabled $true `
    -PasswordNeverExpires $true `
    -Description "Standard domain user - red team attack account"

# Service account that you will Kerberoast in module 14
New-ADUser `
    -Name "svc_backup" `
    -SamAccountName "svc_backup" `
    -UserPrincipalName "svc_backup@corp.local" `
    -AccountPassword (ConvertTo-SecureString "Backup@2024!" -AsPlainText -Force) `
    -Enabled $true `
    -PasswordNeverExpires $true `
    -Description "Backup service account"

# Register a Service Principal Name (SPN) on the service account
# An SPN makes an account Kerberoastable - explained in full in module 14
Set-ADUser svc_backup -ServicePrincipalNames @{Add="HTTP/backup.corp.local"}
```

Verify the users were created:

```powershell
Get-ADUser -Filter * | Select-Object Name, SamAccountName, Enabled
```

You should see at least: `Administrator`, `Guest`, `krbtgt`, `vamsi`, `svc_backup`.

### 2.11 Enable WinRM on the Domain Controller

WinRM (Windows Remote Management) is what lets tools like `evil-winrm` and CrackMapExec connect to machines remotely and run commands. By default it is not enabled on Windows Server. Module 12 (lateral movement) requires it on the DC.

Run this on DC01 as `CORP\Administrator`:

```powershell
# Enable WinRM and configure it to accept remote connections
Enable-PSRemoting -Force

# Allow WinRM through the firewall from all sources (lab only - in production you would restrict this)
netsh advfirewall firewall add rule `
    name="WinRM-HTTP" `
    dir=in `
    action=allow `
    protocol=TCP `
    localport=5985

# Verify it is listening
Get-Service WinRM | Select-Object Status, StartType
```

You should see `Status: Running`. WinRM listens on port 5985 (HTTP) and 5986 (HTTPS). For the lab, port 5985 is enough.

Test from Kali after setup:

```bash
evil-winrm -i 192.168.10.30 -u Administrator -p 'P@ssw0rd123!'
```

You should get a WinRM shell on the DC. Type `exit` to leave. If this works, WinRM is configured correctly.

---

## Part 3: Windows 11 Enterprise (Victim Machine)

### 3.1 Download Windows 11 Enterprise

Go to: `https://www.microsoft.com/en-us/evalcenter/evaluate-windows-11-enterprise`

Click **Download the ISO**. Select **64-bit**. Fill the form. Download. It is around 5 GB.

### 3.2 Create the VM in VMware Pro

**File -> New Virtual Machine**.

- Select **Typical** and click Next
- Select **Installer disc image file (iso)** and select the Windows 11 ISO
- Windows version: **Windows 11 Enterprise**
- Full name: `ammulu`
- Username: `ammulu`
- Password: `Ammulu@123`
- VM name: `WIN11-TARGET`
- Disk size: **80 GB**, store as single file
- Click Finish

Before powering on, right-click `WIN11-TARGET` -> **Settings**:
- Memory: 4096 MB (4 GB)
- Processors: 2
- Network Adapter: **NAT**

**One extra setting for Windows 11:** Windows 11 requires TPM 2.0 to install. VMware Pro can emulate this. In VM Settings, go to **Options** tab -> **Advanced** -> check **Enable VBS** if available. If Windows 11 refuses to install, go to the VM Settings -> **Add** -> **Trusted Platform Module**. Add it and try again.

### 3.3 Install Windows 11

Power on the VM. Go through Windows 11 setup.

When you reach the **Sign in with Microsoft** screen, click **Sign-in options** at the bottom left, then click **Domain join instead**. This lets you create a local account without requiring a Microsoft account.

Create the local account:
- Username: `ammulu`
- Password: `Ammulu@123`
- Security questions: set any three answers you will remember

Go through the rest of setup. Turn off all the optional advertising and telemetry options. They are not needed.

**This `ammulu` account is a local Windows account.** It is not in Active Directory. It is just the local user created during Windows setup. You will not use this account for attacks. You will use the domain account `CORP\vamsi` after joining the domain.

### 3.4 Set a Static IP

Log out of `ammulu`. On the login screen, there is no way to log in as `Administrator` yet because VMware may not have created one. Let us log back in as `ammulu` and elevate.

Log in as `ammulu` with `Ammulu@123`.

Right-click Start -> **Windows PowerShell (Admin)**. It will ask for consent since `ammulu` is a local user with admin rights during setup (Windows gives the first user admin rights). Click **Yes**.

Check the adapter name:

```powershell
Get-NetAdapter
```

Set the IP:

```powershell
Remove-NetIPAddress -InterfaceAlias "Ethernet0" -Confirm:$false -ErrorAction SilentlyContinue
Remove-NetRoute -InterfaceAlias "Ethernet0" -Confirm:$false -ErrorAction SilentlyContinue

New-NetIPAddress `
    -InterfaceAlias "Ethernet0" `
    -IPAddress 192.168.10.20 `
    -PrefixLength 24 `
    -DefaultGateway 192.168.10.2

# Point DNS at the DC so Windows can find the domain to join
Set-DnsClientServerAddress `
    -InterfaceAlias "Ethernet0" `
    -ServerAddresses 192.168.10.30
```

**Why does Win11 point DNS at the DC (`192.168.10.30`)?**

When you join this machine to `corp.local`, Windows needs to find the domain controller. It finds the DC by resolving `corp.local` in DNS. The DC is the only machine running DNS for `corp.local`. So Win11 must use the DC as its DNS server. If you point DNS at `8.8.8.8` instead, `corp.local` will not resolve, and domain join will fail.

Test DNS is working:

```powershell
Resolve-DnsName corp.local
```

You should see the DC's IP `192.168.10.30` returned. If you get an error, make sure the DC VM is powered on and running.

Test internet still works (through the DC's DNS forwarder):

```powershell
Resolve-DnsName google.com
```

This should also work because the DC forwards unknown names to `8.8.8.8`.

### 3.5 Rename the Computer

```powershell
Rename-Computer -NewName "WORKSTATION01" -Restart
```

After reboot, log back in as `ammulu`.

### 3.6 Join the Domain

Open PowerShell as Admin again:

```powershell
Add-Computer `
    -DomainName "corp.local" `
    -Credential (Get-Credential) `
    -Restart
```

A login dialog appears. Enter:
- Username: `CORP\Administrator`
- Password: `P@ssw0rd123!`

Windows joins the domain and reboots.

After reboot, at the login screen you will see `ammulu` as the default user. Click **Other user** in the bottom left. Now log in as:
- Username: `vamsi` (or `CORP\vamsi` to be explicit)
- Password: `vamsi123`

You are now logged in as the domain user `vamsi` on a domain-joined Windows 11 machine. This is your starting point for all attack modules.

### 3.7 Enable the Local Administrator Account

The local Administrator is disabled by default. You need it active for some setup steps. Log out of `vamsi` and log back in as `ammulu` (local account).

Open PowerShell as Admin:

```powershell
net user Administrator "LocalAdmin@123!" /active:yes
```

This enables the local Administrator account with password `LocalAdmin@123!`.

### 3.8 Verify vamsi Has No Admin Rights

Log out and log back in as `CORP\vamsi`.

Open PowerShell (not as admin). Run:

```powershell
whoami /groups
```

Look through the groups listed. You should NOT see:
- `BUILTIN\Administrators`
- `CORP\Domain Admins`
- `CORP\Enterprise Admins`

If you do not see those, `vamsi` is correctly a standard user. This is your attack starting point.

Try opening PowerShell as admin:

```powershell
# Right-click Start -> Windows PowerShell (Admin)
```

Windows will ask for an administrator username and password. `vamsi` cannot approve this because they are not an admin. This is correct. In real engagements, your initial access is almost always a standard user.

### 3.9 Configure AppLocker

Log out of `vamsi`. Log in as the local `Administrator` (`WORKSTATION01\Administrator` with `LocalAdmin@123!`).

#### Why AppLocker Matters

AppLocker controls which programs can run. Default rules allow:
- Anything in `C:\Windows\` to run
- Anything in `C:\Program Files\` to run
- Administrators can run anything

This means `vamsi` cannot run a random `.exe` or `.ps1` file they download. But there are gaps:
1. Some folders inside `C:\Windows\` that users can write to (module 11)
2. Trusted Microsoft binaries in `C:\Windows\` that can execute code indirectly (modules 05, 10)
3. DLL loading is completely unrestricted by default (module 09)

You will exploit all three gaps across the course.

AppLocker does nothing without this service running. On Windows 10/11, the Service Control Manager protects the Application Identity service (`AppIDSvc`) configuration and will return an "Access is denied" error if you try to change its startup type using `Set-Service` or `sc.exe`.

To configure it to start automatically, you must update its registry key directly, and then start the service:

```powershell
# Set startup type to Automatic (2) in the Registry
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\AppIDSvc" -Name "Start" -Value 2

# Start the service
Start-Service -Name AppIDSvc
```

Verify:

```powershell
Get-Service AppIDSvc
```

Status must be `Running`.

#### Create AppLocker Rules

Open Local Group Policy Editor from your elevated PowerShell window (so it opens with write permissions instead of read-only mode):

```powershell
gpedit.msc
```

Navigate in the left panel:

```
Computer Configuration
  -> Windows Settings
    -> Security Settings
      -> Application Control Policies
        -> AppLocker
```

You see five categories under AppLocker in the left pane. 

First, create the default rules for the four categories:
1. Right-click **Executable Rules** -> click **Create Default Rules**
2. Right-click **Windows Installer Rules** -> click **Create Default Rules**
3. Right-click **Script Rules** -> click **Create Default Rules**
4. Right-click **Packaged app Rules** -> click **Create Default Rules**

Once you have created the default rules for all four categories, you need to enable rule enforcement:
1. Right-click the parent **AppLocker** folder in the left pane (the one with the lock icon, right above Executable Rules) and select **Properties**.
2. In the **AppLocker Properties** dialog, check the **Configured** checkbox next to these four items, and ensure the dropdown next to each is set to **Enforce rules**:
   - **Executable rules**
   - **Windows Installer rules**
   - **Script rules**
   - **Packaged app rules**
3. **Leave DLL rules completely unchecked.** Do not select or configure DLL rules. (This is the security gap you will exploit in module 09).
4. Click **Apply**, then click **OK**.

Apply the policy immediately:

```powershell
gpupdate /force
```

#### Test AppLocker Is Working

Log out of the local Administrator. Log back in as `CORP\vamsi`.

Open PowerShell (normal, not admin). Try running something from Downloads:

```powershell
"Write-Host 'test'" | Out-File "$env:USERPROFILE\Downloads\test.ps1"
powershell.exe -File "$env:USERPROFILE\Downloads\test.ps1"
```

You should get an error like:

```
File C:\Users\vamsi\Downloads\test.ps1 cannot be loaded because running scripts
is disabled on this system.
```

Or the file gets blocked with a policy error. Either way, AppLocker is working.

Try an exe too:

```powershell
# Copy cmd.exe to Downloads and try to run it from there
Copy-Item C:\Windows\System32\cmd.exe "$env:USERPROFILE\Downloads\test.exe"
& "$env:USERPROFILE\Downloads\test.exe"
```

You should see:

```
This program is blocked by group policy.
```

AppLocker is enforced.

### 3.10 Verify Defender Is Active

Still logged in as `CORP\vamsi`:

```powershell
Get-MpComputerStatus | Select-Object `
    AMServiceEnabled, `
    AntispywareEnabled, `
    AntivirusEnabled, `
    RealTimeProtectionEnabled, `
    IsTamperProtected
```

All five should be `True`. If any are `False`, log in as Administrator and re-enable them via Windows Security settings (Start -> Windows Security -> Virus and threat protection).

**Do not disable Defender.** Do not exclude any folders. If you do, you break the entire point of the course.

### 3.11 Add svc_backup as Local Admin on WORKSTATION01

After Kerberoasting in module 14, you crack `svc_backup`'s password. To make that useful in the lab, `svc_backup` needs local admin access on WORKSTATION01. This is realistic: service accounts used for backups often have local admin on workstations so the backup software can read all files.

Still logged in as local `Administrator` (`WORKSTATION01\Administrator`):

```powershell
# Add the service account to local Administrators
net localgroup Administrators "CORP\svc_backup" /add

# Verify it was added
net localgroup Administrators
```

You should see `CORP\svc_backup` in the list alongside `CORP\Domain Admins` and `WORKSTATION01\Administrator`.

### 3.12 Create a Vulnerable Service for Modules 07 and 11

Two modules require a deliberately misconfigured service on the victim machine:

- **Module 07 (Privilege Escalation):** You will exploit this service's run-as account (`Network Service`) which has a Windows privilege called `SeImpersonatePrivilege`. With that privilege, PrintSpoofer and GodPotato can impersonate SYSTEM.
- **Module 11 (Path Misconfigurations):** This service has an unquoted binary path with a space in it. Windows resolves it in a way that lets a standard user plant a malicious binary that runs as the service account.

Still logged in as local `Administrator` on WORKSTATION01:

```powershell
# Create the directory structure
# The space in 'Vuln Service' is intentional - this is what creates the vulnerability
New-Item -ItemType Directory -Path "C:\CustomApp\Vuln Service\bin" -Force

# Copy cmd.exe as a placeholder binary so the service has something to point to
Copy-Item "C:\Windows\System32\cmd.exe" `
    -Destination "C:\CustomApp\Vuln Service\bin\svc.exe"

# Grant full access to C:\CustomApp\ for all users
# This is what lets vamsi (a standard user) write a malicious binary there
icacls "C:\CustomApp" /grant "Everyone:(OI)(CI)F" /T

# Create the vulnerable service:
# - binpath has a SPACE and NO QUOTES around the path
# - obj sets it to run as 'Network Service' (has SeImpersonatePrivilege)
# - start= auto so it starts on boot
sc.exe create VulnSvc `
    binpath= "C:\CustomApp\Vuln Service\bin\svc.exe" `
    start= auto `
    obj= "NT AUTHORITY\Network Service" `
    DisplayName= "Custom Application Service"

# Set a description so it looks like a real service
sc.exe description VulnSvc "Custom application management service"
```

Verify the service was created:

```powershell
sc.exe qc VulnSvc
```

You should see:
```
BINARY_PATH_NAME   : C:\CustomApp\Vuln Service\bin\svc.exe
SERVICE_START_NAME : NT AUTHORITY\Network Service
```

Notice `BINARY_PATH_NAME` has no quotes around the path. That is the vulnerability. Windows will try to resolve `C:\CustomApp\Vuln.exe` before it finds the real binary - and since `C:\CustomApp\` is world-writable, vamsi can plant a malicious `Vuln.exe` there.

Do NOT start the service now. Leave it stopped. Module 07 and 11 will walk you through exploiting it.

### 3.13 Cache Domain Admin Credentials in LSASS for Module 08

Module 08 teaches you to dump password hashes out of LSASS memory (the Windows process that stores active login credentials). For there to be anything worth dumping, a privileged account needs to have logged into this machine.

Log out of local `Administrator`. At the login screen, click **Other user** and log in as:
- Username: `CORP\Administrator`
- Password: `P@ssw0rd123!`

Once the desktop loads, open PowerShell and run:

```powershell
whoami
```

You should see `corp\administrator`. That is enough. The login event has put `CORP\Administrator`'s NTLM hash into LSASS memory.

Log out immediately. Log back in as `CORP\vamsi` for the baseline state.

When you take the baseline snapshot in Part 5, the LSASS memory will contain `CORP\Administrator`'s cached credentials. Module 08 will dump those and you will have the domain admin hash.

---

## Part 4: Verify Full Connectivity

### From Kali

```bash
# Can you reach Win11?
ping -c 3 192.168.10.20

# Can you reach the DC?
ping -c 3 192.168.10.30

# Can you reach the internet?
ping -c 3 8.8.8.8
```

All three should succeed.

### From Win11 (logged in as vamsi)

```powershell
# Can you reach Kali?
Test-NetConnection -ComputerName 192.168.10.10 -Port 80

# Can you reach the DC?
Test-NetConnection -ComputerName 192.168.10.30 -Port 389

# Is the machine on the domain?
systeminfo | findstr /i "domain"

# Can you resolve corp.local?
Resolve-DnsName corp.local
```

The domain info line should show `corp.local`.

### From DC (logged in as CORP\Administrator)

```powershell
# Can you see the workstation in AD?
Get-ADComputer -Filter * | Select-Object Name

# Can you see all users?
Get-ADUser -Filter * | Select-Object SamAccountName
```

You should see `WORKSTATION01` in computers, and `Administrator`, `Guest`, `krbtgt`, `vamsi`, `svc_backup` in users.

---

## Part 5: Take Snapshots

This is mandatory. Do not skip it.

Snapshots let you restore any VM to this exact clean state whenever you want. Before each module you revert to `baseline-clean`. After the module you can either revert again for the next module or continue building on the current state.

**Take a snapshot on each VM now:**

1. Make sure the VM is powered on and at a clean desktop
2. In VMware Pro, select the VM in the left panel
3. Go to the **VM** menu at the top -> **Snapshot** -> **Take Snapshot**
4. Name: `baseline-clean`
5. Description: `Clean baseline - AppLocker on, Defender on, domain joined`
6. Click **Take Snapshot**

Do this for all three VMs: Kali, WIN11-TARGET, DC01.

**To restore a snapshot later:**
VM menu -> Snapshot -> **Revert to Snapshot: baseline-clean**

Or go to VM menu -> Snapshot -> **Snapshot Manager** to see all your snapshots and choose which one to revert to.

---

## Complete Summary

### Your Lab At a Glance

| Machine | VM Name | IP | OS | Role |
|---------|---------|----|----|------|
| Attacker | kali | 192.168.10.10 | Kali Linux | Sliver C2, attack tools |
| Victim | WIN11-TARGET | 192.168.10.20 | Windows 11 Enterprise | Target, AppLocker + Defender on |
| DC | DC01 | 192.168.10.30 | Windows Server 2022 | corp.local domain controller |

### User Accounts

| Account | Type | Password | Used For |
|---------|------|----------|---------|
| `ammulu` | Win11 local user | `Ammulu@123` | Created during Win11 setup only |
| `CORP\vamsi` | Domain standard user | `vamsi123` | Your attack persona (every module) |
| `CORP\svc_backup` | Domain service account | `Backup@2024!` | Kerberoasting target in module 14 |
| `CORP\Administrator` | Domain Admin | `P@ssw0rd123!` | Your final goal |
| `WORKSTATION01\Administrator` | Local Admin | `LocalAdmin@123!` | Lab configuration only |

### Security Controls and Lab Configurations

| Item | State | Used In |
|------|-------|---------|
| Defender real-time protection | ON | All modules |
| AppLocker executable rules | Enforced | Module 02, 05 |
| AppLocker script rules | Enforced | Module 06 |
| AppLocker installer rules | Enforced | Module 02 |
| AppLocker DLL rules | Not configured (intentional gap) | Module 09 |
| Domain password complexity | Disabled for lab simplicity | All modules |
| WinRM on DC01 (port 5985) | Enabled | Module 12 |
| VulnSvc on WORKSTATION01 | Created (unquoted path, Network Service) | Module 07, 11 |
| CORP\Administrator cached in LSASS | Yes (after login in 3.13) | Module 08 |
| svc_backup local admin on WORKSTATION01 | Yes | Module 12, 14 |

---

If your lab matches everything in this summary, take your snapshots and move to the next module.

Open `02-initial-access-nim.md` next.
