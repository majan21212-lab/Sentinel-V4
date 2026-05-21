# 🚀 Sentinel-V4 VPS Deployment Guide (IP: 35.184.162.126)

This document is for the USER and the Antigravity instance on the remote VPS.

## 1. Environment Preparation
The VPS should be running Windows Server (recommended for MT5) or Windows 10/11.
Ensure the following are installed:
- Python 3.10+
- Git
- MetaTrader 5 Terminal (logged into Exness)
- Nginx (for web exposure)

## 2. Automated Setup
Run the `setup_vps.ps1` script located in this directory. It will:
- Install required python libraries.
- Configure Windows Firewall to allow port 8000 (Local) and 80 (Public).
- Create a 'Sentinel' background task to keep the bot running 24/7.

## 3. Web Interface Access
- URL: `http://35.184.162.126:8000`
- To enable HTTPS/SSL, use the provided Nginx config.

## 4. Security Checklist
- [ ] Change the default `shared_state.json` passwords if applicable.
- [ ] Ensure SSH/RDP access to the VPS is restricted to your IP.
- [ ] Enable the 'Kill Switch' in the dashboard before doing major updates.

---
Created by Antigravity on 2026-04-27.
