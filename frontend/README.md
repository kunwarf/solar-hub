# Solar Hub Frontend

A modern React-based web application for monitoring and managing solar energy systems. Built with TypeScript, Vite, Tailwind CSS, and shadcn/ui components.

## Features

- **Real-time Dashboard**: Live monitoring of solar production, battery status, and energy consumption
- **Device Management**: View and configure inverters, batteries, and meters
- **Billing & Tariffs**: Pakistani DISCO tariff calculations with net metering support
- **Load Shedding Tracking**: Monitor and track power outages
- **Alerts & Notifications**: Configurable alert rules and notifications
- **PWA Support**: Installable progressive web app with offline capabilities
- **Mobile Optimized**: Responsive design with mobile-specific features

## Tech Stack

- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS + shadcn/ui components
- **State Management**: React Context + TanStack Query
- **Charts**: Recharts
- **Animations**: Framer Motion
- **HTTP Client**: Axios
- **PWA**: vite-plugin-pwa

## Prerequisites

- Node.js 18+ (LTS recommended)
- npm 9+ or yarn 1.22+

## Quick Start

### Development

```bash
# Install dependencies
npm install

# Copy environment file
cp .env.example .env

# Start development server
npm run dev
```

The app will be available at `http://localhost:8080`

### Testing with curl

You can verify the development server is running using curl:

**Basic connectivity test:**
```bash
curl http://localhost:8080
```

**Check HTTP status code:**
```bash
curl -I http://localhost:8080
```

**Get full response headers:**
```bash
curl -v http://localhost:8080
```

**Test specific endpoint (e.g., API health check if backend is running):**
```bash
# Test frontend
curl http://localhost:8080

# Test backend API (if running on port 8000)
curl http://localhost:8000/api/v1/health
```

**Windows PowerShell (using Invoke-WebRequest):**
```powershell
# Basic test
Invoke-WebRequest -Uri http://localhost:8080

# Check status only
Invoke-WebRequest -Uri http://localhost:8080 -Method Head

# Get status code
(Invoke-WebRequest -Uri http://localhost:8080).StatusCode
```

**Expected responses:**
- **200 OK**: Server is running and responding
- **Connection refused**: Server is not running or wrong port
- **Timeout**: Firewall may be blocking the connection

**Troubleshooting "Connection refused" (Linux):**

If you get "Connection refused", the dev server is not running. Check and start it:

```bash
# Check if anything is listening on port 8080
sudo netstat -tlnp | grep 8080
# or
sudo ss -tlnp | grep 8080
# or
sudo lsof -i :8080

# Check if node/npm processes are running
ps aux | grep -E "node|npm|vite"

# Start the development server
cd /opt/solarhub/app/solar-hub/frontend
npm run dev

# Or if using a process manager (PM2, systemd, etc.)
# Check service status
systemctl status solar-hub-frontend  # if using systemd
pm2 list  # if using PM2
```

**Note:** The dev server must be running in a terminal or as a background service for curl to work.

### Accessing from Other Devices

The development server is configured to listen on all network interfaces, so you can access it from other devices on your local network.

#### Step 1: Find Your Machine's IP Address

**Windows (PowerShell):**
```powershell
ipconfig | findstr IPv4
```

**Windows (Command Prompt):**
```cmd
ipconfig
```
Look for the IPv4 address under your active network adapter (usually starts with `192.168.x.x` or `10.x.x.x`).

#### Step 2: Configure Windows Firewall

Allow incoming connections on port 8080:

**Option A: Using PowerShell (Run as Administrator):**
```powershell
New-NetFirewallRule -DisplayName "Solar Hub Dev Server" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow
```

**Option B: Using Windows Firewall GUI:**
1. Open Windows Defender Firewall
2. Click "Advanced settings"
3. Click "Inbound Rules" → "New Rule"
4. Select "Port" → Next
5. Select "TCP" and enter port `8080` → Next
6. Select "Allow the connection" → Next
7. Check all profiles → Next
8. Name it "Solar Hub Dev Server" → Finish

#### Step 3: Access from Other Devices

