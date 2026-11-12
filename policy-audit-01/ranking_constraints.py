"""Can any observation-independent slot ranking reproduce these real choices?"""
from collections import defaultdict
import json
from audit import OUT, dump

snapshots=[json.loads(line) for line in (OUT/'snapshots.jsonl').read_text().splitlines()]
results={}
for row,robot in enumerate(('tb1','tb2','tb3')):
    edges,identical_masks={},defaultdict(dict)
    for r in snapshots:
        legal=tuple(i for i,v in enumerate(r['actual_conditional_masks'][row]) if v)
        if len(legal)<2:
            continue
        selected=r['choices'][row]
        fact=dict(case=r['case'],decision_id=r['decision_id'],sim=r['sim'],
                  legal_slots=list(legal),selected_slot=selected)
        identical_masks[legal].setdefault(selected,fact)
        for other in legal:
            if other!=selected:
                edges.setdefault((selected,other),fact)
    adjacency=defaultdict(list)
    for a,b in edges:
        adjacency[a].append(b)
    visited,active,stack=set(),set(),[]
    cycle=[]
    def visit(node):
        if node in active:
            return stack[stack.index(node):]+[node]
        if node in visited:
            return []
        active.add(node);stack.append(node)
        for target in adjacency[node]:
            found=visit(target)
            if found:
                return found
        stack.pop();active.remove(node);visited.add(node)
        return []
    for node in range(17):
        cycle=visit(node)
        if cycle:
            break
    same=[dict(legal_slots=list(mask),choices=list(choices.values()))
          for mask,choices in identical_masks.items() if len(choices)>1]
    results[robot]=dict(edge_count=len(edges),cycle=cycle,
        cycle_witnesses=[dict(preferred=a,over=b,record=edges[(a,b)]) for a,b in zip(cycle,cycle[1:])],
        identical_legal_masks_with_different_actual_choice=len(same),
        identical_mask_examples=same[:2],
        fixed_ranking_can_reproduce_all_actual_prefix_choices=not bool(cycle),
        limitation='Acyclic only means compatible with a fixed slot ranking on this finite set, not that model uses one.')
dump('REAL_RANKING_CONSTRAINTS.json',dict(method='Actual selected slot outranks other legal slots; cycles exclude any single fixed total ranking per robot including fixed tie order. No new inference.',
    scope='Frozen real-observation actual-prefix masks only; not an observation-ablation performance test.',robots=results))
print(json.dumps(results,ensure_ascii=False,indent=2))
