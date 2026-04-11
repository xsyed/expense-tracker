#!/usr/bin/env bash
# VPS setup script — run once as root on the VPS (68.183.206.181)
# Idempotent: safe to re-run

set -euo pipefail

# --- 1. Install dependencies ---
apt update && apt install -y nginx certbot python3-certbot-nginx sqlite3 curl fail2ban ufw

# --- 2. Deploy nginx config ---
cp "$(dirname "$0")/nginx/expense-tracker.conf" /etc/nginx/sites-available/scorptech.ca

# Enable site if not already linked
if [ ! -L /etc/nginx/sites-enabled/scorptech.ca ]; then
    ln -s /etc/nginx/sites-available/scorptech.ca /etc/nginx/sites-enabled/scorptech.ca
fi

# Remove default site to avoid conflicts
rm -f /etc/nginx/sites-enabled/default

# Validate and reload nginx
nginx -t && systemctl reload nginx

# --- 3. Create app directories ---
mkdir -p /home/sami/expense-tracker/data \
         /home/sami/expense-tracker/backups \
         /home/sami/expense-tracker/staticfiles
chown -R sami:sami /home/sami/expense-tracker

# --- 4. UFW firewall ---
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# --- 5. fail2ban ---
cat > /etc/fail2ban/jail.local << 'EOF'
[nginx-limit-req]
enabled = true
filter = nginx-limit-req
logpath = /var/log/nginx/error.log
maxretry = 5
bantime = 3600
findtime = 600

[nginx-botsearch]
enabled = true
filter = nginx-botsearch
logpath = /var/log/nginx/access.log
maxretry = 2
bantime = 86400

[sshd]
enabled = true
maxretry = 3
bantime = 3600
EOF

systemctl enable fail2ban
systemctl restart fail2ban

echo "VPS setup complete. Next steps:"
echo "  1. Point DNS A records for scorptech.ca and www.scorptech.ca to 68.183.206.181"
echo "  2. Wait for DNS propagation: dig scorptech.ca +short"
echo "  3. Run: certbot --nginx -d scorptech.ca -d www.scorptech.ca --email ssamiuddin007@gmail.com --agree-tos"