Once the server is running and the firewall is configured, access the app from any device on the same network using:

```
http://YOUR_IP_ADDRESS:8080
```

For example, if your IP is `192.168.1.100`, use: `http://192.168.1.100:8080`

#### Step 4: Update Backend API URLs (If Needed)

If you also want to access the backend API from external devices, you'll need to:

1. Update your `.env` file to use your machine's IP instead of `localhost`:
   ```env
   VITE_API_BASE_URL=http://YOUR_IP_ADDRESS:8000/api/v1
   VITE_WS_URL=ws://YOUR_IP_ADDRESS:8000/ws
   ```

2. Ensure your backend server is also configured to accept external connections (check backend configuration)

3. Allow port 8000 in Windows Firewall (if running backend locally)

**Note:** For security reasons, only use this setup on trusted local networks. For production deployment, use proper hosting services or configure a reverse proxy with authentication.

### Production Build

```bash
# Build for production
npm run build

# Preview production build locally
npm run preview
```

## Environment Configuration

Create a `.env` file in the frontend directory:

```env
# API Configuration
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws

# Enable mock fallback when API is unavailable
# Set to 'false' in production when backend is available
VITE_USE_MOCK_FALLBACK=true

# Application Settings
VITE_APP_NAME=Solar Hub
VITE_APP_VERSION=1.0.0

# Feature Flags
VITE_ENABLE_PWA=true
VITE_ENABLE_AI_INSIGHTS=true
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:8000/api/v1` |
| `VITE_WS_URL` | WebSocket URL for real-time data | `ws://localhost:8000/ws` |
| `VITE_USE_MOCK_FALLBACK` | Use mock data when API unavailable | `true` |

## Deployment

### Production Deployment on Linux Server (Nginx on Port 8080)

This section covers deploying the frontend to a Linux production server using nginx on port 8080 (when port 80 is already in use).

#### Prerequisites

- Linux server (Debian/Ubuntu recommended)
- Node.js 18+ installed
- nginx installed
- Root or sudo access

#### Important: Existing Nginx Configuration

**Will this affect my existing application?**

No, this configuration will NOT affect your existing application because:

1. **Different Port**: The Solar Hub frontend uses port **8080**, while your existing app likely uses port **80** (or **443** for HTTPS)
2. **Separate Server Block**: Each nginx site configuration is independent
3. **No Port Conflicts**: nginx can handle multiple server blocks listening on different ports simultaneously

**Before proceeding, check your existing nginx setup:**

```bash
# List all active nginx sites
ls -la /etc/nginx/sites-enabled/

# Check what ports nginx is currently using
sudo netstat -tlnp | grep nginx
# or
sudo ss -tlnp | grep nginx

# View your existing nginx configuration
sudo nginx -T | grep -E "listen|server_name"

# Check if port 8080 is already in use
sudo lsof -i :8080
# or
sudo netstat -tlnp | grep 8080
```

**What to look for:**
- If port 8080 is already in use, choose a different port (e.g., 8081, 3000, etc.) and update the nginx config accordingly
- Your existing site on port 80/443 will remain completely unaffected
- Each nginx site configuration file is independent

**If you want to be extra safe:**

1. **Test nginx configuration before reloading:**
   ```bash
   # This only tests, doesn't apply changes
   sudo nginx -t
   ```

2. **Backup your current nginx config:**
   ```bash
   sudo cp -r /etc/nginx/sites-available /etc/nginx/sites-available.backup
   sudo cp -r /etc/nginx/sites-enabled /etc/nginx/sites-enabled.backup
   ```

3. **If something goes wrong, you can quickly revert:**
   ```bash
   # Remove the new site
   sudo rm /etc/nginx/sites-enabled/solarhub-frontend
   sudo systemctl reload nginx
   ```

**Multiple nginx sites example:**

Your nginx can have multiple configurations like this:
- `/etc/nginx/sites-enabled/default` → Port 80 (your existing app)
- `/etc/nginx/sites-enabled/solarhub-frontend` → Port 8080 (Solar Hub)
- `/etc/nginx/sites-enabled/another-app` → Port 3000 (another app)

