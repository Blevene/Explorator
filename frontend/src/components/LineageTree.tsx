interface LineageNode {
  id: string;
  label: string;
  chordSymbols: string[];
  round?: number;
  children: LineageNode[];
}

interface LineageTreeProps {
  candidates: Array<{
    candidate_id: string;
    chord_symbols: string[];
    metadata?: Record<string, unknown>;
  }>;
  onSelectCandidate?: (id: string) => void;
}

function buildTree(candidates: LineageTreeProps['candidates']): LineageNode[] {
  const byId = new Map<string, LineageTreeProps['candidates'][0]>();
  const childrenOf = new Map<string, string[]>();
  const roots: string[] = [];

  for (const c of candidates) {
    byId.set(c.candidate_id, c);
    const parentId = c.metadata?.mutated_from as string | undefined;
    if (parentId && byId.has(parentId)) {
      const children = childrenOf.get(parentId) ?? [];
      children.push(c.candidate_id);
      childrenOf.set(parentId, children);
    } else if (!parentId) {
      roots.push(c.candidate_id);
    }
  }

  // Also add mutants whose parents aren't in our candidate list as roots
  for (const c of candidates) {
    const parentId = c.metadata?.mutated_from as string | undefined;
    if (parentId && !byId.has(parentId) && !roots.includes(c.candidate_id)) {
      roots.push(c.candidate_id);
    }
  }

  function toNode(id: string): LineageNode {
    const c = byId.get(id);
    const children = childrenOf.get(id) ?? [];
    return {
      id,
      label: id.slice(0, 12) + '...',
      chordSymbols: c?.chord_symbols ?? [],
      round: c?.metadata?.mutation_round as number | undefined,
      children: children.map(toNode),
    };
  }

  return roots.map(toNode);
}

function TreeNode({
  node,
  depth,
  onSelect,
}: {
  node: LineageNode;
  depth: number;
  onSelect?: (id: string) => void;
}) {
  const isMutant = depth > 0;

  return (
    <div className={depth > 0 ? 'ml-4 border-l border-gray-700 pl-3' : ''}>
      <div
        onClick={() => onSelect?.(node.id)}
        className="flex items-center gap-2 py-1 px-2 rounded hover:bg-gray-800 cursor-pointer group"
      >
        {isMutant && (
          <span className="text-cyan-500 text-xs">⟳</span>
        )}
        <span className="text-xs font-mono text-gray-300 group-hover:text-white">
          {node.label}
        </span>
        {node.round && (
          <span className="text-xs text-gray-600">R{node.round}</span>
        )}
        <span className="text-xs text-gray-500 truncate max-w-[150px]">
          {node.chordSymbols.join(' → ')}
        </span>
      </div>
      {node.children.map((child) => (
        <TreeNode key={child.id} node={child} depth={depth + 1} onSelect={onSelect} />
      ))}
    </div>
  );
}

export default function LineageTree({ candidates, onSelectCandidate }: LineageTreeProps) {
  const tree = buildTree(candidates);

  // Don't show if no mutations have occurred
  const hasMutations = candidates.some((c) => c.metadata?.mutated_from);
  if (!hasMutations) return null;

  return (
    <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-3">
      <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
        Mutation Lineage
      </h4>
      {tree.map((root) => (
        <TreeNode key={root.id} node={root} depth={0} onSelect={onSelectCandidate} />
      ))}
    </div>
  );
}
