"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Nav({ links }: { links: [href: string, label: string][] }) {
  const path = usePathname();
  // Mục khớp dài nhất được đánh dấu (để /yeu-cau/moi không làm sáng cả /yeu-cau)
  const active = links
    .map(([href]) => href)
    .filter((href) => path === href || (href !== "/" && path.startsWith(href + "/")))
    .sort((a, b) => b.length - a.length)[0];
  return (
    <nav>
      {links.map(([href, label]) => (
        <Link key={href} href={href} className={href === active ? "active" : undefined}>
          {label}
        </Link>
      ))}
    </nav>
  );
}
