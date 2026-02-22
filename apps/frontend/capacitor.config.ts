import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.floodsafe.app',
  appName: 'FloodSafe',
  webDir: 'dist',
  server: {
    androidScheme: 'http',  // Capacitor 6+ defaults to https; keep http for WebView compat
  },
};

export default config;
