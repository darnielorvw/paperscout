import {
    Pagination,
    PaginationContent,
    PaginationEllipsis,
    PaginationItem,
    PaginationLink,
    PaginationNext,
    PaginationPrevious,
} from "~/components/ui/pagination";

type ResultsPaginationProps = {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
};

export function ResultsPagination({
  currentPage,
  totalPages,
  onPageChange,
}: ResultsPaginationProps) {
  if (totalPages <= 1) {
    return null;
  }

  return (
    <div className="mt-auto border-t bg-background p-4">
      <Pagination>
        <PaginationContent className="w-full justify-between">
          <PaginationItem>
            <PaginationPrevious
              onClick={() => onPageChange(currentPage - 1)}
              disabled={currentPage <= 1}
            />
          </PaginationItem>

          <div className="flex items-center justify-center gap-0.5">
            {[...Array(totalPages)].map((_, i) => {
              const page = i + 1;
              if (
                page === currentPage ||
                page <= 2 ||
                page >= totalPages - 1 ||
                Math.abs(currentPage - page) <= 1
              ) {
                return (
                  <PaginationItem key={page}>
                    <PaginationLink
                      onClick={() => onPageChange(page)}
                      isActive={currentPage === page}
                    >
                      {page}
                    </PaginationLink>
                  </PaginationItem>
                );
              }
              if (page === currentPage - 2 || page === currentPage + 2) {
                return <PaginationEllipsis key={page} />;
              }
              return null;
            })}
          </div>

          <PaginationItem>
            <PaginationNext
              onClick={() => onPageChange(currentPage + 1)}
              disabled={currentPage >= totalPages}
            />
          </PaginationItem>
        </PaginationContent>
      </Pagination>
    </div>
  );
}
