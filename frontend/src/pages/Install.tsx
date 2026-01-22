import { AppLayout } from '@/components/layout/AppLayout';
import { AppHeader } from '@/components/layout/AppHeader';
import { InstallPage } from '@/components/pwa/InstallPrompt';

const Install = () => {
  return (
    <AppLayout>
      <AppHeader title="Install App" subtitle="Add Solar Hub to your device" />
      <InstallPage />
    </AppLayout>
  );
};

export default Install;
