import { Card } from '../ui/card';
import { Button } from '../ui/button';
import { ArrowLeft } from 'lucide-react';

export function PrivacyPolicyScreen() {
  return (
    <div className="min-h-full bg-muted pb-4">
      {/* Header */}
      <div className="bg-card border-b sticky top-0 z-10">
        <div className="max-w-2xl mx-auto px-4 py-4 flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => window.history.back()}>
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <h1 className="text-xl font-semibold">Privacy Policy</h1>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-2xl mx-auto px-4 py-6">
        <Card className="p-6">
          <div className="prose prose-sm max-w-none">
            <p className="text-muted-foreground text-sm mb-6">Last updated: December 2024</p>

            <h2 className="text-lg font-semibold mt-6 mb-3">1. Introduction</h2>
            <p className="text-foreground mb-4">
              FloodSafe ("we", "our", or "us") is a nonprofit flood monitoring platform committed to protecting your privacy.
              This Privacy Policy explains how we collect, use, and safeguard your information when you use our mobile application.
            </p>

            <h2 className="text-lg font-semibold mt-6 mb-3">2. Information We Collect</h2>
            <p className="text-foreground mb-2">We collect the following types of information:</p>
            <ul className="list-disc pl-5 text-foreground mb-4 space-y-1">
              <li><strong>Account Information:</strong> Name, email, phone number (for authentication)</li>
              <li><strong>Location Data:</strong> GPS coordinates when you submit flood reports or set watch areas</li>
              <li><strong>User Content:</strong> Flood reports, photos, and descriptions you submit</li>
              <li><strong>Device Information:</strong> Device type, operating system, for service optimization</li>
            </ul>

            <h2 className="text-lg font-semibold mt-6 mb-3">3. How We Use Your Information</h2>
            <p className="text-foreground mb-2">Your information is used to:</p>
            <ul className="list-disc pl-5 text-foreground mb-4 space-y-1">
              <li>Provide flood alerts and warnings for your watch areas</li>
              <li>Display community flood reports on the map</li>
              <li>Calculate safe routes that avoid flood-prone areas</li>
              <li>Improve our flood prediction models</li>
              <li>Send emergency notifications</li>
            </ul>

            <h2 className="text-lg font-semibold mt-6 mb-3">4. Data Sharing</h2>
            <p className="text-foreground mb-4">
              We do not sell your personal information. Flood reports you submit are shared publicly on the map
              to help the community. Your profile information is only visible according to your privacy settings.
            </p>

            <h2 className="text-lg font-semibold mt-6 mb-3">5. Data Security</h2>
            <p className="text-foreground mb-4">
              We implement industry-standard security measures to protect your data, including encryption
              in transit and at rest, secure authentication, and regular security audits.
            </p>

            <h2 className="text-lg font-semibold mt-6 mb-3">6. Your Rights</h2>
            <p className="text-foreground mb-2">You have the right to:</p>
            <ul className="list-disc pl-5 text-foreground mb-4 space-y-1">
              <li>Access your personal data</li>
              <li>Update or correct your information</li>
              <li>Delete your account and associated data</li>
              <li>Opt-out of non-essential communications</li>
              <li>Control your profile visibility</li>
            </ul>

            <h2 className="text-lg font-semibold mt-6 mb-3">7. Contact Us</h2>
            <p className="text-foreground mb-4">
              For privacy-related questions or concerns, contact us at:{' '}
              <a href="mailto:privacy@floodsafe.app" className="text-primary hover:underline">
                privacy@floodsafe.app
              </a>
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}