All can run simultaneously without conflicts!

#### Step 1: Build the Production Bundle

```bash
# Navigate to frontend directory
cd /opt/solarhub/app/solar-hub/frontend

# Install dependencies (if not already done)
npm install

# Create production environment file
cp .env.example .env

# Edit .env with production API URLs
nano .env
```

Update `.env` for production:
```env
# API Configuration - Use your server's IP or domain
VITE_API_BASE_URL=http://YOUR_SERVER_IP:8000/api/v1
# Or if using domain:
# VITE_API_BASE_URL=https://api.yourdomain.com/api/v1

VITE_WS_URL=ws://YOUR_SERVER_IP:8000/ws
# Or if using domain:
# VITE_WS_URL=wss://api.yourdomain.com/ws

# Disable mock fallback in production
VITE_USE_MOCK_FALLBACK=false

# Application Settings
VITE_APP_NAME=Solar Hub
VITE_APP_VERSION=1.0.0

# Feature Flags
VITE_ENABLE_PWA=true
VITE_ENABLE_AI_INSIGHTS=true
```

Build the production bundle:
```bash
# Build for production
npm run build

# Verify build output
ls -la dist/
```

The `dist/` directory contains the production-ready static files.

#### Step 2: Configure Nginx

**Important:** You already have a `solarhub` nginx config on ports 80/443. We'll add a separate config for port 8080 that won't affect your existing setup.

**Option A: Use the provided config file (Recommended)**

```bash
# Copy the production nginx config
sudo cp /opt/solarhub/app/solar-hub/frontend/nginx.production.conf /etc/nginx/sites-available/solarhub-frontend-8080

# Update the root path to match your build directory
sudo nano /etc/nginx/sites-available/solarhub-frontend-8080
```

**Note:** The config file uses `/opt/solarhub/app/solar-hub/frontend/dist` - make sure this matches where your `npm run build` outputs files (should be in the `dist/` directory).

**Option B: Create custom configuration**

Create a new nginx configuration file:

```bash
sudo nano /etc/nginx/sites-available/solarhub-frontend-8080
```

**Option C: Add port 8080 to existing solarhub config (Alternative)**

If you prefer to add port 8080 to your existing `/etc/nginx/sites-available/solarhub` config instead of creating a separate file, you can add a new server block. However, **Option A is recommended** to keep configurations separate and easier to manage.

Add the following configuration (listening on port 8080):

```nginx
# Rate limiting
limit_req_zone $binary_remote_addr zone=frontend_limit:10m rate=10r/s;

# Frontend server on port 8080
server {
    listen 8080;
    listen [::]:8080;
    server_name _;

    # Root directory for static files
    root /opt/solarhub/app/solar-hub/frontend/dist;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml application/json application/javascript application/rss+xml application/atom+xml image/svg+xml;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # SPA fallback - serve index.html for all routes
    location / {
        try_files $uri $uri/ /index.html;
        limit_req zone=frontend_limit burst=20 nodelay;
    }

    # Deny access to hidden files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }

    # Health check endpoint (optional)
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
```

Enable the site:
```bash
# Create symlink (using a different name to avoid confusion with existing solarhub config)
sudo ln -s /etc/nginx/sites-available/solarhub-frontend-8080 /etc/nginx/sites-enabled/

# Test nginx configuration (VERY IMPORTANT - checks all configs including your existing solarhub)
sudo nginx -t

# If test passes, reload nginx (this won't affect your existing sites on ports 80/443/8123)
sudo systemctl reload nginx
```

**Note:** 
- The `nginx -t` command tests ALL nginx configurations, including your existing `solarhub`, `homeassistant`, and `openmediavault-webgui` configs
- If it reports any errors, fix them before reloading
- The reload is graceful and won't interrupt your existing applications
- Your existing `solarhub` config on ports 80/443 will continue working normally
- The new config only adds port 8080 as an additional entry point

#### Step 3: Configure Firewall

Allow port 8080 through the firewall:

