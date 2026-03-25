import PlanWorkspace from '@/components/plan/PlanWorkspace';

export function generateStaticParams() {
  return [{ planId: 'plan-001' }];
}

export default async function PlanPage({ params }: { params: Promise<{ planId: string }> }) {
  const { planId } = await params;
  return <PlanWorkspace planId={planId} />;
}
