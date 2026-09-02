/**
 * Step 10: Quick Actions - the three things an officer ever comes here to do.
 * Plain router links, so they work with keyboard and middle-click as usual.
 */

import { Link } from 'react-router-dom'

import { ChartIcon, FolderIcon, PlusIcon, ShieldIcon } from './Icons'

const ACTIONS = [
  {
    to: '/verify',
    label: 'Start Verification',
    description: 'Look up a CNIC and open a new verification case.',
    Icon: PlusIcon,
    primary: true,
  },
  {
    to: '/verifications',
    label: 'View Verification Cases',
    description: 'Track every case you can access and continue the ones in progress.',
    Icon: FolderIcon,
    primary: false,
  },
  {
    to: '/reports',
    label: 'Reports',
    description: 'Open an auditable verification report and download its PDF.',
    Icon: ChartIcon,
    primary: false,
  },
]

const STAGGER = ['gv-stagger-1', 'gv-stagger-2', 'gv-stagger-3']

export default function QuickActions() {
  return (
    <section aria-labelledby="quick-actions-heading">
      <div className="mb-3 flex items-center gap-2">
        <span className="text-brand-600" aria-hidden="true">
          <ShieldIcon size={15} />
        </span>
        <h2 id="quick-actions-heading" className="gv-eyebrow">
          Quick Actions
        </h2>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {ACTIONS.map(({ to, label, description, Icon, primary }, index) => (
          <Link
            key={to}
            to={to}
            className={`gv-card gv-card-hover animate-gv-fade-up group flex items-start gap-3 p-4 ${STAGGER[index] ?? 'gv-stagger-3'}`}
          >
            <span
              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-colors ${
                primary
                  ? 'bg-brand-600 text-white group-hover:bg-brand-700'
                  : 'bg-brand-50 text-brand-700 ring-1 ring-brand-100 group-hover:bg-brand-100'
              }`}
              aria-hidden="true"
            >
              <Icon size={18} />
            </span>
            <span className="min-w-0">
              <span className="block text-sm font-semibold text-gray-900">{label}</span>
              <span className="mt-0.5 block text-xs leading-relaxed text-gray-500">{description}</span>
            </span>
          </Link>
        ))}
      </div>
    </section>
  )
}
