import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Listing Details",
  description: "View details of a specific listing",
};

export default function ListingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
