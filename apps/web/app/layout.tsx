import './globals.css';
import AuthSessionGuard from '../components/auth-session-guard';

export const metadata = { title: 'GenQuantaa AI', description: 'AI interview and coding copilot' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body><AuthSessionGuard />{children}</body></html>;
}
