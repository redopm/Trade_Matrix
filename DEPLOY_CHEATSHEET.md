# 🚀 TradeMatrix — GitHub & Cloud VM Deployment Cheatsheet

Ye guide aapko yaad dilayegi ki local computer se code GitHub par kaise daalna hai aur Cloud VM par 1 click mein kaise deploy karna hai.

---

## 📌 Quick Summary Links
- **GitHub Repository:** [https://github.com/redopm/Trade_Matrix](https://github.com/redopm/Trade_Matrix)
- **Live Secure Website:** [https://34.68.221.238.sslip.io](https://34.68.221.238.sslip.io)
- **VM Name:** `tradematrix-vm` (Zone: `us-central1-a`, IP: `34.68.221.238`)

---

## 🛠️ Roz ke Kaam ke 2 Simple Steps

### Step 1: Apne Computer Par (Code GitHub Par Bhejo)
Jab bhi aap apne local system par koi code badlein:

```bash
# 1. Sare badle huye files ko stage karein
git add .

# 2. Commit message likhein
git commit -m "Mera naya feature ya bug fix"

# 3. GitHub par push karein
git push origin main
```

---

### Step 2: Cloud VM Par (1-Click Auto Deploy)

1. **Terminal se VM connect karein:**
   ```bash
   gcloud compute ssh tradematrix-vm --zone=us-central1-a
   ```

2. **VM ke andar sirf yeh 1 command chalayein:**
   ```bash
   ./deploy.sh
   ```

> **Ye script kya karta hai?**
> - GitHub se automatically naya code pull karega.
> - Backend aur trading services ko live update karke restart karega.
> - Health check karke dikhayega ki system 100% chal raha hai.

---

## 🔍 Useful Diagnostic Commands (Jab Bhi Check Karna Ho)

### 1. Website & Fyers Health Check (Terminal se):
```bash
# Backend Health check (200 OK aana chahiye)
curl https://34.68.221.238.sslip.io/health

# Fyers Broker Status (Connected aana chahiye)
curl https://34.68.221.238.sslip.io/api/v1/broker/status
```

### 2. VM ke Andar Container Status Dekhna:
```bash
# Teeno containers (caddy, backend, frontend) running dekhne ke liye:
docker ps

# Live backend trading logs dekhne ke liye:
docker logs tradematrix_backend --tail 50 -f
```
*(Live logs se bahar aane ke liye `Ctrl + C` dabayein)*
