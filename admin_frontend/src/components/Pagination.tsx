import { ChevronLeft, ChevronRight } from 'lucide-react';

interface PaginationProps {
  total: number;
  limit: number;
  skip: number;
  onPageChange: (newSkip: number) => void;
}

export default function Pagination({ total, limit, skip, onPageChange }: PaginationProps) {
  const totalPages = Math.ceil(total / limit);
  const currentPage = Math.floor(skip / limit) + 1;

  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-between px-6 py-4 border-t border-border bg-secondary/10">
      <p className="text-sm text-muted-foreground">
        Показано <span className="font-bold text-foreground">{Math.min(skip + 1, total)}</span> - <span className="font-bold text-foreground">{Math.min(skip + limit, total)}</span> из <span className="font-bold text-foreground">{total}</span>
      </p>
      
      <div className="flex items-center gap-2">
        <button
          onClick={() => onPageChange(Math.max(0, skip - limit))}
          disabled={currentPage === 1}
          className="p-2 h-9 w-9 flex items-center justify-center rounded-lg border border-border bg-background disabled:opacity-50 hover:bg-secondary transition-colors"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
        
        <div className="flex items-center gap-1">
          {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
            // Simple logic for first 5 pages, can be improved for many pages
            const pageNum = i + 1;
            const pageSkip = i * limit;
            return (
              <button
                key={pageNum}
                onClick={() => onPageChange(pageSkip)}
                className={`h-9 w-9 flex items-center justify-center rounded-lg text-sm font-bold transition-all ${
                  currentPage === pageNum ? 'bg-primary text-white' : 'hover:bg-secondary'
                }`}
              >
                {pageNum}
              </button>
            );
          })}
          {totalPages > 5 && <span className="px-2 text-muted-foreground">...</span>}
        </div>

        <button
          onClick={() => onPageChange(skip + limit)}
          disabled={currentPage === totalPages}
          className="p-2 h-9 w-9 flex items-center justify-center rounded-lg border border-border bg-background disabled:opacity-50 hover:bg-secondary transition-colors"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
