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

The app will be available at `http://localhost:5173`

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

# Run container
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
