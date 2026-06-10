// app/routes/_index.tsx
import { Button } from "~/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "~/components/ui/card";

export function meta() {
  return [
    { title: "React Router + shadcn/ui" },
    { name: "description", content: "Modern React with beautiful components" },
  ];
}

export default function Home() {
  return (
    <div className="container mx-auto p-8">
      <Card>
        <CardHeader>
          <CardTitle>Welcome to React Journals v7</CardTitle>
        </CardHeader>
        <CardContent>
          <p>Full-stack React with shadcn/ui components</p>
          <Button className="mt-4">Get Started</Button>
        </CardContent>
      </Card>
    </div>
  );
}