```bash
# UFW (Ubuntu/Debian)
sudo ufw allow 8080/tcp
sudo ufw reload

# Or firewalld (CentOS/RHEL)
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload
```

#### Step 4: Test the Deployment

```bash
# Test from localhost
curl http://localhost:8080

# Test from another machine (replace with your server IP)
curl http://YOUR_SERVER_IP:8080

# Verify all your sites are still working
curl http://localhost          # Your existing app (port 80)
curl http://localhost:8080     # Solar Hub frontend (new)
curl http://localhost:8123     # Home Assistant (if accessible)

# Check nginx status
sudo systemctl status nginx

# Check what ports nginx is listening on
sudo netstat -tlnp | grep nginx

# Check nginx error logs if issues occur
sudo tail -f /var/log/nginx/error.log
```

**Note about the http2 deprecation warning:**

You may see a warning like:
```
the "listen ... http2" directive is deprecated, use the "http2" directive instead
```

This is from your existing `solarhub` config. It's just a warning and won't break anything, but you can fix it later by updating `/etc/nginx/sites-available/solarhub`:

**Old (deprecated):**
```nginx
listen 443 ssl http2;
```

**New (recommended):**
```nginx
listen 443 ssl;
http2 on;
```

This is optional and can be done later - it doesn't affect functionality.

#### Step 5: Set Up Auto-rebuild on Code Updates (Optional)

Create a deployment script:

```bash
sudo nano /opt/solarhub/scripts/deploy-frontend.sh
```

```bash
#!/bin/bash
set -e

echo "Building frontend..."

cd /opt/solarhub/app/solar-hub/frontend

# Pull latest code (if using git)
# git pull origin main

# Install dependencies
npm install

# Build production bundle
npm run build

# Reload nginx
sudo systemctl reload nginx

echo "Frontend deployed successfully!"
```

Make it executable:
```bash
sudo chmod +x /opt/solarhub/scripts/deploy-frontend.sh
```

#### Troubleshooting

**Issue: Existing application stopped working after adding Solar Hub config**
- This should NOT happen, but if it does:
  - Check nginx error logs: `sudo tail -f /var/log/nginx/error.log`
  - Verify your existing site config is still enabled: `ls -la /etc/nginx/sites-enabled/`
  - Test all nginx configs: `sudo nginx -T` (look for syntax errors)
  - Check if port 80 is still listening: `sudo netstat -tlnp | grep :80`
  - If needed, remove Solar Hub config temporarily: `sudo rm /etc/nginx/sites-enabled/solarhub-frontend && sudo systemctl reload nginx`

**Issue: 502 Bad Gateway or Connection Refused**
- Check if nginx is running: `sudo systemctl status nginx`
- Verify the `dist/` directory exists and has files
- Check nginx error logs: `sudo tail -f /var/log/nginx/error.log`

**Issue: 404 on page refresh**
- Ensure the `try_files` directive includes `/index.html` fallback
- Verify the `root` path in nginx config is correct

**Issue: API calls failing**
- Check `.env` file has correct `VITE_API_BASE_URL`
- Rebuild after changing `.env`: `npm run build`
- Verify backend is running on port 8000

**Issue: Port 8080 not accessible from outside**
- Check firewall rules: `sudo ufw status`
- Verify nginx is listening: `sudo netstat -tlnp | grep 8080`
- Check if another service is using port 8080: `sudo lsof -i :8080`

**Issue: Port 8080 already in use**
- Find what's using it: `sudo lsof -i :8080`
- Choose a different port (e.g., 8081, 3000, 9000)
- Update the nginx config to use the new port
- Update firewall rules for the new port

#### Updating the Frontend

When you need to update the frontend:

```bash
cd /opt/solarhub/app/solar-hub/frontend

# Pull latest changes (if using git)
git pull origin main

# Rebuild
npm run build

# Reload nginx
sudo systemctl reload nginx
```

### Option 1: Static Hosting (Recommended)

The frontend builds to static files that can be hosted on any static hosting service.

#### Vercel

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel --prod
```

#### Netlify

```bash
# Install Netlify CLI
npm i -g netlify-cli

