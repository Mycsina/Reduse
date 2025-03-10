'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiClient } from '@/lib/api-client';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';

export default function Home() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { toast } = useToast();

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    try {
      const response = await apiClient.naturalLanguageQuery(query);
      
      // Store the query in sessionStorage for the listings page
      sessionStorage.setItem('listingQuery', JSON.stringify(response.structured_query));
      
      // Redirect to the listings page
      router.push('/listings?nl=true');
    } catch (error) {
      console.error('Search error:', error);
      toast({
        title: 'Search failed',
        description: 'There was an error processing your query.',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="container mx-auto px-4 py-8">
      <h1 className="text-4xl font-bold mb-8 text-center">
        Find Your Next Deal with Natural Language
      </h1>
      
      <div className="max-w-2xl mx-auto mb-12">
        <form onSubmit={handleSearch} className="flex gap-2">
          <Input
            placeholder="Try 'Apartments under $500,000 with at least 2 bedrooms' or 'Red cars with low mileage'"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1"
          />
          <Button type="submit" disabled={loading}>
            {loading ? 'Searching...' : 'Search'}
          </Button>
        </form>
        
        <div className="mt-2 text-sm text-gray-500">
          Ask in plain language what you're looking for, and our AI will find it.
        </div>
      </div>
    </main>
  );
}
