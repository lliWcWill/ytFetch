'use client';

export default function AuthSetupPage() {
  const projectRef = 'rlrtrqednrmgfiwbidet';
  const redirectUrl = `https://${projectRef}.supabase.co/auth/v1/callback`;

  return (
    <div className="container mx-auto p-8 max-w-2xl">
      <h1 className="text-2xl font-bold mb-6">Google OAuth Setup Guide</h1>
      
      <div className="bg-gray-100 p-6 rounded-lg mb-6">
        <h2 className="text-xl font-semibold mb-4">Your Supabase Redirect URL:</h2>
        <code className="bg-white p-3 block rounded text-sm break-all">
          {redirectUrl}
        </code>
        <p className="mt-2 text-sm text-gray-600">
          Add this to "Authorized redirect URIs" in Google Cloud Console
        </p>
      </div>

      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Setup Steps:</h2>
        <ol className="list-decimal list-inside space-y-2">
          <li>Go to Google Cloud Console → APIs & Services → Credentials</li>
          <li>Create OAuth 2.0 Client ID (Web application)</li>
          <li>Add <code className="bg-gray-200 px-1">http://localhost:3000</code> to Authorized JavaScript origins</li>
          <li>Add the redirect URL above to Authorized redirect URIs</li>
          <li>Save and copy your Client ID and Client Secret</li>
          <li>Go to Supabase Dashboard → Authentication → Providers → Google</li>
          <li>Paste your Client ID and Client Secret there</li>
          <li>Enable the Google provider</li>
        </ol>
      </div>

      <div className="mt-8 p-4 bg-yellow-50 border border-yellow-200 rounded">
        <p className="font-semibold">Important:</p>
        <p>After completing setup, you can delete this page or keep it for reference.</p>
      </div>
    </div>
  );
}