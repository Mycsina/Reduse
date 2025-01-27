import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen py-2">
      <h1 className="text-4xl font-bold mb-8">Welcome to Vroom</h1>
      <p className="text-xl mb-8">Find and list used items with ease</p>
      <div className="flex space-x-4">
        <Button asChild>
          <Link href="/listings">Browse Listings</Link>
        </Button>
      </div>
    </div>
  );
}
