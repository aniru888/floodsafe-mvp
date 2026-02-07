import { Card } from '../ui/card';
import { Button } from '../ui/button';
import { ArrowLeft } from 'lucide-react';

export function TermsScreen() {
  return (
    <div className="min-h-full bg-muted pb-4">
      {/* Header */}
      <div className="bg-card border-b sticky top-0 z-10">
        <div className="max-w-2xl mx-auto px-4 py-4 flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => window.history.back()}>
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <h1 className="text-xl font-semibold">Terms of Service</h1>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-2xl mx-auto px-4 py-6">
        <Card className="p-6">
          <div className="prose prose-sm max-w-none">
            <p className="text-muted-foreground text-sm mb-6">Last updated: December 2024</p>

            <h2 className="text-lg font-semibold mt-6 mb-3">1. Acceptance of Terms</h2>
            <p className="text-foreground mb-4">
              By accessing or using FloodSafe, you agree to be bound by these Terms of Service.
              If you do not agree to these terms, please do not use the application.
            </p>

            <h2 className="text-lg font-semibold mt-6 mb-3">2. Description of Service</h2>
            <p className="text-foreground mb-4">
              FloodSafe is a nonprofit community flood monitoring platform that provides:
            </p>
            <ul className="list-disc pl-5 text-foreground mb-4 space-y-1">
              <li>Real-time flood alerts and warnings</li>
              <li>Community-reported flood information</li>
              <li>Safe route navigation during floods</li>
              <li>Weather-based flood risk predictions</li>
            </ul>

            <h2 className="text-lg font-semibold mt-6 mb-3">3. User Responsibilities</h2>
            <p className="text-foreground mb-2">As a user, you agree to:</p>
            <ul className="list-disc pl-5 text-foreground mb-4 space-y-1">
              <li>Provide accurate information when submitting flood reports</li>
              <li>Not submit false or misleading reports</li>
              <li>Use the service responsibly and not for any unlawful purpose</li>
              <li>Not attempt to interfere with the proper functioning of the service</li>
              <li>Respect other users and the community</li>
            </ul>

            <h2 className="text-lg font-semibold mt-6 mb-3">4. Disclaimer of Warranties</h2>
            <p className="text-foreground mb-4">
              FloodSafe is provided "as is" without warranties of any kind. While we strive to provide
              accurate flood information, we cannot guarantee the accuracy, completeness, or timeliness
              of all data. <strong>Always follow official government advisories and use your own judgment
              in emergency situations.</strong>
            </p>

            <h2 className="text-lg font-semibold mt-6 mb-3">5. Limitation of Liability</h2>
            <p className="text-foreground mb-4">
              FloodSafe and its operators shall not be liable for any damages arising from your use of
              the service, including but not limited to decisions made based on flood alerts, route
              recommendations, or community reports. This is a community-driven tool meant to supplement,
              not replace, official emergency services.
            </p>

            <h2 className="text-lg font-semibold mt-6 mb-3">6. User Content</h2>
            <p className="text-foreground mb-4">
              By submitting flood reports, photos, or other content, you grant FloodSafe a non-exclusive,
              royalty-free license to use, display, and share this content for the purpose of providing
              the service and improving flood monitoring.
            </p>

            <h2 className="text-lg font-semibold mt-6 mb-3">7. Account Termination</h2>
            <p className="text-foreground mb-4">
              We reserve the right to suspend or terminate accounts that violate these terms or submit
              false reports. You may delete your account at any time through the app settings.
            </p>

            <h2 className="text-lg font-semibold mt-6 mb-3">8. Changes to Terms</h2>
            <p className="text-foreground mb-4">
              We may update these terms from time to time. Continued use of the service after changes
              constitutes acceptance of the new terms.
            </p>

            <h2 className="text-lg font-semibold mt-6 mb-3">9. Contact</h2>
            <p className="text-foreground mb-4">
              For questions about these terms, contact us at:{' '}
              <a href="mailto:legal@floodsafe.app" className="text-primary hover:underline">
                legal@floodsafe.app
              </a>
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}
