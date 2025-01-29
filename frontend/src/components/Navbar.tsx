import Link from 'next/link'

export default function Navbar() {
  return (
    <nav className="bg-gray-800 text-white p-4">
      <div className="container mx-auto flex justify-between items-center">
        <Link href="/" className="text-xl font-bold">Vroom</Link>
        <ul className="flex space-x-4">
          <li><Link href="/listings">Listings</Link></li>
          <li><Link href="/scrape">Scrape</Link></li>
          <li><Link href="/analysis">Analysis</Link></li>
          <li><Link href="/tasks">Tasks</Link></li>
        </ul>
      </div>
    </nav>
  )
}

