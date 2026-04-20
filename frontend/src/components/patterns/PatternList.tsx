import { PatternCard } from './PatternCard';
import { usePatternLibraryStore } from '../../stores/patternLibraryStore';
import { toast } from '../../lib/toast';

export function PatternList() {
  const items = usePatternLibraryStore((s) => s.items);
  const removePattern = usePatternLibraryStore((s) => s.removePattern);

  const handleDelete = async (id: string) => {
    try {
      await removePattern(id);
      toast.success('Pattern deleted');
    } catch {
      toast.error('Failed to delete pattern');
    }
  };

  return (
    <div className="flex flex-col gap-2" data-testid="pattern-list">
      {items.map((p) => (
        <PatternCard key={p.id} pattern={p} onDelete={handleDelete} />
      ))}
    </div>
  );
}
