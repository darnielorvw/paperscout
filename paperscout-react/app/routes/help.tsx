import {
  BookmarkIcon,
  CalendarRangeIcon,
  ListIcon,
  MailIcon,
  NewspaperIcon,
  SlidersHorizontalIcon,
  TextSearchIcon,
  UserIcon,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "~/components/ui/card";
import { protectPage } from "~/lib/auth";

export function clientLoader() {
  protectPage();
  return null;
}

type HelpSection = {
  id: string;
  title: string;
  icon: LucideIcon;
  // Where the section's feature lives in the app.
  link?: { to: string; label: string };
  summary: string;
  tips: ReactNode[];
};

const quickStart = [
  "Pick the journals you want to follow.",
  "Choose the publication time range.",
  "Optionally enter a search term or a semantic search, then start the search.",
  "Mark interesting papers and save them to your reading list.",
  "Save the search parameters as a profile to get it by email every month.",
];

const sections: HelpSection[] = [
  {
    id: "search",
    title: "Search",
    icon: TextSearchIcon,
    link: { to: "/", label: "Start a search" },
    summary:
      "Narrow the results to papers about a topic, either with a search term or with the semantic search. Both are optional and don't go together.",
    tips: [
      <>
        <strong>Keyword Search</strong> finds papers containing your words. It
        has higher loading times than a search without a term.
      </>,
      <>
        <strong>Semantic Search</strong> finds papers by meaning rather than
        exact words. Describe what you are looking for in full sentences: an
        abstract, a research aim or a paragraph from your own paper. The richer
        the description, the better the matches.
      </>,
      "The semantic search returns up to 50 papers, the most similar first, and uses only the first 2,000 characters.",
      "The semantic search only filters by year: it finds papers from every month of the years in your time range. That's why semantic profiles get no monthly email.",
      "Some journals cannot be searched semantically. They are listed below the field and left out of the results.",
    ],
  },
  {
    id: "results",
    title: "Results",
    icon: ListIcon,
    link: { to: "/results", label: "Open results" },
    summary:
      "The papers matching your journals, time range and search, shown page by page.",
    tips: [
      <>
        <strong>Find at library</strong> opens the paper through your library,
        so you get the full text with your institution's access.
      </>,
      <>
        <strong>Open publisher page</strong> follows the DOI to the publisher's
        page of the paper.
      </>,
      <>
        Tick <strong>Mark for reading list</strong> on the papers you want to
        keep, then click <strong>Save to reading list</strong>.
      </>,
    ],
  },
  {
    id: "reading-list",
    title: "Reading List",
    icon: BookmarkIcon,
    link: { to: "/reading-list", label: "Open reading list" },
    summary: "All papers you have saved, in one place.",
    tips: [
      <>
        Tick <strong>Read</strong> on a paper once you have read it. The list
        shows unread papers by default; switch to <strong>Read</strong> or{" "}
        <strong>All</strong> to see the others.
      </>,
      <>
        If your library has no access to a paper, click{" "}
        <strong>Request PDF</strong>. An admin looks for the PDF; once it is
        uploaded, <strong>Open PDF</strong> appears on the paper. You can
        withdraw a request at any time.
      </>,
      <>
        To remove papers, click <strong>Remove papers</strong>, mark them and
        click <strong>Remove selected</strong>.
      </>,
    ],
  },
  {
    id: "profiles",
    title: "Profiles",
    icon: SlidersHorizontalIcon,
    link: { to: "/profiles", label: "Manage profiles" },
    summary:
      "A profile saves a selection of journals together with a search term or semantic search, so you can run the search again with one click.",
    tips: [
      "Set up journals and search first, then navigate to the profile page, enter a name and click Save.",
      "Switch between profiles in the bar at the top of every page, or click Apply on the profile.",
      <>
        To change a profile, adjust its journals or search and click{" "}
        <strong>Save to Profile</strong>.
      </>,
    ],
  },
  {
    id: "digest",
    title: "Monthly Email",
    icon: MailIcon,
    link: { to: "/profiles", label: "Turn on emails" },
    summary:
      "PaperScout can send you the new papers of your profiles once a month.",
    tips: [
      <>
        Turn on <strong>Email notifications</strong> on each profile you want to
        receive.
      </>,
      "Only profiles with a keyword search can get the email; the semantic search only filters by year.",
      "At the start of every month you get the papers published in the previous month, up to 25 per profile.",
      "Each paper comes with its DOI and a link to the full text via your library.",
      "A link per profile opens all results in PaperScout, so you can go through the rest and save papers.",
    ],
  },
  {
    id: "account",
    title: "Account",
    icon: UserIcon,
    link: { to: "/account", label: "Open account" },
    summary:
      "Click your name at the bottom of the sidebar to manage your account.",
    tips: [
      "Change your email address or password.",
      "The library link depends on your email domain, so use your institution's email address.",
      "Deleting your account also deletes your profiles and cannot be undone.",
    ],
  },
];

export default function HelpPage() {
  return (
    <div className="flex w-full flex-col gap-6 p-4">
      <div>
        <h1 className="text-2xl font-bold">Help</h1>
        <p className="text-muted-foreground">
          PaperScout finds new papers in the journals you follow and helps you
          keep track of the ones worth reading.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Quick Start</CardTitle>
          <CardDescription>Your first search in five steps.</CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="list-decimal space-y-1 pl-5 text-sm">
            {quickStart.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </CardContent>
      </Card>

      <nav className="flex flex-wrap gap-2 text-sm" aria-label="Help topics">
        {sections.map((section) => (
          <a
            key={section.id}
            href={`#${section.id}`}
            className="rounded-full border px-3 py-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground"
          >
            {section.title}
          </a>
        ))}
      </nav>

      <div className="grid gap-4 md:grid-cols-2">
        {sections.map((section) => (
          <Card key={section.id} id={section.id} className="scroll-mt-4">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <section.icon className="size-4" />
                {section.title}
              </CardTitle>
              <CardDescription>{section.summary}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {section.tips.map((tip, index) => (
                  <li key={index}>{tip}</li>
                ))}
              </ul>
              {section.link && (
                <Link
                  to={section.link.to}
                  className="text-sm font-medium text-sidebar-primary underline-offset-4 hover:underline"
                >
                  {section.link.label} →
                </Link>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
