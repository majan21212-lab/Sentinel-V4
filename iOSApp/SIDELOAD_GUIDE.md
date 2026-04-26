# 📱 iPhone Installation Guide (Windows)

Since you are running on Windows, we are using a **Cloud Build + Sideloadly** workflow. This allows you to install the **Jewel Elite** bot on your iPhone without owning a Mac.

---

## 🛠️ Step 1: Generate the Installer

1.  **Push your code to GitHub**: Ensure the `FlutterApp` folder and `.github` folder are in your repository.
2.  **Go to "Actions" Tab**: In your GitHub repository, click on the **Actions** tab at the top.
3.  **Download Artifact**:
    - Find the latest run of **"Build Flutter iOS Installer"**.
    - Once finished, scroll down to the "Artifacts" section.
    - Download the `JewelElite_Flutter_IPA` zip and extract the `JewelElite_Flutter.ipa`.

## 🚀 Step 2: Install on iPhone

1.  **Download Sideloadly**: Go to [sideloadly.io](https://sideloadly.io/) and install it on your Windows PC.
2.  **Connect iPhone**: Plug your iPhone into your PC via USB. (Ensure you "Trust" the computer on the phone).
3.  **Open Sideloadly**:
    - **IPA File**: Drag and drop the `JewelElite_Flutter.ipa` into the Sideloadly window.
    - **Apple ID**: Enter your Free Apple ID (email).
    - **Start**: Click "Start". You may be asked for your Apple ID password (this is sent securely to Apple for signing).
4.  **Trust the App**:
    - Once it says "Done", the app will appear on your iPhone.
    - **It won't open yet!** Go to **Settings > General > VPN & Device Management**.
    - Tap on your Apple ID and select **"Trust [Your Email]"**.

## ⚖️ Important Limitations

- **7-Day Limit**: Because you are using a Free Apple ID, the app will expire every 7 days. You just need to plug it back into Sideloadly and click "Start" again to refresh it (your data will be saved).
- **Network**: Ensure your iPhone can reach your Bot's API (check the `FastAPIService.swift` for the correct server URL).

---

### 🔍 Troubleshooting

- **No Device Found (Most Common)**:
  1. **Check iTunes**: Open iTunes. If your iPhone isn't showing up there, Sideloadly won't see it either.
  2. **Install iTunes (Web Version)**: If you installed iTunes from the Microsoft Store, it often fails to provide the right drivers. **Uninstall it** and download the 64-bit version directly from [Apple's website](https://www.apple.com/itunes/download/win64).
  3. **Trust Computer**: Unlock your iPhone and tap **"Trust"** when the popup appears.
  4. **Restart Services**: Press `Win + R`, type `services.msc`, and restart **Apple Mobile Device Service**.

- **Signing Error**: Check if your Apple ID has 2FA enabled; Sideloadly will prompt for the code.
- **Connection Timeout (WinError 10060)**:
  1. **Use a VPN**: If you are in a region where Apple services are restricted, try using a VPN. If you are already using one, try disabling it or switching servers.
  2. **Anisette Settings**: In Sideloadly, click **Advanced Options** and change **Anisette Authentication** from `Local` to `Remote` (or vice versa).
  3. **Firewall**: Ensure `Sideloadly.exe` is allowed through your Windows Firewall.
  4. **DNS**: Try changing your PC DNS to Google (`8.8.8.8`) or Cloudflare (`1.1.1.1`).
