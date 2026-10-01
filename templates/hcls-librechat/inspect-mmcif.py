#!/usr/bin/env python3
"""Read-only mmCIF inventory. Coordinate coverage is not MD readiness."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import gemmi


def rows(block, category):
    values = block.get_mmcif_category(category)
    if not values:
        return []
    keys = list(values)
    return [dict(zip(keys, values)) for values in zip(*(values[k] for k in keys))]


def intervals(values):
    result = []
    for value in sorted(set(values)):
        if result and value == result[-1][1] + 1:
            result[-1][1] = value
        else:
            result.append([value, value])
    return result


def inventory(path):
    path = Path(path)
    raw = path.read_bytes()
    doc = gemmi.cif.read_string(raw.decode('utf-8'))
    if len(doc) != 1:
        raise ValueError('Choose a single data block explicitly; multi-block input is not silently merged')
    block = doc.sole_block()
    atoms = rows(block, '_atom_site.')
    if not atoms:
        raise ValueError('No coordinate atoms in _atom_site')
    entities = {r['id']: r for r in rows(block, '_entity.')}
    components = {r['id']: r for r in rows(block, '_chem_comp.')}
    seq = defaultdict(set)
    for r in rows(block, '_entity_poly_seq.'):
        seq[r['entity_id']].add(int(r['num']))
    grouped = defaultdict(list)
    for atom in atoms:
        grouped[(atom.get('pdbx_PDB_model_num', '1'), atom['label_asym_id'],
                 atom['label_entity_id'])].append(atom)
    chains, nonpolymers = [], []
    for (model, label, entity_id), group in sorted(grouped.items()):
        entity = entities.get(entity_id, {})
        item = {'model': model, 'label_asym_id': label,
                'auth_asym_ids': sorted({a['auth_asym_id'] for a in group}),
                'entity_id': entity_id, 'entity_type': entity.get('type', 'unknown'),
                'description': entity.get('pdbx_description'), 'atom_records': len(group),
                'elements': dict(sorted(Counter(a['type_symbol'] for a in group).items()))}
        if entity.get('type') == 'polymer':
            observed = {int(a['label_seq_id']) for a in group
                        if str(a.get('label_seq_id', '')).isdigit()}
            declared = seq[entity_id]
            item.update({'modeled_sequence_positions': len(observed),
                'declared_sequence_positions': len(declared) if declared else None,
                'unmodeled_label_seq_id_ranges': intervals(declared - observed) if declared else None,
                'coverage_basis': 'label_seq_id vs entity_poly_seq; NOT gaps in author residue numbering'})
            chains.append(item)
        else:
            residue_ids = {(a.get('label_comp_id'), a.get('auth_seq_id'),
                            a.get('pdbx_PDB_ins_code')) for a in group}
            ids = sorted({a['label_comp_id'] for a in group})
            item.update({'residue_count': len(residue_ids), 'components': [
                {'id': cid, 'name': components.get(cid, {}).get('name'),
                 'formula': components.get(cid, {}).get('formula')} for cid in ids]})
            nonpolymers.append(item)
    classified = all(entities.get(eid, {}).get('type') in ('polymer', 'non-polymer', 'water', 'branched')
                     for (_, _, eid) in grouped)
    return {'schema': 'scientific-mmcif-inventory/v1', 'file': str(path),
        'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw),
        'parser': {'name': 'gemmi', 'version': gemmi.__version__},
        'data_block': block.name, 'atom_records': len(atoms),
        'models': sorted({a.get('pdbx_PDB_model_num', '1') for a in atoms}),
        'elements': dict(sorted(Counter(a['type_symbol'] for a in atoms).items())),
        'alternate_location_atom_records': sum(a.get('label_alt_id') not in (None, False, '', '.', '?')
                                              for a in atoms),
        'entity_classification_complete': classified,
        'polymer_chains': chains, 'nonpolymer_components': nonpolymers,
        'water_atom_records': sum(len(group) for (_, _, eid), group in grouped.items()
                                  if entities.get(eid, {}).get('type') == 'water') if classified else None,
        'limitations': [
            'Declared sequence includes construct tags/fusions; unmodeled positions are not automatically receptor loops.',
            'Author residue-number jumps do not measure missing sequence.',
            'Counts are atom-site records; alternate locations, if present, are not collapsed. No chemical atom-completeness check was performed.',
            'This inventory does not parameterize, repair or establish MD readiness.']}


def markdown(result):
    lines = [f"Inventory: `{Path(result['file']).name}`", '',
             f"Whole file: {result['atom_records']} atom-site records across {len(result['models'])} model(s).",
             '', '| Model | Polymer chain (label / author) | Description | Modeled / declared residues | Atom-site records |',
             '|---|---|---|---:|---:|']
    for chain in result['polymer_chains']:
        description = str(chain['description'] or 'unspecified').replace('|', '\\|').replace('\n', ' ')
        lines.append(f"| {chain['model']} | {chain['label_asym_id']} / {', '.join(chain['auth_asym_ids'])} | "
                     f"{description} | {chain['modeled_sequence_positions']} / {chain['declared_sequence_positions'] or 'unknown'} | {chain['atom_records']} |")
    lines.extend(['', '| Model | Non-polymer chain | Components | Residues | Atom-site records |',
                  '|---|---|---|---:|---:|'])
    for component in result['nonpolymer_components']:
        lines.append(f"| {component['model']} | {component['label_asym_id']} | "
                     f"{', '.join(c['id'] for c in component['components'])} | {component['residue_count']} | {component['atom_records']} |")
    lines.extend(['', f"Water atom-site records: {result['water_atom_records'] if result['water_atom_records'] is not None else 'unknown (incomplete entity metadata)' }.",
                  f"Alternate-location atom-site records: {result['alternate_location_atom_records']}.",
                  'Counts describe coordinates only. Chemical completeness, loop/domain assignments and MD readiness were not checked.',
                  f"Source SHA-256: `{result['sha256']}`."])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--format', choices=['json', 'markdown'], default='json')
    args = parser.parse_args()
    result = inventory(args.input)
    print(markdown(result) if args.format == 'markdown' else json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
