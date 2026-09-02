/**
 * Step 10: inline SVG icon set.
 *
 * Hand-written 24×24 stroke icons so the Command Center needs no extra
 * dependency (see the performance rule in Step 10). Every icon inherits the
 * current text colour and is `aria-hidden` by default - the surrounding
 * element carries the accessible name.
 */

import type { ReactNode, SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement> & {
  size?: number
  /** Set to false only when the icon conveys information on its own. */
  decorative?: boolean
}

function Icon({ size = 16, decorative = true, children, ...rest }: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={decorative || undefined}
      role={decorative ? undefined : 'img'}
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  )
}

export const CheckIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M20 6 9 17l-5-5" />
  </Icon>
)

export const CheckCircleIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="m8.5 12.5 2.5 2.5 4.5-5" />
  </Icon>
)

export const AlertIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
    <path d="M12 9v4" />
    <path d="M12 17h.01" />
  </Icon>
)

export const CloseCircleIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="m15 9-6 6M9 9l6 6" />
  </Icon>
)

export const ClockIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3.5 2" />
  </Icon>
)

export const DotIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="4" fill="currentColor" stroke="none" />
  </Icon>
)

export const MenuIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 6h16M4 12h16M4 18h16" />
  </Icon>
)

export const XIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M18 6 6 18M6 6l12 12" />
  </Icon>
)

export const LogoutIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <path d="m16 17 5-5-5-5" />
    <path d="M21 12H9" />
  </Icon>
)

export const UserIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </Icon>
)

export const ShieldIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
    <path d="m9 12 2 2 4-4" />
  </Icon>
)

export const SearchIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </Icon>
)

export const PlusIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 5v14M5 12h14" />
  </Icon>
)

export const FolderIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z" />
  </Icon>
)

export const UploadIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M21 15v3a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3v-3" />
    <path d="M12 16V4" />
    <path d="m7 9 5-5 5 5" />
  </Icon>
)

export const SparklesIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3.5 13.6 8l4.4 1.6-4.4 1.6L12 15.6 10.4 11.2 6 9.6l4.4-1.6Z" />
    <path d="M18.5 15.5 19.2 17.5 21 18.2 19.2 18.9 18.5 21 17.8 18.9 16 18.2 17.8 17.5Z" />
  </Icon>
)

export const DnaIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M5 3c0 6 14 4 14 10S5 15 5 21" />
    <path d="M19 3c0 6-14 4-14 10s14 0 14 8" />
    <path d="M8 6h8M8 18h8" />
  </Icon>
)

export const CompareIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3v18" />
    <path d="M5 8H2l3-5 3 5Z" />
    <path d="M19 8h-3l3-5 3 5Z" />
    <path d="M2 8c0 2.2 1.3 4 3 4s3-1.8 3-4" />
    <path d="M16 8c0 2.2 1.3 4 3 4s3-1.8 3-4" />
  </Icon>
)

export const ScaleIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 4v16M7 20h10" />
    <path d="M4 9h16" />
    <path d="M6 9 3.5 14.5h5L6 9Z" />
    <path d="M18 9l-2.5 5.5h5L18 9Z" />
  </Icon>
)

export const GavelIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M14 3 21 10l-2.5 2.5L11.5 5.5Z" />
    <path d="m9.5 7.5 7 7" />
    <path d="M3 21h11" />
    <path d="m6.5 17.5 4-4" />
  </Icon>
)

export const FileTextIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z" />
    <path d="M14 3v5h5" />
    <path d="M9 13h6M9 17h6" />
  </Icon>
)

export const DownloadIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 4v11" />
    <path d="m7 11 5 5 5-5" />
    <path d="M4 19h16" />
  </Icon>
)

export const PrinterIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M7 9V4h10v5" />
    <path d="M6 18H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-1" />
    <path d="M7 14h10v6H7z" />
  </Icon>
)

export const ChartIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
  </Icon>
)

export const LayoutIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="3" y="3" width="18" height="7" rx="2" />
    <rect x="3" y="14" width="8" height="7" rx="2" />
    <rect x="15" y="14" width="6" height="7" rx="2" />
  </Icon>
)

export const ArrowRightIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M5 12h14" />
    <path d="m13 6 6 6-6 6" />
  </Icon>
)

export const ChevronRightIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="m9 6 6 6-6 6" />
  </Icon>
)

export const ActivityIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3 12h4l2.5 7 5-14L17 12h4" />
  </Icon>
)

export const InboxIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3 12a9 9 0 0 1 18 0v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z" />
    <path d="M3 12h5l1.5 3h5L16 12h5" />
  </Icon>
)

export const InfoIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5M12 8h.01" />
  </Icon>
)

export const RefreshIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M21 12a9 9 0 1 1-3-6.7" />
    <path d="M21 4v5h-5" />
  </Icon>
)