# Build and deploy
npm run build
netlify deploy --prod --dir=dist
```

#### AWS S3 + CloudFront

```bash
# Build
npm run build

# Sync to S3
aws s3 sync dist/ s3://your-bucket-name --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id YOUR_DIST_ID --paths "/*"
```

### Option 2: Docker

Create a `Dockerfile` in the frontend directory:

```dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL
ARG VITE_WS_URL
ARG VITE_USE_MOCK_FALLBACK=false
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

Create `nginx.conf`:

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    # Cache static assets
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy (optional - if backend on same domain)
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Build and run:

```bash
# Build image
docker build -t solar-hub-frontend \
  --build-arg VITE_API_BASE_URL=https://api.yourdomain.com/api/v1 \
  --build-arg VITE_WS_URL=wss://api.yourdomain.com/ws \
  .

# Run container on port 8080 (if port 80 is in use)
docker run -d -p 8080:80 solar-hub-frontend

# Or on port 80
docker run -d -p 80:80 solar-hub-frontend
```

### Option 3: Docker Compose (Full Stack)

Add to your `docker-compose.yml`:

```yaml
services:
  frontend:
    build:
      context: ./frontend
      args:
        VITE_API_BASE_URL: http://localhost:8000/api/v1
        VITE_WS_URL: ws://localhost:8000/ws
        VITE_USE_MOCK_FALLBACK: "false"
    ports:
      - "3000:80"
    depends_on:
      - backend
```

## Project Structure

```
frontend/
├── public/              # Static assets
│   ├── icons/          # PWA icons
│   └── manifest.json   # PWA manifest
├── src/
│   ├── api/            # API client and services
│   │   ├── client.ts   # Axios client with interceptors
│   │   ├── config.ts   # API configuration
│   │   ├── types.ts    # TypeScript interfaces
│   │   └── services/   # API service modules
│   ├── components/     # React components
│   │   ├── dashboard/  # Dashboard widgets
│   │   ├── devices/    # Device components
│   │   ├── layout/     # Layout components
│   │   ├── ui/         # shadcn/ui components
│   │   └── ...
│   ├── contexts/       # React contexts
│   ├── hooks/          # Custom hooks
│   ├── pages/          # Page components
│   ├── data/           # Mock data (development)
│   ├── lib/            # Utilities
│   ├── App.tsx         # Main app component
│   └── main.tsx        # Entry point
├── .env.example        # Environment template
├── package.json
├── tailwind.config.ts
├── tsconfig.json
└── vite.config.ts
```

## API Integration

The frontend connects to the System A backend API. Key integration points:

### Authentication
- JWT-based authentication with refresh tokens
- Automatic token refresh on 401 responses
- Mock fallback for development without backend

### Real-time Data
- WebSocket connection for live telemetry
- HTTP polling fallback when WebSocket unavailable
- Automatic reconnection with exponential backoff

### Mock Mode
When `VITE_USE_MOCK_FALLBACK=true`, the app uses realistic mock data:
- Simulated solar production based on time of day
- Mock user authentication (demo@example.com / Password123!)
- Simulated device telemetry

## Development

### Demo Credentials

When running in mock mode:
- **Email**: `demo@example.com`
- **Password**: `Password123!`

Or:
- **Email**: `admin@solarhub.pk`
- **Password**: `Admin123!`

### Available Scripts

```bash
npm run dev       # Start development server
npm run build     # Build for production
npm run preview   # Preview production build
npm run lint      # Run ESLint
```

### Code Style

- ESLint for linting
- Prettier for formatting (via ESLint)
- TypeScript strict mode enabled

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Integration Status

### Phase 1: API Infrastructure (Complete)
- API client with Axios
- JWT token management
- Mock fallback system
- Authentication service
- Dashboard service

### Phase 2: Authentication (In Progress)
- Login/Register integration
- Token refresh
- User preferences

### Phase 3-7: Upcoming
- Dashboard real-time data
- Device management
- Billing & tariffs
- Alerts system
- User management

## License

Proprietary - Solar Hub

## Support

For issues and feature requests, please contact the development team.
