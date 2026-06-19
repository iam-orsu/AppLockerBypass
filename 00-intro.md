# AppLocker Bypass - Introduction

## What is This Guide?

This guide teaches you how to bypass AppLocker on Windows 11.

AppLocker is a security feature built into Windows. Companies use it to control which programs can run on their computers. Your job as a security tester is to find out if AppLocker actually stops attacks - or if there are holes in it.

This guide assumes you know nothing about Windows security, PowerShell, or hacking. Every concept is explained before it is used.

---

## What is AppLocker?

Think of AppLocker like a bouncer at a club.

The bouncer has a list of people allowed inside. If your name is on the list, you get in. If not, you are turned away.

AppLocker works the same way. It has a list of programs that are allowed to run. If a program is on the list, it runs. If not, Windows blocks it.

The problem? The bouncer does not check the back door. This guide shows you where the back doors are.

---

## Why Should You Care?

**If you are a penetration tester:** Companies hire you to test their security. If AppLocker can be bypassed, you need to find it and report it before an attacker does.

**If you are a security analyst:** You need to understand how attackers bypass AppLocker so you can detect and stop it. You cannot defend against attacks you do not understand.

**If you are studying for certifications:** OSCP, CEH, and CompTIA PenTest+ all expect you to know how application control works and how to test it.

---

## What You Will Learn

Six bypass methods:

1. **LOLBins** - Using trusted Windows tools to run code AppLocker does not watch
2. **PowerShell Bypasses** - Encoding and running scripts in ways AppLocker does not catch
3. **DLL Hijacking** - Placing fake code libraries where real ones are expected
4. **COM Object Abuse** - Using internal Windows communication objects to run commands
5. **AMSI Bypass** - Disabling the antimalware scanner so malicious scripts are not detected
6. **Full Attack Chain** - Combining everything into a real attack scenario

---

## What You Need

- **VMware Workstation Pro** (your hypervisor)
- **Windows 11 Enterprise VM** (the target machine)
- **Kali Linux VM** (the attacker machine)

Setup instructions are in [01-lab-setup.md](./01-lab-setup.md).

---

## How Long Will This Take?

| File | Topic | Time |
|------|-------|------|
| 01 | Lab Setup | 60-90 min |
| 02 | PowerShell Intro | 45-60 min |
| 03 | AppLocker Deep Dive + Setup | 60-90 min |
| 04 | LOLBins Lab | 60-90 min |
| 05 | PowerShell Bypass Lab | 60-90 min |
| 06 | DLL Hijacking Lab | 60-90 min |
| 07 | COM Objects Lab | 45-60 min |
| 08 | AMSI Bypass Lab | 45-60 min |
| 09 | Full Attack Chain | 60-90 min |
| **Total** | | **7-9 hours** |

---

## Important

Everything in this guide is done on your own virtual machines. Testing on systems you do not own or do not have written permission to test is illegal.

Document your results as you go. Writing down what worked and what did not is how professional penetration testers work.

---

**Start here: [01-lab-setup.md](./01-lab-setup.md)**
