import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate', // Auto-update without user prompt for immediate deployment visibility
      includeAssets: ['favicon.svg', 'apple-touch-icon.png'],
      manifest: {
        name: 'FloodSafe - Real-time Flood Monitoring',
        short_name: 'FloodSafe',
        description: 'Community-powered flood monitoring and safe navigation for Delhi',
        theme_color: '#3B82F6',
        background_color: '#ffffff',
        display: 'standalone',
        orientation: 'portrait',
        scope: '/',
        start_url: '/',
        icons: [
          {
            src: '/pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: '/pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: '/pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        // Allow larger bundles for precaching (default is 2MB, our bundle is ~2.2MB)
        maximumFileSizeToCacheInBytes: 3 * 1024 * 1024, // 3 MB
        // Import custom SW code for SOS Background Sync handler
        importScripts: ['/sw-sos-sync.js'],
        // Cache static assets (JS, CSS, fonts) - CacheFirst
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-cache',
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 60 * 60 * 24 * 365, // 1 year
              },
              cacheableResponse: {
                statuses: [0, 200],
              },
            },
          },
          {
            urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'gstatic-fonts-cache',
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 60 * 60 * 24 * 365, // 1 year
              },
              cacheableResponse: {
                statuses: [0, 200],
              },
            },
          },
          // MapLibre CSS
          {
            urlPattern: /^https:\/\/unpkg\.com\/maplibre-gl.*\.css$/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'maplibre-css-cache',
              expiration: {
                maxEntries: 5,
                maxAgeSeconds: 60 * 60 * 24 * 30, // 30 days
              },
            },
          },
          // ML classification endpoint - NetworkOnly, no timeout (can take 30s+ on mobile)
          // Must be defined BEFORE general API rule due to regex matching order
          {
            urlPattern: /\/api\/ml\/classify/i,
            handler: 'NetworkOnly',
            options: {
              // No caching - each image classification is unique
              // No networkTimeoutSeconds - let the request complete naturally
              // Frontend handles its own timeout via AbortController
            },
          },
          // API calls - NetworkFirst with cache fallback (excludes ML classification above)
          {
            urlPattern: /\/api\/.*/i,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              expiration: {
                maxEntries: 100,
                maxAgeSeconds: 60 * 60 * 24, // 24 hours
              },
              networkTimeoutSeconds: 10,
              cacheableResponse: {
                statuses: [0, 200],
              },
            },
          },
          // PMTiles map tiles - CacheFirst with size limit
          {
            urlPattern: /\.pmtiles$/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'pmtiles-cache',
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 60 * 60 * 24 * 7, // 7 days
              },
              rangeRequests: true,
            },
          },
          // GeoJSON files - StaleWhileRevalidate
          {
            urlPattern: /\.geojson$/i,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'geojson-cache',
              expiration: {
                maxEntries: 20,
                maxAgeSeconds: 60 * 60 * 24, // 24 hours
              },
            },
          },
          // Images - CacheFirst
          {
            urlPattern: /\.(png|jpg|jpeg|svg|gif|webp)$/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'images-cache',
              expiration: {
                maxEntries: 100,
                maxAgeSeconds: 60 * 60 * 24 * 30, // 30 days
              },
            },
          },
        ],
        // Precache essential files
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        globIgnores: ['**/firebase-messaging-sw.js'],  // Handled by Firebase, not Workbox
        // Skip waiting for new service worker - immediately activate new SW
        skipWaiting: true,
        clientsClaim: true,
        cleanupOutdatedCaches: true, // Remove stale precache entries on SW update
      },
      devOptions: {
        enabled: false, // Disable in dev to avoid caching issues during development
      },
    }),
  ],
  server: {
    host: '0.0.0.0',
    port: 5175,  // Use 5175 for Google OAuth compatibility
    strictPort: true,
    watch: {
      usePolling: true,
    },
    headers: {
      // Required for PMTiles range requests
      'Accept-Ranges': 'bytes',
      // Allow cross-origin requests (needed for PMTiles)
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
      'Access-Control-Allow-Headers': 'Range',
      // Disable caching in dev to prevent HMR reload issues
      'Cache-Control': 'no-store',
    },
    // Configure HMR for WebSocket connections
    hmr: {
      host: 'localhost',
      port: 5175,
    },
  },
  // Optimize asset handling
  build: {
    assetsInlineLimit: 0, // Don't inline any assets
    rollupOptions: {
      output: {
        // Ensure PMTiles files are handled correctly
        assetFileNames: (assetInfo) => {
          if (assetInfo.name && assetInfo.name.endsWith('.pmtiles')) {
            return 'assets/[name]-[hash][extname]';
          }
          return 'assets/[name]-[hash][extname]';
        },
      },
    },
  },
})
